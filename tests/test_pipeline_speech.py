"""Unit and integration tests for end-to-end speech alignment pipeline and CLI subcommands."""

import json
import subprocess
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from subtitle_workbench.cli import main
from subtitle_workbench.demo import generate as generate_demo
from subtitle_workbench.models import ASRSegment, WordToken
from subtitle_workbench.pipeline import (
    get_duration,
    normalize_transcript,
    run_speech_pipeline,
)


def create_test_wav(
    path: Path,
    duration_sec: float = 2.0,
    sample_rate: int = 16000,
) -> None:
    """Create a valid PCM16 mono WAV file with a synthetic 440 Hz tone."""
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.linspace(0, duration_sec, int(round(sample_rate * duration_sec)), endpoint=False)
    samples = (np.sin(2 * np.pi * 440 * t) * 16384).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())


def make_mock_transcriber(words_spec: list[tuple[str, str, float, float]] | None = None):
    """Create a mock WhisperTranscriber with deterministic segments and unload tracking."""
    if words_spec is None:
        words_spec = [
            ("hello", "hello", 0.1, 0.9),
            ("world", "world", 1.0, 1.9),
        ]
    word_tokens = [
        WordToken(
            id=f"w_{i}",
            text=text,
            normalized=norm,
            start=start,
            end=end,
            confidence=0.95,
            char_start=0,
            char_end=len(text),
        )
        for i, (text, norm, start, end) in enumerate(words_spec)
    ]
    seg = ASRSegment(
        id="seg_0",
        start=words_spec[0][2],
        end=words_spec[-1][3],
        text=" ".join(w[0] for w in words_spec),
        words=word_tokens,
    )
    mock = MagicMock()
    mock.transcribe.return_value = [seg]
    mock.unload = MagicMock()
    return mock


def make_mock_aligner(words_spec: list[tuple[str, str, float, float]] | None = None):
    """Create a mock ForcedAligner returning reconciled WordTokens."""
    if words_spec is None:
        words_spec = [
            ("hello", "hello", 0.12, 0.88),
            ("world", "world", 1.05, 1.85),
        ]
    word_tokens = [
        WordToken(
            id=f"w_{i}",
            text=text,
            normalized=norm,
            start=start,
            end=end,
            confidence=0.92,
            char_start=0,
            char_end=len(text),
        )
        for i, (text, norm, start, end) in enumerate(words_spec)
    ]
    mock = MagicMock()
    mock.align_chunks.return_value = word_tokens
    return mock


# ============================================================================
# Helper and Contract Tests
# ============================================================================


def test_get_duration_helper(tmp_path: Path) -> None:
    """Verify get_duration reads WAV duration accurately."""
    wav_path = tmp_path / "audio_3s.wav"
    create_test_wav(wav_path, duration_sec=3.0)
    dur = get_duration(wav_path)
    assert abs(dur - 3.0) < 1e-4


def test_normalize_transcript_helper() -> None:
    """Verify normalize_transcript returns TokenSpan list with character offsets."""
    text = "Don't stop 42 tests!"
    spans = normalize_transcript(text)
    assert len(spans) >= 4
    for span in spans:
        assert text[span.char_start : span.char_end] == span.token


# ============================================================================
# Pipeline End-to-End & Lifecycle Tests
# ============================================================================


def test_run_speech_pipeline_mocked_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify all 7 stages execute with mock transcriber/aligner and emit all 4 artifacts."""
    wav_path = tmp_path / "input.wav"
    out_dir = tmp_path / "output_speech"
    create_test_wav(wav_path, duration_sec=2.0)

    # Mock extract_vad_silences for deterministic offline CPU execution
    monkeypatch.setattr(
        "subtitle_workbench.pipeline.extract_vad_silences",
        lambda *args, **kwargs: [(0.0, 0.1), (1.9, 2.0)],
    )

    mock_transcriber = make_mock_transcriber()
    mock_aligner = make_mock_aligner()

    manifest = run_speech_pipeline(
        audio_path=wav_path,
        output_dir=out_dir,
        engine="mfa",
        transcriber=mock_transcriber,
        aligner=mock_aligner,
    )

    # Stage 2 VRAM cleanup verification
    mock_transcriber.transcribe.assert_called_once()
    mock_transcriber.unload.assert_called_once()

    # Stage 5 & 6 Aligner invocation
    mock_aligner.align_chunks.assert_called_once()

    # Stage 7 Artifacts verification on disk
    assert (out_dir / "subtitles.vtt").is_file()
    assert (out_dir / "timeline.jsonld").is_file()
    assert (out_dir / "alignment_raw.json").is_file()
    assert (out_dir / "manifest.json").is_file()

    # Validate subtitles.vtt content
    vtt_text = (out_dir / "subtitles.vtt").read_text(encoding="utf-8")
    assert vtt_text.startswith("WEBVTT\n\n")
    assert "<c.word>" in vtt_text
    assert "hello" in vtt_text
    assert "world" in vtt_text

    # Validate timeline.jsonld content
    jsonld_data = json.loads((out_dir / "timeline.jsonld").read_text(encoding="utf-8"))
    assert jsonld_data["@type"] == "VideoObject"
    assert len(jsonld_data["hasPart"]) == 2
    assert jsonld_data["hasPart"][0]["name"] == "hello"

    # Validate alignment_raw.json content
    raw_data = json.loads((out_dir / "alignment_raw.json").read_text(encoding="utf-8"))
    assert raw_data["schema_version"] == 1
    assert raw_data["alignment_method"] == "mfa"
    assert raw_data["summary"]["total_words"] == 2

    # Validate returned manifest
    assert manifest["schema_version"] == 1
    assert manifest["tool"]["name"] == "local-subtitle-workbench"
    assert "inputs" in manifest
    assert "outputs" in manifest
    assert manifest["metrics"]["word_count"] == 2
    assert abs(manifest["metrics"]["audio_duration_seconds"] - 2.0) < 1e-4
    assert manifest["metrics"]["chunk_count"] >= 1


def test_run_speech_pipeline_with_explicit_transcript_string(tmp_path: Path) -> None:
    """Scenario A: a known transcript is anchored with ASR output, then force-aligned."""
    wav_path = tmp_path / "audio.wav"
    out_dir = tmp_path / "output_transcript_str"
    create_test_wav(wav_path, duration_sec=2.0)

    mock_aligner = make_mock_aligner(
        [
            ("explicit", "explicit", 0.2, 0.9),
            ("transcript", "transcript", 1.0, 1.8),
        ]
    )

    manifest = run_speech_pipeline(
        audio_path=wav_path,
        output_dir=out_dir,
        transcript_text="explicit transcript",
        aligner=mock_aligner,
    )

    mock_aligner.align_chunks.assert_called_once()
    assert (out_dir / "manifest.json").is_file()
    assert manifest["metrics"]["word_count"] == 2
    assert manifest["metrics"]["scenario"] == "A"
    assert manifest["metrics"]["anchoring"]["n_reference_words"] == 2

    # Whisper is never skipped: it supplies the anchors in scenario A
    from conftest import FakeWhisperTranscriber

    assert FakeWhisperTranscriber.instances[-1].transcribe_calls == 1
    assert FakeWhisperTranscriber.instances[-1].unload_calls == 1


def test_run_speech_pipeline_with_explicit_transcript_file(tmp_path: Path) -> None:
    """Verify pipeline reads transcript from disk file path."""
    wav_path = tmp_path / "audio.wav"
    transcript_file = tmp_path / "input_transcript.txt"
    out_dir = tmp_path / "output_transcript_file"
    create_test_wav(wav_path, duration_sec=2.0)
    transcript_file.write_text("audio testing workflow", encoding="utf-8")

    mock_aligner = make_mock_aligner(
        [
            ("audio", "audio", 0.1, 0.6),
            ("testing", "testing", 0.7, 1.2),
            ("workflow", "workflow", 1.3, 1.9),
        ]
    )

    manifest = run_speech_pipeline(
        audio_path=wav_path,
        output_dir=out_dir,
        transcript_path=transcript_file,
        aligner=mock_aligner,
    )

    assert (out_dir / "manifest.json").is_file()
    assert manifest["metrics"]["word_count"] == 3


def test_vram_lifecycle_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify transcriber.unload() is always invoked even if transcription throws an error."""
    wav_path = tmp_path / "audio.wav"
    out_dir = tmp_path / "output_vram_err"
    create_test_wav(wav_path, duration_sec=2.0)

    monkeypatch.setattr(
        "subtitle_workbench.pipeline.extract_vad_silences",
        lambda *args, **kwargs: [],
    )

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe.side_effect = RuntimeError("VRAM allocation failure simulated")
    mock_transcriber.unload = MagicMock()

    with pytest.raises(RuntimeError, match="VRAM allocation failure simulated"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=out_dir,
            transcriber=mock_transcriber,
        )

    mock_transcriber.unload.assert_called_once()
    assert not (out_dir / "manifest.json").exists()


# ============================================================================
# Collision & Overwrite Protection Tests
# ============================================================================


def test_output_overwrite_protection(tmp_path: Path) -> None:
    """Verify pipeline rejects execution when output directory already contains artifacts."""
    wav_path = tmp_path / "audio.wav"
    out_dir = tmp_path / "output_protect"
    create_test_wav(wav_path, duration_sec=2.0)

    mock_aligner = make_mock_aligner()

    # First run succeeds
    run_speech_pipeline(
        audio_path=wav_path,
        output_dir=out_dir,
        transcript_text="hello world",
        aligner=mock_aligner,
    )
    assert (out_dir / "manifest.json").is_file()

    # Second run to same directory must raise ValueError
    with pytest.raises(
        ValueError, match="output files already exist; choose a new output directory"
    ):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=out_dir,
            transcript_text="hello world",
            aligner=mock_aligner,
        )


def test_output_collision_with_input_audio(tmp_path: Path) -> None:
    """Verify pipeline rejects output resolving to input WAV file."""
    wav_path = tmp_path / "audio.wav"
    create_test_wav(wav_path, duration_sec=2.0)

    with pytest.raises(ValueError, match="output may not overwrite an input"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=wav_path,
            transcript_text="hello world",
        )


def test_output_collision_with_input_transcript(tmp_path: Path) -> None:
    """Verify pipeline rejects output resolving to input transcript file."""
    wav_path = tmp_path / "audio.wav"
    transcript_file = tmp_path / "transcript.txt"
    create_test_wav(wav_path, duration_sec=2.0)
    transcript_file.write_text("sample transcript", encoding="utf-8")

    with pytest.raises(ValueError, match="output may not overwrite an input"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=transcript_file,
            transcript_path=transcript_file,
        )


# ============================================================================
# Error Handling & Boundary Condition Tests
# ============================================================================


def test_missing_audio_file(tmp_path: Path) -> None:
    """Verify missing audio file raises FileNotFoundError."""
    missing_wav = tmp_path / "nonexistent.wav"
    with pytest.raises(FileNotFoundError, match="File not found"):
        run_speech_pipeline(
            audio_path=missing_wav,
            output_dir=tmp_path / "out",
            transcript_text="hello",
        )


def test_corrupt_audio_file(tmp_path: Path) -> None:
    """Verify invalid or corrupt WAV file raises ValueError."""
    corrupt_wav = tmp_path / "corrupt.wav"
    corrupt_wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt invalid audio data bytes")

    with pytest.raises(ValueError, match="Corrupt or invalid WAV file"):
        run_speech_pipeline(
            audio_path=corrupt_wav,
            output_dir=tmp_path / "out",
            transcript_text="hello",
        )


def test_missing_transcript_file(tmp_path: Path) -> None:
    """Verify missing explicit transcript file raises FileNotFoundError."""
    wav_path = tmp_path / "audio.wav"
    create_test_wav(wav_path, duration_sec=2.0)
    missing_transcript = tmp_path / "missing_transcript.txt"

    with pytest.raises(FileNotFoundError, match="Transcript file not found"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=tmp_path / "out",
            transcript_path=missing_transcript,
        )


def test_empty_transcript_string(tmp_path: Path) -> None:
    """Verify empty or whitespace transcript raises ValueError."""
    wav_path = tmp_path / "audio.wav"
    create_test_wav(wav_path, duration_sec=2.0)

    with pytest.raises(ValueError, match="transcript cannot be empty"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=tmp_path / "out",
            transcript_text="   \n\t  ",
        )


def test_transcript_no_words_after_norm(tmp_path: Path) -> None:
    """Verify transcript without words after normalization raises ValueError."""
    wav_path = tmp_path / "audio.wav"
    create_test_wav(wav_path, duration_sec=2.0)

    with pytest.raises(ValueError, match="transcript contains no valid words after normalization"):
        run_speech_pipeline(
            audio_path=wav_path,
            output_dir=tmp_path / "out",
            transcript_text="... --- !!! ;;;",
        )


def test_invalid_pipeline_parameters(tmp_path: Path) -> None:
    """Verify scalar threshold validation raises ValueError on non-positive values."""
    wav_path = tmp_path / "audio.wav"
    create_test_wav(wav_path, duration_sec=2.0)

    with pytest.raises(ValueError, match="unsupported engine"):
        run_speech_pipeline(wav_path, tmp_path / "out", engine="invalid_engine")

    with pytest.raises(ValueError, match="vad_silence_min_sec must be positive"):
        run_speech_pipeline(wav_path, tmp_path / "out", vad_silence_min_sec=-0.5)

    with pytest.raises(ValueError, match="max_chunk_sec must be positive"):
        run_speech_pipeline(wav_path, tmp_path / "out", max_chunk_sec=0.0)

    with pytest.raises(ValueError, match="chunk_padding_sec must be nonnegative"):
        run_speech_pipeline(wav_path, tmp_path / "out", chunk_padding_sec=-0.1)


# ============================================================================
# CLI Integration Tests
# ============================================================================


def test_cli_align_speech_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verify CLI align-speech subcommand succeeds with exit code 0 and prints JSON metrics."""
    wav_path = tmp_path / "speech.wav"
    out_dir = tmp_path / "cli_speech_out"
    create_test_wav(wav_path, duration_sec=2.0)

    mock_aligner = make_mock_aligner()
    monkeypatch.setattr(
        "subtitle_workbench.pipeline.ForcedAligner",
        lambda: mock_aligner,
    )

    exit_code = main(
        [
            "align-speech",
            str(wav_path),
            "-o",
            str(out_dir),
            "--transcript-text",
            "hello world",
            "--engine",
            "ctc",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    metrics = json.loads(captured.out)
    assert metrics["word_count"] == 2
    assert (out_dir / "manifest.json").is_file()


def test_cli_align_speech_invalid_audio_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Verify CLI align-speech returns exit code 2 on invalid audio and emits error to stderr."""
    exit_code = main(
        [
            "align-speech",
            str(tmp_path / "nonexistent.wav"),
            "-o",
            str(tmp_path / "out"),
        ]
    )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_cli_align_dtw_subcommand(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Verify CLI align-dtw subcommand succeeds and emits DTW metrics."""
    fixture_dir = tmp_path / "dtw_input"
    generate_demo(fixture_dir)
    out_dir = tmp_path / "cli_dtw_out"

    exit_code = main(
        [
            "align-dtw",
            str(fixture_dir / "reference.wav"),
            str(fixture_dir / "target.wav"),
            str(fixture_dir / "cues.json"),
            "-o",
            str(out_dir),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    metrics = json.loads(captured.out)
    assert metrics["cue_count"] == 6
    assert (out_dir / "manifest.json").is_file()


def test_cli_legacy_root_flags_backward_compatibility(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Verify legacy root flags without subcommand preserve backward compatibility."""
    fixture_dir = tmp_path / "legacy_input"
    generate_demo(fixture_dir)
    out_dir = tmp_path / "cli_legacy_out"

    exit_code = main(
        [
            "--reference",
            str(fixture_dir / "reference.wav"),
            "--target",
            str(fixture_dir / "target.wav"),
            "--cues",
            str(fixture_dir / "cues.json"),
            "-o",
            str(out_dir),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    metrics = json.loads(captured.out)
    assert metrics["cue_count"] == 6


def test_cli_missing_required_arguments_exit_2(capsys: pytest.CaptureFixture) -> None:
    """Verify CLI returns exit code 2 when required arguments are omitted."""
    # No arguments at all
    exit_code = main([])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "Traceback" not in captured.err

    # Partial arguments
    exit_code = main(["--reference", "ref.wav"])
    assert exit_code == 2


def test_cli_subprocess_invocation(tmp_path: Path) -> None:
    """Verify python -m subtitle_workbench subprocess execution contract."""
    fixture_dir = tmp_path / "subp_in"
    generate_demo(fixture_dir)
    out_dir = tmp_path / "subp_out"

    cmd = [
        sys.executable,
        "-m",
        "subtitle_workbench",
        "align-dtw",
        str(fixture_dir / "reference.wav"),
        str(fixture_dir / "target.wav"),
        str(fixture_dir / "cues.json"),
        "-o",
        str(out_dir),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["cue_count"] == 6
