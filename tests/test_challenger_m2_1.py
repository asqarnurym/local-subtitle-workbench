"""Adversarial stress test harness for Milestone 2 of Increment 5.

Verifies:
1. VRAM cleanup: transcriber.unload() is always called across all error paths.
2. Output collision: ValueError raised when output path collides with input audio or transcript.
3. Existing output directory rejection: ValueError raised when output directory contains artifacts.
4. Audio error handling: corrupt WAV, missing audio file, 0-byte file, 0 frames, truncated data.
5. Transcript handling: empty string, whitespace string, empty file, missing file, punctuation.
6. Pipeline property checks: monotonicity, chunk duration bounds, manifest SHA-256 integrity.
7. CLI integration error paths: exit code 2 contract without stack traces.
"""

import hashlib
import json
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from subtitle_workbench.cli import main
from subtitle_workbench.models import ASRSegment, WordToken
from subtitle_workbench.pipeline import run_speech_pipeline


def create_pcm16_wav(
    path: Path,
    duration_sec: float = 2.0,
    sample_rate: int = 16000,
    channels: int = 1,
    sampwidth: int = 2,
) -> None:
    """Create a PCM WAV file with specified audio properties."""
    path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(round(sample_rate * duration_sec))
    t = np.linspace(0, duration_sec, num_samples, endpoint=False)
    signal = (np.sin(2 * np.pi * 440 * t) * 16384).astype(np.int16)
    if channels == 2:
        samples = np.column_stack((signal, signal)).ravel()
    else:
        samples = signal

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sampwidth)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())


def make_mock_transcriber(words_spec: list[tuple[str, str, float, float]] | None = None):
    """Create mock transcriber returning valid segments."""
    if words_spec is None:
        words_spec = [
            ("alpha", "alpha", 0.1, 0.8),
            ("beta", "beta", 0.9, 1.8),
        ]
    tokens = [
        WordToken(
            id=f"w_{i}",
            text=t,
            normalized=n,
            start=s,
            end=e,
            confidence=0.95,
            char_start=0,
            char_end=len(t),
        )
        for i, (t, n, s, e) in enumerate(words_spec)
    ]
    seg = ASRSegment(
        id="seg_0",
        start=words_spec[0][2],
        end=words_spec[-1][3],
        text=" ".join(w[0] for w in words_spec),
        words=tokens,
    )
    mock = MagicMock()
    mock.transcribe.return_value = [seg]
    mock.unload = MagicMock()
    return mock


def make_mock_aligner(words_spec: list[tuple[str, str, float, float]] | None = None):
    """Create mock aligner returning reconciled WordTokens."""
    if words_spec is None:
        words_spec = [
            ("alpha", "alpha", 0.12, 0.78),
            ("beta", "beta", 0.92, 1.78),
        ]
    tokens = [
        WordToken(
            id=f"w_{i}",
            text=t,
            normalized=n,
            start=s,
            end=e,
            confidence=0.91,
            char_start=0,
            char_end=len(t),
        )
        for i, (t, n, s, e) in enumerate(words_spec)
    ]
    mock = MagicMock()
    mock.align_chunks.return_value = tokens
    return mock


# =============================================================================
# 1. Adversarial VRAM Cleanup Tests
# =============================================================================


def test_vram_cleanup_on_cuda_oom_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """transcriber.unload() must be invoked when transcribe raises CUDA OOM."""
    wav_path = tmp_path / "audio.wav"
    out_dir = tmp_path / "out_oom"
    create_pcm16_wav(wav_path, duration_sec=1.5)

    monkeypatch.setattr(
        "subtitle_workbench.pipeline.extract_vad_silences",
        lambda *args, **kwargs: [],
    )

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe.side_effect = RuntimeError("CUDA out of memory")
    mock_transcriber.unload = MagicMock()

    with pytest.raises(RuntimeError, match="CUDA out of memory"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=out_dir,
            transcriber=mock_transcriber,
        )

    mock_transcriber.unload.assert_called_once()
    assert not (out_dir / "manifest.json").exists()


def test_vram_cleanup_on_generic_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """transcriber.unload() must be invoked when transcribe raises unexpected Exception."""
    wav_path = tmp_path / "audio.wav"
    out_dir = tmp_path / "out_err"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    monkeypatch.setattr(
        "subtitle_workbench.pipeline.extract_vad_silences",
        lambda *args, **kwargs: [],
    )

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe.side_effect = ValueError("Corrupted feature tensor shape")
    mock_transcriber.unload = MagicMock()

    with pytest.raises(ValueError, match="Corrupted feature tensor shape"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=out_dir,
            transcriber=mock_transcriber,
        )

    mock_transcriber.unload.assert_called_once()
    assert not (out_dir / "manifest.json").exists()


def test_vram_cleanup_when_no_segments_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """transcriber.unload() must be invoked before pipeline raises on empty segments."""
    wav_path = tmp_path / "audio.wav"
    out_dir = tmp_path / "out_empty_seg"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    monkeypatch.setattr(
        "subtitle_workbench.pipeline.extract_vad_silences",
        lambda *args, **kwargs: [],
    )

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe.return_value = []
    mock_transcriber.unload = MagicMock()

    with pytest.raises(ValueError, match="no speech segments detected in audio"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=out_dir,
            transcriber=mock_transcriber,
        )

    mock_transcriber.unload.assert_called_once()


def test_vram_cleanup_when_vad_silences_throws(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A VAD failure is a pipeline error (no silent fallback); the model is still unloaded."""
    wav_path = tmp_path / "audio.wav"
    out_dir = tmp_path / "out_vad_fail"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    def failing_vad(*args, **kwargs):
        raise RuntimeError("Silero VAD model failed to initialize")

    monkeypatch.setattr("subtitle_workbench.pipeline.extract_vad_silences", failing_vad)

    mock_transcriber = make_mock_transcriber([("hello", "hello", 0.1, 0.9)])
    mock_aligner = make_mock_aligner([("hello", "hello", 0.1, 0.9)])

    with pytest.raises(RuntimeError, match="Silero VAD model failed to initialize"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=out_dir,
            transcriber=mock_transcriber,
            aligner=mock_aligner,
        )

    mock_transcriber.unload.assert_called_once()
    mock_aligner.align_chunks.assert_not_called()
    assert not (out_dir / "manifest.json").exists()


def test_transcriber_duck_typing_without_unload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pipeline must handle a transcriber object that does not implement unload()."""
    wav_path = tmp_path / "audio.wav"
    out_dir = tmp_path / "out_nounload"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    monkeypatch.setattr(
        "subtitle_workbench.pipeline.extract_vad_silences",
        lambda *args, **kwargs: [],
    )

    class PlainTranscriber:
        def transcribe(self, path):
            token = WordToken(
                id="w_0",
                text="test",
                normalized="test",
                start=0.1,
                end=0.9,
                confidence=0.9,
            )
            return [ASRSegment(id="s_0", start=0.1, end=0.9, text="test", words=[token])]

    mock_aligner = make_mock_aligner([("test", "test", 0.1, 0.9)])

    manifest = run_speech_pipeline(
        audio_path=wav_path,
        output_dir=out_dir,
        transcriber=PlainTranscriber(),
        aligner=mock_aligner,
    )
    assert manifest["metrics"]["word_count"] == 1


# =============================================================================
# 2. Adversarial Output Collision Tests
# =============================================================================


def test_collision_when_output_dir_is_input_audio_exact(tmp_path: Path) -> None:
    """output_dir exactly matching audio_path must raise ValueError."""
    wav_path = tmp_path / "speech.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    with pytest.raises(ValueError, match="output may not overwrite an input"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=wav_path,
            transcript_text="test transcript",
        )


def test_collision_when_output_dir_is_input_audio_via_relative_path(tmp_path: Path) -> None:
    """output_dir resolving to audio_path via relative syntax must raise ValueError."""
    wav_path = tmp_path / "speech.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    relative_output = wav_path.parent / "." / wav_path.name
    with pytest.raises(ValueError, match="output may not overwrite an input"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=relative_output,
            transcript_text="test transcript",
        )


@pytest.mark.parametrize(
    "artifact_name",
    ["subtitles.vtt", "timeline.jsonld", "alignment_raw.json", "manifest.json"],
)
def test_collision_when_audio_file_named_as_output_artifact(
    tmp_path: Path, artifact_name: str
) -> None:
    """If input audio is named like an output artifact inside output_dir, reject with ValueError."""
    out_dir = tmp_path / "collision_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_as_artifact = out_dir / artifact_name
    create_pcm16_wav(audio_as_artifact, duration_sec=1.0)

    collision_pattern = "(output files already exist|output may not overwrite an input)"
    with pytest.raises(ValueError, match=collision_pattern):
        run_speech_pipeline(
            audio_path=audio_as_artifact,
            output_dir=out_dir,
            transcript_text="test transcript",
        )


def test_collision_when_output_dir_is_transcript_file(tmp_path: Path) -> None:
    """output_dir resolving to input transcript file must raise ValueError."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)
    transcript_file = tmp_path / "transcript.txt"
    transcript_file.write_text("sample transcript text", encoding="utf-8")

    with pytest.raises(ValueError, match="output may not overwrite an input"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=transcript_file,
            transcript_path=transcript_file,
        )


@pytest.mark.parametrize(
    "artifact_name",
    ["subtitles.vtt", "timeline.jsonld", "alignment_raw.json", "manifest.json"],
)
def test_collision_when_transcript_file_named_as_output_artifact(
    tmp_path: Path, artifact_name: str
) -> None:
    """If transcript file has the path of a target output artifact, reject with ValueError."""
    out_dir = tmp_path / "coll_tr"
    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    transcript_as_artifact = out_dir / artifact_name
    transcript_as_artifact.write_text("some words", encoding="utf-8")

    collision_pattern = "(output files already exist|output may not overwrite an input)"
    with pytest.raises(ValueError, match=collision_pattern):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=out_dir,
            transcript_path=transcript_as_artifact,
        )


# =============================================================================
# 3. Existing Output Directory Rejection Tests
# =============================================================================


@pytest.mark.parametrize(
    "existing_file",
    ["subtitles.vtt", "timeline.jsonld", "alignment_raw.json", "manifest.json"],
)
def test_reject_existing_single_artifact(tmp_path: Path, existing_file: str) -> None:
    """Pipeline must raise ValueError if ANY single generated artifact exists in output_dir."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    out_dir = tmp_path / f"out_exists_{existing_file}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / existing_file).write_text("pre-existing content", encoding="utf-8")

    with pytest.raises(
        ValueError, match="output files already exist; choose a new output directory"
    ):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=out_dir,
            transcript_text="hello world",
            aligner=make_mock_aligner(),
        )


def test_reject_all_existing_artifacts(tmp_path: Path) -> None:
    """Pipeline must raise ValueError if all generated artifacts exist."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    out_dir = tmp_path / "out_all_exist"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ("subtitles.vtt", "timeline.jsonld", "alignment_raw.json", "manifest.json"):
        (out_dir / name).write_text("pre-existing", encoding="utf-8")

    with pytest.raises(
        ValueError, match="output files already exist; choose a new output directory"
    ):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=out_dir,
            transcript_text="hello world",
            aligner=make_mock_aligner(),
        )


def test_permit_output_dir_with_unrelated_files(tmp_path: Path) -> None:
    """Non-conflicting files in output directory must NOT trigger rejection."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    out_dir = tmp_path / "out_unrelated"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "notes.txt").write_text("important user notes", encoding="utf-8")

    mock_aligner = make_mock_aligner([("hello", "hello", 0.1, 0.9)])
    manifest = run_speech_pipeline(
        audio_path=wav_path,
        output_dir=out_dir,
        transcript_text="hello",
        aligner=mock_aligner,
    )
    assert (out_dir / "manifest.json").is_file()
    assert (out_dir / "notes.txt").is_file()
    assert manifest["metrics"]["word_count"] == 1


# =============================================================================
# 4. Audio Error Handling Tests
# =============================================================================


def test_missing_audio_raises_filenotfound(tmp_path: Path) -> None:
    """Missing audio path must raise FileNotFoundError."""
    missing_wav = tmp_path / "absent.wav"
    with pytest.raises(FileNotFoundError, match="File not found"):
        run_speech_pipeline(
            audio_path=missing_wav,
            output_dir=tmp_path / "out",
            transcript_text="test",
        )


def test_directory_as_audio_path_raises_filenotfound(tmp_path: Path) -> None:
    """A directory passed as audio_path must be rejected by is_file() check."""
    audio_dir = tmp_path / "audio_dir.wav"
    audio_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="File not found"):
        run_speech_pipeline(
            audio_path=audio_dir,
            output_dir=tmp_path / "out",
            transcript_text="test",
        )


def test_zero_byte_audio_file_raises_valueerror(tmp_path: Path) -> None:
    """0-byte empty file must raise ValueError."""
    empty_wav = tmp_path / "empty.wav"
    empty_wav.write_bytes(b"")
    with pytest.raises(ValueError, match="Corrupt or invalid WAV file"):
        run_speech_pipeline(
            audio_path=empty_wav,
            output_dir=tmp_path / "out",
            transcript_text="test",
        )


def test_zero_frames_valid_header_wav_raises_valueerror(tmp_path: Path) -> None:
    """WAV with valid header but 0 audio frames must raise ValueError."""
    zero_frame_wav = tmp_path / "zero_frames.wav"
    with wave.open(str(zero_frame_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        # 0 frames written

    with pytest.raises(ValueError, match="audio file contains no audio frames"):
        run_speech_pipeline(
            audio_path=zero_frame_wav,
            output_dir=tmp_path / "out",
            transcript_text="test",
        )


def test_truncated_wav_data_raises_valueerror(tmp_path: Path) -> None:
    """WAV header specifying more frames than actual data on disk must raise ValueError."""
    trunc_wav = tmp_path / "truncated.wav"
    # Construct raw header claiming 16000 frames (32000 bytes) but provide only 100 bytes
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + 100,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        1,  # mono
        16000,
        32000,
        2,
        16,
        b"data",
        32000,  # claims 32000 bytes
    )
    trunc_wav.write_bytes(header + b"\x00" * 100)

    with pytest.raises(ValueError, match="WAV data is truncated"):
        run_speech_pipeline(
            audio_path=trunc_wav,
            output_dir=tmp_path / "out",
            transcript_text="test",
        )


def test_corrupt_riff_header_raises_valueerror(tmp_path: Path) -> None:
    """Random garbage or non-WAV format must raise ValueError."""
    corrupt_wav = tmp_path / "garbage.wav"
    corrupt_wav.write_bytes(b"NOT_A_RIFF_FILE_AT_ALL_JUST_RANDOM_DATA")
    with pytest.raises(ValueError, match="Corrupt or invalid WAV file"):
        run_speech_pipeline(
            audio_path=corrupt_wav,
            output_dir=tmp_path / "out",
            transcript_text="test",
        )


def test_stereo_wav_raises_valueerror(tmp_path: Path) -> None:
    """Stereo (2 channels) WAV must be rejected with ValueError."""
    stereo_wav = tmp_path / "stereo.wav"
    create_pcm16_wav(stereo_wav, duration_sec=1.0, channels=2)

    with pytest.raises(ValueError, match="audio must be uncompressed mono PCM16 WAV at 16000 Hz"):
        run_speech_pipeline(
            audio_path=stereo_wav,
            output_dir=tmp_path / "out",
            transcript_text="test",
        )


def test_unsupported_sample_rate_wav_raises_valueerror(tmp_path: Path) -> None:
    """44.1 kHz WAV must be rejected with ValueError."""
    rate_wav = tmp_path / "rate_44100.wav"
    create_pcm16_wav(rate_wav, duration_sec=1.0, sample_rate=44100)

    with pytest.raises(ValueError, match="audio must be uncompressed mono PCM16 WAV at 16000 Hz"):
        run_speech_pipeline(
            audio_path=rate_wav,
            output_dir=tmp_path / "out",
            transcript_text="test",
        )


def test_unsupported_sample_width_wav_raises_valueerror(tmp_path: Path) -> None:
    """8-bit PCM (1 byte width) WAV must be rejected with ValueError."""
    width_wav = tmp_path / "width_8bit.wav"
    with wave.open(str(width_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(16000)
        w.writeframes(b"\x80" * 16000)

    with pytest.raises(ValueError, match="audio must be uncompressed mono PCM16 WAV at 16000 Hz"):
        run_speech_pipeline(
            audio_path=width_wav,
            output_dir=tmp_path / "out",
            transcript_text="test",
        )


# =============================================================================
# 5. Transcript Error Handling Tests
# =============================================================================


def test_empty_transcript_string_raises_valueerror(tmp_path: Path) -> None:
    """Empty string transcript must raise ValueError."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    with pytest.raises(ValueError, match="transcript cannot be empty"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=tmp_path / "out",
            transcript_text="",
        )


def test_whitespace_only_transcript_string_raises_valueerror(tmp_path: Path) -> None:
    """Whitespace-only transcript string must raise ValueError."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    with pytest.raises(ValueError, match="transcript cannot be empty"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=tmp_path / "out",
            transcript_text="   \n\t\r  \n  ",
        )


def test_empty_transcript_file_raises_valueerror(tmp_path: Path) -> None:
    """0-byte transcript file must raise ValueError."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)
    empty_file = tmp_path / "empty_tr.txt"
    empty_file.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="transcript cannot be empty"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=tmp_path / "out",
            transcript_path=empty_file,
        )


def test_whitespace_only_transcript_file_raises_valueerror(tmp_path: Path) -> None:
    """Whitespace-only transcript file must raise ValueError."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)
    ws_file = tmp_path / "ws_tr.txt"
    ws_file.write_text("   \n\t  \r\n  ", encoding="utf-8")

    with pytest.raises(ValueError, match="transcript cannot be empty"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=tmp_path / "out",
            transcript_path=ws_file,
        )


def test_missing_transcript_path_object_raises_filenotfound(tmp_path: Path) -> None:
    """Path object pointing to non-existent file must raise FileNotFoundError."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)
    missing_file = tmp_path / "absent_transcript.txt"

    with pytest.raises(FileNotFoundError, match="Transcript file not found"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=tmp_path / "out",
            transcript_path=missing_file,
        )


def test_missing_transcript_string_path_raises_filenotfound(tmp_path: Path) -> None:
    """String filename with .txt extension pointing to missing file raises FileNotFoundError."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)
    missing_str = str(tmp_path / "does_not_exist.txt")

    with pytest.raises(FileNotFoundError, match="Transcript file not found"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=tmp_path / "out",
            transcript_path=missing_str,
        )


def test_punctuation_only_transcript_raises_valueerror(tmp_path: Path) -> None:
    """Transcript containing only punctuation/symbols must raise ValueError after normalization."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    with pytest.raises(ValueError, match="transcript contains no valid words after normalization"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=tmp_path / "out",
            transcript_text="... --- !!! ??? *** ,,, ::: ;;;",
        )


# =============================================================================
# 6. Pipeline Property & Invariant Checks
# =============================================================================


@pytest.mark.parametrize(
    ("engine", "vad_silence", "max_chunk", "chunk_pad", "match_str"),
    [
        ("invalid", 0.4, 30.0, 0.5, "unsupported engine"),
        ("mfa", 0.0, 30.0, 0.5, "vad_silence_min_sec must be positive"),
        ("mfa", -0.1, 30.0, 0.5, "vad_silence_min_sec must be positive"),
        ("mfa", 0.4, 0.0, 0.5, "max_chunk_sec must be positive"),
        ("mfa", 0.4, -5.0, 0.5, "max_chunk_sec must be positive"),
        ("mfa", 0.4, 30.0, -0.01, "chunk_padding_sec must be nonnegative"),
    ],
)
def test_pipeline_parameter_boundary_guards(
    tmp_path: Path,
    engine: str,
    vad_silence: float,
    max_chunk: float,
    chunk_pad: float,
    match_str: str,
) -> None:
    """Scalar thresholds and engine strings must satisfy boundary contracts."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    with pytest.raises(ValueError, match=match_str):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=tmp_path / "out",
            transcript_text="hello world",
            engine=engine,  # type: ignore[arg-type]
            vad_silence_min_sec=vad_silence,
            max_chunk_sec=max_chunk,
            chunk_padding_sec=chunk_pad,
        )


def test_monotonicity_and_hash_integrity_property(tmp_path: Path) -> None:
    """All output tokens must be strictly monotonic and manifest hashes match disk files."""
    wav_path = tmp_path / "audio_monotonic.wav"
    out_dir = tmp_path / "out_monotonic"
    create_pcm16_wav(wav_path, duration_sec=5.0)

    # 5 words across 5 seconds
    words_spec = [
        ("first", "first", 0.2, 0.9),
        ("second", "second", 1.1, 1.8),
        ("third", "third", 2.0, 2.7),
        ("fourth", "fourth", 3.1, 3.8),
        ("fifth", "fifth", 4.0, 4.8),
    ]
    mock_aligner = make_mock_aligner(words_spec)

    manifest = run_speech_pipeline(
        audio_path=wav_path,
        output_dir=out_dir,
        transcript_text="first second third fourth fifth",
        aligner=mock_aligner,
    )

    # Read generated artifacts
    vtt_path = out_dir / "subtitles.vtt"
    jsonld_path = out_dir / "timeline.jsonld"
    raw_path = out_dir / "alignment_raw.json"
    manifest_path = out_dir / "manifest.json"

    assert vtt_path.is_file()
    assert jsonld_path.is_file()
    assert raw_path.is_file()
    assert manifest_path.is_file()

    # Verify SHA-256 integrity
    for p in (vtt_path, jsonld_path, raw_path):
        expected_hash = manifest["outputs"][p.name]["sha256"]
        actual_hash = hashlib.sha256(p.read_bytes()).hexdigest()
        assert expected_hash == actual_hash, f"Hash mismatch on {p.name}"

    # Verify input audio SHA-256
    expected_audio_hash = manifest["inputs"]["audio"]["sha256"]
    actual_audio_hash = hashlib.sha256(wav_path.read_bytes()).hexdigest()
    assert expected_audio_hash == actual_audio_hash

    # Verify monotonicity in alignment_raw.json
    raw_data = json.loads(raw_path.read_text(encoding="utf-8"))
    words = raw_data["words"]
    assert len(words) == 5
    for i in range(len(words) - 1):
        assert words[i]["start"] < words[i]["end"], f"Word {i} duration inverted"
        assert words[i]["start"] <= words[i + 1]["start"], (
            f"Word {i} to {i + 1} onset not monotonic"
        )


# =============================================================================
# 7. CLI Subcommand Contract Stress Tests
# =============================================================================


def test_cli_align_speech_missing_audio_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """CLI align-speech with missing WAV must exit 2 with clean error message."""
    exit_code = main(
        [
            "align-speech",
            str(tmp_path / "not_there.wav"),
            "-o",
            str(tmp_path / "out"),
            "--transcript-text",
            "sample text",
        ]
    )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "error: File not found" in captured.err
    assert "Traceback" not in captured.err


def test_cli_align_speech_empty_transcript_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """CLI align-speech with empty transcript must exit 2 with clean error message."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    exit_code = main(
        [
            "align-speech",
            str(wav_path),
            "-o",
            str(tmp_path / "out"),
            "--transcript-text",
            "   ",
        ]
    )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "error: transcript cannot be empty" in captured.err
    assert "Traceback" not in captured.err


def test_cli_align_speech_missing_transcript_file_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """CLI align-speech with missing transcript file must exit 2 with clean error message."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    exit_code = main(
        [
            "align-speech",
            str(wav_path),
            "-o",
            str(tmp_path / "out"),
            "--transcript-file",
            str(tmp_path / "missing.txt"),
        ]
    )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "error: Transcript file not found" in captured.err
    assert "Traceback" not in captured.err


def test_cli_align_speech_output_collision_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """CLI align-speech with output matching input WAV must exit 2."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)

    exit_code = main(
        [
            "align-speech",
            str(wav_path),
            "-o",
            str(wav_path),
            "--transcript-text",
            "hello",
        ]
    )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "error: output may not overwrite an input" in captured.err
    assert "Traceback" not in captured.err


def test_cli_align_speech_existing_output_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """CLI align-speech to directory with existing artifact must exit 2."""
    wav_path = tmp_path / "audio.wav"
    create_pcm16_wav(wav_path, duration_sec=1.0)
    out_dir = tmp_path / "existing_cli_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text("old", encoding="utf-8")

    exit_code = main(
        [
            "align-speech",
            str(wav_path),
            "-o",
            str(out_dir),
            "--transcript-text",
            "hello",
        ]
    )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "error: output files already exist; choose a new output directory" in captured.err
    assert "Traceback" not in captured.err
