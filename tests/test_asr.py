"""Unit, contract, and error-handling tests for ASR and VAD modules."""

import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from subtitle_workbench import (
    ASRError,
    ASRInferenceError,
    ASRSegment,
    AudioFormatError,
    VRAMAllocationError,
    WhisperTranscriber,
    WordToken,
    extract_vad_silences,
)


def create_test_wav(
    path: Path,
    sample_rate: int = 16000,
    channels: int = 1,
    sampwidth: int = 2,
    duration_sec: float = 1.0,
    amplitude: float = 0.5,
) -> Path:
    """Create a synthetic PCM WAV file for testing."""
    n_samples = max(1, int(sample_rate * duration_sec))
    t = np.linspace(0, duration_sec, n_samples, endpoint=False)
    raw = (np.sin(2 * np.pi * 440 * t) * amplitude * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sampwidth)
        wav.setframerate(sample_rate)
        wav.writeframes(raw.tobytes())
    return path


class DummyWord:
    def __init__(self, word: str, start: float, end: float, probability: float = 0.95):
        self.word = word
        self.start = start
        self.end = end
        self.probability = probability


class DummySegment:
    def __init__(
        self,
        id: int,
        start: float,
        end: float,
        text: str,
        words: list[DummyWord],
    ):
        self.id = id
        self.start = start
        self.end = end
        self.text = text
        self.words = words


class DummyTranscriptionInfo:
    def __init__(
        self,
        language: str = "en",
        language_probability: float = 0.99,
        duration: float = 4.5,
    ):
        self.language = language
        self.language_probability = language_probability
        self.duration = duration


class DummyWhisperBackend:
    """Deterministic offline Faster-Whisper mock backend."""

    def __init__(
        self,
        model_size_or_path: str = "large-v3",
        device: str = "cpu",
        compute_type: str = "int8",
        **kwargs,
    ):
        self.model_size_or_path = model_size_or_path
        self.device = device
        self.compute_type = compute_type
        self.kwargs = kwargs
        self.transcribe_called = False
        self.transcribe_args = {}

    def transcribe(
        self,
        audio: str,
        language: str = "en",
        word_timestamps: bool = True,
        vad_filter: bool = True,
        vad_parameters: dict | None = None,
        **kwargs,
    ):
        self.transcribe_called = True
        self.transcribe_args = {
            "audio": audio,
            "language": language,
            "word_timestamps": word_timestamps,
            "vad_filter": vad_filter,
            "vad_parameters": vad_parameters,
            **kwargs,
        }
        segments = [
            DummySegment(
                id=0,
                start=0.5,
                end=2.0,
                text="Hello world don't worry",
                words=[
                    DummyWord(" Hello", 0.5, 0.9, 0.98),
                    DummyWord(" world", 0.95, 1.4, 0.95),
                    DummyWord(" don't", 1.45, 1.8, 0.92),
                    DummyWord(" worry", 1.85, 2.0, 0.91),
                ],
            ),
            DummySegment(
                id=1,
                start=2.5,
                end=4.0,
                text="Second segment here",
                words=[
                    DummyWord(" Second", 2.5, 3.0, 0.97),
                    DummyWord(" segment", 3.05, 3.6, 0.94),
                    DummyWord(" here", 3.65, 4.0, 0.96),
                ],
            ),
        ]
        info = DummyTranscriptionInfo(language=language, duration=4.5)
        return iter(segments), info


# ============================================================================
# 1. Exception Hierarchy Tests
# ============================================================================


def test_exception_hierarchy():
    """Verify ECC Error Handling exception inheritance."""
    assert issubclass(AudioFormatError, ASRError)
    assert issubclass(ASRInferenceError, ASRError)
    assert issubclass(VRAMAllocationError, ASRError)
    assert issubclass(ASRError, Exception)

    # Polymorphic catch test
    for exc_cls in (AudioFormatError, ASRInferenceError, VRAMAllocationError):
        try:
            raise exc_cls("test error")
        except ASRError as err:
            assert "test error" in str(err)


# ============================================================================
# 2. Hardware Bounds & Device / Compute Type Auto-Selection Tests
# ============================================================================


def test_device_and_compute_type_cuda_selection():
    """When CTranslate2 can use CUDA, auto-select cuda and int8_float16."""
    with patch("subtitle_workbench.asr.whisper_cuda_available", return_value=True):
        transcriber = WhisperTranscriber(
            model_instance=DummyWhisperBackend(),
            device=None,
            compute_type=None,
        )
        assert transcriber.device == "cuda"
        assert transcriber.compute_type == "int8_float16"


def test_device_and_compute_type_cpu_selection():
    """When CUDA is unavailable, auto-select cpu and int8."""
    with patch("subtitle_workbench.asr.whisper_cuda_available", return_value=False):
        transcriber = WhisperTranscriber(
            model_instance=DummyWhisperBackend(),
            device=None,
            compute_type=None,
        )
        assert transcriber.device == "cpu"
        assert transcriber.compute_type == "int8"


def test_device_and_compute_type_explicit_override():
    """Explicit device and compute_type parameters must be preserved."""
    transcriber = WhisperTranscriber(
        model_instance=DummyWhisperBackend(),
        device="cpu",
        compute_type="float32",
    )
    assert transcriber.device == "cpu"
    assert transcriber.compute_type == "float32"


# ============================================================================
# 3. Deterministic VRAM Lifecycle & Unload Tests
# ============================================================================


def test_vram_lifecycle_unload():
    """Unload must clear model reference and invoke gc and empty_cache."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True

    dummy = DummyWhisperBackend()
    transcriber = WhisperTranscriber(model_instance=dummy)
    assert transcriber.is_loaded

    with patch.dict(sys.modules, {"torch": mock_torch}), patch("gc.collect") as mock_gc:
        transcriber.unload()
        assert not transcriber.is_loaded
        assert transcriber._model is None
        mock_gc.assert_called_once()
        mock_torch.cuda.empty_cache.assert_called_once()


def test_vram_lifecycle_idempotent_unload():
    """Calling unload multiple times should be safe and idempotent."""
    transcriber = WhisperTranscriber(model_instance=DummyWhisperBackend())
    transcriber.unload()
    assert not transcriber.is_loaded
    # Second call should not raise
    transcriber.unload()
    assert not transcriber.is_loaded


def test_vram_lifecycle_context_manager():
    """Context manager must guarantee unload on exit."""
    dummy = DummyWhisperBackend()
    with WhisperTranscriber(model_instance=dummy) as transcriber:
        assert transcriber.is_loaded
    assert not transcriber.is_loaded


# ============================================================================
# 4. Input Validation & AudioFormatError Tests
# ============================================================================


def test_transcribe_nonexistent_file(tmp_path):
    """Missing audio file must raise AudioFormatError."""
    transcriber = WhisperTranscriber(model_instance=DummyWhisperBackend())
    bad_path = tmp_path / "nonexistent.wav"
    with pytest.raises(AudioFormatError, match="not exist|not found"):
        transcriber.transcribe(bad_path)


def test_transcribe_invalid_wav_content(tmp_path):
    """Corrupt or non-WAV data must raise AudioFormatError."""
    transcriber = WhisperTranscriber(model_instance=DummyWhisperBackend())
    bad_path = tmp_path / "corrupt.wav"
    bad_path.write_bytes(b"NOT A REAL WAV FILE HEADER")
    with pytest.raises(AudioFormatError, match="Failed to read|Corrupt|uncompressed mono PCM16"):
        transcriber.transcribe(bad_path)


@pytest.mark.parametrize(
    "rate,channels,width",
    [
        (8000, 1, 2),  # Unsupported sample rate
        (44100, 1, 2),  # Unsupported sample rate
        (16000, 2, 2),  # Stereo instead of mono
        (16000, 1, 1),  # 8-bit PCM instead of 16-bit
        (16000, 1, 3),  # 24-bit PCM instead of 16-bit
    ],
)
def test_transcribe_unsupported_audio_format(tmp_path, rate, channels, width):
    """Invalid sampling rate, channels, or bit depth must raise AudioFormatError."""
    transcriber = WhisperTranscriber(model_instance=DummyWhisperBackend())
    bad_path = tmp_path / f"bad_{rate}_{channels}_{width}.wav"
    create_test_wav(bad_path, sample_rate=rate, channels=channels, sampwidth=width)
    with pytest.raises(AudioFormatError, match="must be uncompressed mono PCM16 WAV at 16000 Hz"):
        transcriber.transcribe(bad_path)


def test_transcribe_truncated_wav(tmp_path):
    """Truncated WAV file must raise AudioFormatError."""
    transcriber = WhisperTranscriber(model_instance=DummyWhisperBackend())
    path = tmp_path / "truncated.wav"
    create_test_wav(path, duration_sec=1.0)
    raw = path.read_bytes()
    path.write_bytes(raw[:-100])  # Lop off 100 bytes of audio data
    with pytest.raises(AudioFormatError, match="truncated|Corrupt"):
        transcriber.transcribe(path)


# ============================================================================
# 5. Faster-Whisper Inference & Contract Tests
# ============================================================================


def test_transcribe_contract_and_normalization(tmp_path):
    """Verify transcription produces valid ASRSegments and WordTokens with normalized forms."""
    audio_path = tmp_path / "test.wav"
    create_test_wav(audio_path, duration_sec=4.5)

    backend = DummyWhisperBackend()
    transcriber = WhisperTranscriber(model_instance=backend)

    segments = transcriber.transcribe(audio_path, language="en")

    assert backend.transcribe_called
    assert backend.transcribe_args["word_timestamps"] is True
    assert backend.transcribe_args["vad_filter"] is True
    assert backend.transcribe_args["vad_parameters"] == {"min_silence_duration_ms": 400}

    assert isinstance(segments, list)
    assert len(segments) == 2

    # Segment 0 verification
    seg0 = segments[0]
    assert isinstance(seg0, ASRSegment)
    assert seg0.id == "seg_0"
    assert seg0.start == 0.5
    assert seg0.end == 2.0
    assert "Hello" in seg0.text
    assert len(seg0.words) == 4

    # WordToken contracts
    w0 = seg0.words[0]
    assert isinstance(w0, WordToken)
    assert w0.id == "seg_0_w_0"
    assert w0.text == "Hello"
    assert w0.normalized == "hello"
    assert 0.0 <= w0.start < w0.end <= 2.0
    assert 0.0 <= w0.confidence <= 1.0

    # Contraction normalization verification ("don't" -> "do not")
    w2 = seg0.words[2]
    assert w2.text == "don't"
    assert w2.normalized == "do not"

    # Segment 1 verification
    seg1 = segments[1]
    assert isinstance(seg1, ASRSegment)
    assert seg1.id == "seg_1"
    assert seg1.start == 2.5
    assert seg1.end == 4.0
    assert len(seg1.words) == 3


def test_transcribe_word_timestamp_monotonicity(tmp_path):
    """Ensure WordTokens within segments strictly maintain 0 <= start < end."""
    audio_path = tmp_path / "test_mono.wav"
    create_test_wav(audio_path, duration_sec=4.5)

    # Create dummy segment with degenerate word timestamps (Whisper edge case)
    class DegenerateBackend:
        def transcribe(self, *args, **kwargs):
            segments = [
                DummySegment(
                    id=0,
                    start=1.0,
                    end=2.0,
                    text="word zero duration",
                    words=[
                        # Degenerate: start == end
                        DummyWord("word", 1.0, 1.0, 0.9),
                        # Normal
                        DummyWord("duration", 1.1, 1.5, 0.9),
                    ],
                )
            ]
            info = DummyTranscriptionInfo()
            return iter(segments), info

    transcriber = WhisperTranscriber(model_instance=DegenerateBackend())
    segments = transcriber.transcribe(audio_path)
    assert len(segments) == 1
    # Degenerate timestamp should be fixed to ensure start < end
    w0 = segments[0].words[0]
    assert w0.start < w0.end


def test_transcribe_vram_allocation_error(tmp_path):
    """CUDA OOM error during transcription must be caught and raised as VRAMAllocationError."""
    audio_path = tmp_path / "test_oom.wav"
    create_test_wav(audio_path)

    class OOMBackend:
        def transcribe(self, *args, **kwargs):
            raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")

    transcriber = WhisperTranscriber(model_instance=OOMBackend())
    with pytest.raises(VRAMAllocationError, match="CUDA VRAM allocation failed"):
        transcriber.transcribe(audio_path)


def test_transcribe_general_inference_error(tmp_path):
    """General model failure during transcription must raise ASRInferenceError."""
    audio_path = tmp_path / "test_inf_err.wav"
    create_test_wav(audio_path)

    class BrokenBackend:
        def transcribe(self, *args, **kwargs):
            raise RuntimeError("Internal CTranslate2 inference crash")

    transcriber = WhisperTranscriber(model_instance=BrokenBackend())
    with pytest.raises(ASRInferenceError, match="ASR transcription failed"):
        transcriber.transcribe(audio_path)


def test_transcriber_missing_faster_whisper(tmp_path):
    """When faster-whisper is not installed and model_instance is None, raise ASRInferenceError."""
    audio_path = tmp_path / "test.wav"
    create_test_wav(audio_path)

    with patch.dict(sys.modules, {"faster_whisper": None}):
        transcriber = WhisperTranscriber()
        with pytest.raises(ASRInferenceError, match="faster-whisper is not installed"):
            transcriber.transcribe(audio_path)


# ============================================================================
# 6. VAD Silence Extraction Tests (extract_vad_silences)
# ============================================================================


def test_extract_vad_silences_format_validation(tmp_path):
    """Invalid audio inputs must raise AudioFormatError in extract_vad_silences."""
    bad_path = tmp_path / "nonexistent.wav"
    with pytest.raises(AudioFormatError):
        extract_vad_silences(bad_path)

    corrupt_path = tmp_path / "corrupt.wav"
    corrupt_path.write_bytes(b"garbage")
    with pytest.raises(AudioFormatError):
        extract_vad_silences(corrupt_path)


def test_extract_vad_silences_with_backend(tmp_path):
    """extract_vad_silences properly extracts leading, interior, and trailing pauses."""
    audio_path = tmp_path / "speech_intervals.wav"
    # 5.0 seconds total audio
    create_test_wav(audio_path, duration_sec=5.0)

    # Speech between 1.0-2.0s and 3.0-4.0s
    # Sample rate is 16000:
    # 1.0s = 16000, 2.0s = 32000
    # 3.0s = 48000, 4.0s = 64000
    def mock_vad_backend(samples, sample_rate=16000, min_silence_duration_ms=400):
        return [
            {"start": 16000, "end": 32000},
            {"start": 48000, "end": 64000},
        ]

    silences = extract_vad_silences(
        audio_path,
        min_silence_duration_ms=400,
        vad_backend=mock_vad_backend,
    )

    # Expected silences:
    # 1. Leading silence: [0.0, 1.0] (1000ms >= 400ms)
    # 2. Interior pause: [2.0, 3.0] (1000ms >= 400ms)
    # 3. Trailing silence: [4.0, 5.0] (1000ms >= 400ms)
    assert len(silences) == 3
    assert silences[0] == (0.0, 1.0)
    assert silences[1] == (2.0, 3.0)
    assert silences[2] == (4.0, 5.0)


def test_extract_vad_silences_short_pause_filtering(tmp_path):
    """Pauses shorter than min_silence_duration_ms must be filtered out."""
    audio_path = tmp_path / "short_pause.wav"
    create_test_wav(audio_path, duration_sec=3.0)

    # Speech 0.0-1.0s, speech 1.2-3.0s (pause is 0.2s = 200ms < 400ms)
    def mock_vad_backend(samples, sample_rate=16000, min_silence_duration_ms=400):
        return [
            {"start": 0, "end": 16000},
            {"start": 19200, "end": 48000},
        ]

    silences = extract_vad_silences(
        audio_path,
        min_silence_duration_ms=400,
        vad_backend=mock_vad_backend,
    )
    # The 200ms pause is filtered out, no leading or trailing silence
    assert len(silences) == 0


def test_extract_vad_silences_all_silent(tmp_path):
    """When no speech is detected, the entire audio duration is returned as silence."""
    audio_path = tmp_path / "silent.wav"
    create_test_wav(audio_path, duration_sec=4.0, amplitude=0.001)

    def mock_vad_backend(samples, sample_rate=16000, min_silence_duration_ms=400):
        return []

    silences = extract_vad_silences(
        audio_path,
        min_silence_duration_ms=400,
        vad_backend=mock_vad_backend,
    )
    assert len(silences) == 1
    assert silences[0] == (0.0, 4.0)


def test_extract_vad_silences_missing_faster_whisper(tmp_path):
    """When faster-whisper is not installed and no backend provided, raise ASRInferenceError."""
    audio_path = tmp_path / "test.wav"
    create_test_wav(audio_path)

    with patch.dict(sys.modules, {"faster_whisper": None, "faster_whisper.vad": None}):
        with pytest.raises(ASRInferenceError, match="faster-whisper is required"):
            extract_vad_silences(audio_path)


# ============================================================================
# 7. Public API Export Tests
# ============================================================================


def test_public_api_exports():
    """Verify all required ASR components are exported from subtitle_workbench."""
    import subtitle_workbench

    required_names = [
        "ASRError",
        "AudioFormatError",
        "ASRInferenceError",
        "VRAMAllocationError",
        "WhisperTranscriber",
        "extract_vad_silences",
    ]
    for name in required_names:
        assert hasattr(subtitle_workbench, name), f"Missing export: {name}"
        assert name in subtitle_workbench.__all__, f"{name} not in __all__"


# ============================================================================
# 8. Additional Edge Cases & Path Flexibility
# ============================================================================


def test_transcribe_and_silences_accept_str_path(tmp_path):
    """transcribe and extract_vad_silences must accept both str and Path."""
    audio_path = tmp_path / "str_path.wav"
    create_test_wav(audio_path, duration_sec=2.0)

    transcriber = WhisperTranscriber(model_instance=DummyWhisperBackend())
    segments = transcriber.transcribe(str(audio_path))
    assert len(segments) > 0

    silences = extract_vad_silences(
        str(audio_path),
        vad_backend=lambda samples, **kw: [{"start": 0, "end": 16000}],
    )
    assert isinstance(silences, list)


def test_extract_vad_silences_object_with_method(tmp_path):
    """extract_vad_silences handles backend objects with get_speech_timestamps."""
    audio_path = tmp_path / "obj_backend.wav"
    create_test_wav(audio_path, duration_sec=3.0)

    class CustomVAD:
        def get_speech_timestamps(self, samples):
            return [{"start": 16000, "end": 32000}]

    silences = extract_vad_silences(audio_path, vad_backend=CustomVAD())
    assert len(silences) == 2
    assert silences[0] == (0.0, 1.0)
    assert silences[1] == (2.0, 3.0)


def test_transcribe_handles_punctuation_tokens(tmp_path):
    """Whisper occasionally emits isolated punctuation tokens; they should be handled safely."""
    audio_path = tmp_path / "punct_test.wav"
    create_test_wav(audio_path, duration_sec=2.0)

    class PunctBackend:
        def transcribe(self, *args, **kwargs):
            segments = [
                DummySegment(
                    id=0,
                    start=0.5,
                    end=1.8,
                    text="Hello - world",
                    words=[
                        DummyWord("Hello", 0.5, 0.9, 0.98),
                        DummyWord("-", 0.95, 1.0, 0.5),
                        DummyWord("world", 1.1, 1.5, 0.95),
                    ],
                )
            ]
            return iter(segments), DummyTranscriptionInfo()

    transcriber = WhisperTranscriber(model_instance=PunctBackend())
    segments = transcriber.transcribe(audio_path)
    assert len(segments) == 1
    # Check that all emitted words satisfy contracts
    for w in segments[0].words:
        assert w.start < w.end
        assert w.normalized != ""


# ============================================================================
# 9. Adversarial & Edge-Case Robustness Tests
# ============================================================================


def test_extract_vad_silences_sub_threshold_duration(tmp_path):
    """Audio shorter than min_silence_duration_ms with no speech must return no pauses."""
    audio_path = tmp_path / "sub_thresh.wav"
    create_test_wav(audio_path, duration_sec=0.2)  # 200ms < 400ms

    silences = extract_vad_silences(
        audio_path,
        min_silence_duration_ms=400,
        vad_backend=lambda s, **kw: [],
    )
    assert silences == []


def test_transcribe_microsecond_timestamps_rounding_collapse(tmp_path):
    """Word timestamps that differ by less than rounding threshold must not collapse."""
    audio_path = tmp_path / "micro.wav"
    create_test_wav(audio_path, duration_sec=1.5)

    class MicroBackend:
        def transcribe(self, *args, **kwargs):
            return iter(
                [
                    DummySegment(
                        id=0,
                        start=1.00001,
                        end=1.00004,
                        text="Hello",
                        words=[DummyWord("Hello", 1.00001, 1.00004)],
                    )
                ]
            ), DummyTranscriptionInfo()

    transcriber = WhisperTranscriber(model_instance=MicroBackend())
    segments = transcriber.transcribe(audio_path)
    assert len(segments) == 1
    w = segments[0].words[0]
    assert w.start < w.end
    assert segments[0].start < segments[0].end


def test_extract_vad_silences_seconds_over_100_seconds(tmp_path):
    """extract_vad_silences handles chunk timestamps in seconds exceeding 100 without corrupting."""
    audio_path = tmp_path / "long_clip.wav"
    create_test_wav(audio_path, duration_sec=120.0)

    silences = extract_vad_silences(
        audio_path,
        min_silence_duration_ms=400,
        vad_backend=lambda s, **kw: [(105, 110)],
    )
    assert len(silences) == 2
    assert silences[0] == (0.0, 105.0)
    assert silences[1] == (110.0, 120.0)


def test_extract_vad_silences_sample_index_under_100(tmp_path):
    """extract_vad_silences properly scales small sample indices under 100 samples."""
    audio_path = tmp_path / "sample_scale.wav"
    create_test_wav(audio_path, duration_sec=2.0)

    # 50 samples = 0.0031s, 16000 samples = 1.0s
    silences = extract_vad_silences(
        audio_path,
        min_silence_duration_ms=400,
        vad_backend=lambda s, **kw: [(50, 16000)],
    )
    assert len(silences) == 1
    assert silences[0] == (1.0, 2.0)


def test_transcribe_sanitizes_control_characters(tmp_path):
    """Raw Whisper output containing control characters must be sanitized without ValueError."""
    audio_path = tmp_path / "control_chars.wav"
    create_test_wav(audio_path, duration_sec=1.0)

    class DirtyBackend:
        def transcribe(self, *args, **kwargs):
            return iter(
                [
                    DummySegment(
                        id=0,
                        start=0.1,
                        end=0.9,
                        text="Hello \x00 world",
                        words=[
                            DummyWord("Hello", 0.1, 0.4),
                            DummyWord("\x00", 0.4, 0.5),
                            DummyWord("world", 0.5, 0.9),
                        ],
                    )
                ]
            ), DummyTranscriptionInfo()

    transcriber = WhisperTranscriber(model_instance=DirtyBackend())
    segments = transcriber.transcribe(audio_path)
    assert len(segments) == 1
    assert all("\x00" not in w.text for w in segments[0].words)


def test_transcribe_synthesizes_words_when_raw_words_omitted(tmp_path):
    """When Whisper provides segment text but empty words list, words should be synthesized."""
    audio_path = tmp_path / "no_words.wav"
    create_test_wav(audio_path, duration_sec=2.0)

    class NoWordsBackend:
        def transcribe(self, *args, **kwargs):
            return iter(
                [
                    DummySegment(
                        id=0,
                        start=0.5,
                        end=1.5,
                        text="Synthesized segment text",
                        words=[],
                    )
                ]
            ), DummyTranscriptionInfo()

    transcriber = WhisperTranscriber(model_instance=NoWordsBackend())
    segments = transcriber.transcribe(audio_path)
    assert len(segments) == 1
    assert len(segments[0].words) == 3
    assert [w.text for w in segments[0].words] == ["Synthesized", "segment", "text"]
    for w in segments[0].words:
        assert w.start < w.end
        assert 0.5 <= w.start < w.end <= 1.5


def test_transcribe_vram_allocation_error_on_alloc_failure(tmp_path):
    """Various allocation error strings must map to VRAMAllocationError."""
    audio_path = tmp_path / "oom.wav"
    create_test_wav(audio_path)

    class AllocFailBackend:
        def transcribe(self, *args, **kwargs):
            raise RuntimeError("Failed to allocate 2097152 bytes on device: CUDA error")

    transcriber = WhisperTranscriber(model_instance=AllocFailBackend())
    with pytest.raises(VRAMAllocationError):
        transcriber.transcribe(audio_path)


def test_device_resolution_handles_cuda_driver_exception():
    """Auto device resolution uses cpu when CTranslate2 raises while probing CUDA."""
    mock_ct2 = MagicMock()
    mock_ct2.get_cuda_device_count.side_effect = RuntimeError("Driver mismatch")

    with patch.dict(sys.modules, {"ctranslate2": mock_ct2}):
        transcriber = WhisperTranscriber(
            model_instance=DummyWhisperBackend(),
            device=None,
            compute_type=None,
        )
        assert transcriber.device == "cpu"
        assert transcriber.compute_type == "int8"


def test_explicit_cuda_request_is_strict():
    """device='cuda' must raise instead of silently running on CPU."""
    with patch("subtitle_workbench.asr.whisper_cuda_available", return_value=False):
        with pytest.raises(ASRInferenceError, match="cuda"):
            WhisperTranscriber(model_instance=DummyWhisperBackend(), device="cuda")


def test_extract_vad_silences_timestamp_overshoot_not_treated_as_samples(tmp_path):
    """Speech timestamps in seconds slightly exceeding duration must not trigger sample division."""
    audio_path = tmp_path / "overshoot.wav"
    create_test_wav(audio_path, duration_sec=5.0)

    # 10ms overshoot due to audio frame boundary (5.01s > 5.00s)
    silences = extract_vad_silences(
        audio_path,
        min_silence_duration_ms=400,
        vad_backend=lambda s, **kw: [(0.5, 5.01)],
    )
    assert silences == [(0.0, 0.5)]


def test_corrupted_wav_chunk_structure_raises_audio_format_error(tmp_path):
    """Corrupted WAV chunk structures raising wave/RuntimeError must map to AudioFormatError."""
    import struct

    from subtitle_workbench.audio import validate_wav

    audio_path = tmp_path / "corrupt_chunk.wav"
    riff_header = b"RIFF"
    fmt_chunk = b"fmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00"
    # LIST chunk with corrupted inner size 14 vs 16 bytes triggers RuntimeError in wave.py
    list_chunk = b"LIST\x0e\x00\x00\x00INFOINAM\x04\x00\x00\x00Test"
    data_chunk = b"data\x04\x00\x00\x00\x00\x00\x00\x00"
    file_bytes = (
        riff_header
        + struct.pack("<I", 4 + len(fmt_chunk) + len(list_chunk) + len(data_chunk))
        + b"WAVE"
        + fmt_chunk
        + list_chunk
        + data_chunk
    )
    audio_path.write_bytes(file_bytes)

    with pytest.raises(ValueError):
        validate_wav(audio_path)

    transcriber = WhisperTranscriber(model_instance=DummyWhisperBackend())
    with pytest.raises(AudioFormatError):
        transcriber.transcribe(audio_path)

    with pytest.raises(AudioFormatError):
        extract_vad_silences(audio_path)


def test_extract_vad_silences_backend_runtime_error_wrapped(tmp_path):
    """Custom VAD backend exceptions must be wrapped into ASRInferenceError."""
    audio_path = tmp_path / "vad_fail.wav"
    create_test_wav(audio_path, duration_sec=2.0)

    def failing_backend(*args, **kwargs):
        raise RuntimeError("Silero VAD execution failed")

    with pytest.raises(ASRInferenceError) as exc_info:
        extract_vad_silences(audio_path, vad_backend=failing_backend)
    assert "Silero VAD execution failed" in str(exc_info.value)


def test_extract_vad_silences_malformed_chunk_payload_wrapped(tmp_path):
    """Malformed speech chunk payloads with non-numeric fields must raise ASRInferenceError."""
    audio_path = tmp_path / "vad_malformed.wav"
    create_test_wav(audio_path, duration_sec=2.0)

    with pytest.raises(ASRInferenceError):
        extract_vad_silences(
            audio_path,
            vad_backend=lambda s, **kw: [{"start": "not_a_number", "end": 1000}],
        )


def test_transcribe_hyphenated_compound_words_preserved(tmp_path):
    """Compound hyphenated words must retain their full token text rather than truncating."""
    audio_path = tmp_path / "hyphen.wav"
    create_test_wav(audio_path, duration_sec=2.0)

    class CompoundBackend:
        def transcribe(self, *args, **kwargs):
            return iter(
                [
                    DummySegment(
                        id=0,
                        start=0.5,
                        end=1.5,
                        text="twenty-five years",
                        words=[
                            DummyWord("twenty-five", 0.5, 1.0, 0.95),
                            DummyWord("years", 1.05, 1.5, 0.94),
                        ],
                    )
                ]
            ), DummyTranscriptionInfo()

    transcriber = WhisperTranscriber(model_instance=CompoundBackend())
    segments = transcriber.transcribe(audio_path)
    assert len(segments) == 1
    words = segments[0].words
    assert words[0].text == "twenty-five"
    assert words[0].normalized == "twenty five"


def test_transcribe_words_sorted_and_segment_bounds_encompassing(tmp_path):
    """Segment words must be chronologically ordered and segment bounds encompass all word spans."""
    audio_path = tmp_path / "jitter.wav"
    create_test_wav(audio_path, duration_sec=3.0)

    class JitterBackend:
        def transcribe(self, *args, **kwargs):
            return iter(
                [
                    DummySegment(
                        id=0,
                        start=1.0,
                        end=1.8,
                        text="Two words",
                        words=[
                            DummyWord("words", 1.5, 2.0, 0.95),
                            DummyWord("Two", 0.8, 1.2, 0.96),
                        ],
                    )
                ]
            ), DummyTranscriptionInfo()

    transcriber = WhisperTranscriber(model_instance=JitterBackend())
    segments = transcriber.transcribe(audio_path)
    assert len(segments) == 1
    seg = segments[0]
    # Words must be sorted chronologically
    assert seg.words[0].text == "Two"
    assert seg.words[1].text == "words"
    # Segment bounds must encompass all word spans
    assert seg.start <= seg.words[0].start
    assert seg.end >= seg.words[1].end


def test_transcribe_rejects_empty_or_whitespace_language(tmp_path):
    """transcribe must reject empty or whitespace language strings with ASRInferenceError."""
    audio_path = tmp_path / "lang.wav"
    create_test_wav(audio_path, duration_sec=1.0)

    transcriber = WhisperTranscriber(model_instance=DummyWhisperBackend())
    with pytest.raises(ASRInferenceError):
        transcriber.transcribe(audio_path, language="")

    with pytest.raises(ASRInferenceError):
        transcriber.transcribe(audio_path, language="   ")

    with pytest.raises(ASRInferenceError):
        transcriber.transcribe(audio_path, language=None)  # type: ignore[arg-type]


def test_rejects_non_positive_silence_duration(tmp_path):
    """Non-positive silence duration must be rejected."""
    audio_path = tmp_path / "sil_dur.wav"
    create_test_wav(audio_path, duration_sec=1.0)

    with pytest.raises(ASRInferenceError):
        WhisperTranscriber(min_silence_duration_ms=0)

    with pytest.raises(ASRInferenceError):
        WhisperTranscriber(min_silence_duration_ms=-100)

    with pytest.raises(ASRInferenceError):
        extract_vad_silences(audio_path, min_silence_duration_ms=0)

    with pytest.raises(ASRInferenceError):
        extract_vad_silences(audio_path, min_silence_duration_ms=-50)


def test_extract_vad_silences_handles_inverted_chunks(tmp_path):
    """Buggy third-party backends returning inverted chunks (end < start) must be normalized."""
    audio_path = tmp_path / "inverted_vad.wav"
    create_test_wav(audio_path, duration_sec=4.0)

    # Speech chunks: (2.0, 1.0) -> [1.0, 2.0] and (3.5, 3.0) -> [3.0, 3.5]
    # Expected silences with min_silence=400ms: [0.0, 1.0], [2.0, 3.0], [3.5, 4.0]
    silences = extract_vad_silences(
        audio_path,
        min_silence_duration_ms=400,
        vad_backend=lambda s, **kw: [(2.0, 1.0), (3.5, 3.0)],
    )
    assert silences == [(0.0, 1.0), (2.0, 3.0), (3.5, 4.0)]


def test_extract_vad_silences_handles_zero_length_and_negative_chunks(tmp_path):
    """Zero-length and out-of-bound negative chunks must be safely clamped or discarded."""
    audio_path = tmp_path / "zero_neg_vad.wav"
    create_test_wav(audio_path, duration_sec=3.0)

    # Chunks:
    # (-1.0, -0.2) -> both negative -> clamped to (0.0, 0.0) -> dropped
    # (1.0, 1.0) -> length 0 -> dropped
    # (-0.5, 0.8) -> clamped to (0.0, 0.8) -> speech
    # (2.0, 2.6) -> speech from 2.0 to 2.6
    # Silences: [0.8, 2.0] (1.2s), [2.6, 3.0] (0.4s)
    silences = extract_vad_silences(
        audio_path,
        min_silence_duration_ms=400,
        vad_backend=lambda s, **kw: [(-1.0, -0.2), (1.0, 1.0), (-0.5, 0.8), (2.0, 2.6)],
    )
    assert silences == [(0.8, 2.0), (2.6, 3.0)]


def test_extract_vad_silences_rejects_nan_and_inf_timestamps(tmp_path):
    """Non-finite timestamps (NaN, Inf) from VAD backend must raise ASRInferenceError."""
    audio_path = tmp_path / "nan_vad.wav"
    create_test_wav(audio_path, duration_sec=2.0)

    with pytest.raises(ASRInferenceError):
        extract_vad_silences(
            audio_path,
            vad_backend=lambda s, **kw: [(float("nan"), 1.0)],
        )

    with pytest.raises(ASRInferenceError):
        extract_vad_silences(
            audio_path,
            vad_backend=lambda s, **kw: [(0.5, float("inf"))],
        )


def test_transcribe_forwards_optional_kwargs(tmp_path):
    """transcribe must accept and forward optional kwargs (e.g. temperature, beam_size)."""
    audio_path = tmp_path / "kwargs.wav"
    create_test_wav(audio_path, duration_sec=1.0)

    backend = DummyWhisperBackend()
    transcriber = WhisperTranscriber(model_instance=backend)
    segments = transcriber.transcribe(
        audio_path,
        language="en",
        temperature=0.2,
        beam_size=3,
    )
    assert len(segments) > 0
    assert backend.transcribe_called is True
    assert backend.transcribe_args.get("temperature") == 0.2
    assert backend.transcribe_args.get("beam_size") == 3
    assert backend.transcribe_args.get("word_timestamps") is True


def test_transcribe_handles_inverted_segment_and_word_timings(tmp_path):
    """Segment and word timings with start >= end must be repaired to maintain contract."""
    audio_path = tmp_path / "inverted_timing.wav"
    create_test_wav(audio_path, duration_sec=3.0)

    class InvertedBackend:
        def transcribe(self, *args, **kwargs):
            return iter(
                [
                    DummySegment(
                        id=0,
                        start=2.5,
                        end=0.5,  # Inverted segment: start > end
                        text="Inverted timing test",
                        words=[
                            DummyWord("Inverted", 2.0, 1.0, 0.95),  # Inverted word
                            DummyWord("timing", 2.2, 2.2, 0.94),  # Zero-length word
                            DummyWord("test", 2.4, 2.8, 0.96),
                        ],
                    )
                ]
            ), DummyTranscriptionInfo()

    transcriber = WhisperTranscriber(model_instance=InvertedBackend())
    segments = transcriber.transcribe(audio_path)
    assert len(segments) == 1
    seg = segments[0]
    assert 0.0 <= seg.start < seg.end
    for w in seg.words:
        assert 0.0 <= seg.start <= w.start < w.end <= seg.end


def test_transcribe_handles_inverted_segment_with_synthesized_words(tmp_path):
    """Inverted segment without words must synthesize valid tokens across the repaired span."""
    audio_path = tmp_path / "inverted_synth.wav"
    create_test_wav(audio_path, duration_sec=4.0)

    class InvertedSynthBackend:
        def transcribe(self, *args, **kwargs):
            return iter(
                [
                    DummySegment(
                        id=0,
                        start=3.0,
                        end=1.0,  # Inverted segment
                        text="Synthesize words please",
                        words=[],  # No words provided by backend
                    )
                ]
            ), DummyTranscriptionInfo()

    transcriber = WhisperTranscriber(model_instance=InvertedSynthBackend())
    segments = transcriber.transcribe(audio_path)
    assert len(segments) == 1
    seg = segments[0]
    assert seg.start == 1.0
    assert seg.end == 3.0
    assert len(seg.words) == 3
    for w in seg.words:
        assert 0.0 <= seg.start <= w.start < w.end <= seg.end


def test_transcribe_and_silences_reject_invalid_audio_path_types():
    """Non-string, non-Path audio paths must raise AudioFormatError instead of raw TypeError."""
    backend = DummyWhisperBackend()
    transcriber = WhisperTranscriber(model_instance=backend)

    with pytest.raises(AudioFormatError):
        transcriber.transcribe(None)  # type: ignore[arg-type]

    with pytest.raises(AudioFormatError):
        transcriber.transcribe(12345)  # type: ignore[arg-type]

    with pytest.raises(AudioFormatError):
        extract_vad_silences(None)  # type: ignore[arg-type]

    with pytest.raises(AudioFormatError):
        extract_vad_silences([Path("some.wav")])  # type: ignore[arg-type]


def test_validate_wav_streaming_memory_and_invalid_types(tmp_path):
    """validate_wav must reject invalid path types, accept strings, and stream frames."""
    from subtitle_workbench.audio import validate_wav

    with pytest.raises(TypeError):
        validate_wav(None)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        validate_wav(123)  # type: ignore[arg-type]

    audio_path = tmp_path / "valid_test.wav"
    create_test_wav(audio_path, duration_sec=1.0)

    # String path accepted
    validate_wav(str(audio_path))
    # Path object accepted
    validate_wav(audio_path)


# ============================================================================
# 10. Optional Live Integration Test (Skipped in Base CI)
# ============================================================================

try:
    import faster_whisper  # noqa: F401

    HAS_FASTER_WHISPER = True
except ImportError:
    HAS_FASTER_WHISPER = False


@pytest.mark.skipif(not HAS_FASTER_WHISPER, reason="faster-whisper is not installed")
def test_live_faster_whisper_transcription(tmp_path):
    """Live integration test when faster-whisper is available in the environment."""
    audio_path = tmp_path / "live.wav"
    create_test_wav(audio_path, duration_sec=2.0)

    transcriber = WhisperTranscriber(model_size_or_path="tiny")
    try:
        segments = transcriber.transcribe(audio_path, language="en")
        assert isinstance(segments, list)
    finally:
        transcriber.unload()
