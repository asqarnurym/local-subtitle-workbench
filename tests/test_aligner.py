"""Unit tests for CTC Trellis dynamic programming and ForcedAligner facade.

Covers:
- Pure-NumPy CTC Trellis dynamic programming math test oracle
- Viterbi backtracking accuracy on known synthetic emission posteriors
- Character-to-word segment aggregation with boundary separator '|'
- Temporal bounds and error modes (T < J)
- TorchAudioAligner lazy loading and offline fallback guard (CTCAlignerUnavailableError)
- ForcedAligner facade: engine routing ("auto", "mfa", "ctc"), MFA-to-CTC fallback,
  transcripts resolution, audio slicing, and global monotonic reconciliation.
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from subtitle_workbench.aligner import ForcedAligner, align_chunks
from subtitle_workbench.ctc_aligner import (
    CTCAlignerUnavailableError,
    TorchAudioAligner,
    align_ctc_trellis,
    backtrack,
    get_trellis,
)
from subtitle_workbench.mfa_wrapper import (
    MFANotFoundError,
    SubprocessRunner,
)
from subtitle_workbench.models import AudioChunk, WordToken


def create_dummy_wav(path: Path, duration_sec: float = 2.0, sample_rate: int = 16000) -> None:
    """Create a minimal valid PCM16 mono WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(duration_sec * sample_rate)
    data = b"\x00\x00" * n_samples
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(data)


# ============================================================================
# CTC Trellis Dynamic Programming Math Tests (Zero Torch, Pure NumPy)
# ============================================================================


def test_ctc_trellis_forward_and_backtrack_oracle() -> None:
    """Test CTC Trellis DP forward pass and backtrack on a synthetic 10x5 emission oracle."""
    num_frames = 10
    num_classes = 5

    # Initialize log probabilities to very negative numbers (-100.0)
    emissions = np.full((num_frames, num_classes), -100.0, dtype=np.float64)

    # Synthetic optimal path:
    # t=0..2: '|' (class 1)
    # t=3..5: 'c' (class 2)
    # t=6..7: 'a' (class 3)
    # t=8..9: 't' (class 4)
    emissions[0:3, 1] = 0.0  # prob = 1.0
    emissions[3:6, 2] = 0.0
    emissions[6:8, 3] = 0.0
    emissions[8:10, 4] = 0.0

    # Tokens sequence: ['|', 'c', 'a', 't'] -> [1, 2, 3, 4]
    tokens = [1, 2, 3, 4]

    trellis = get_trellis(emissions, tokens, blank_id=0)
    assert trellis.shape == (10, 4)
    assert trellis[0, 0] == 0.0  # Initial step at t=0, j=0

    # Verify cumulative path reached terminal token with 0.0 total log prob penalty
    assert trellis[9, 3] == 0.0

    path = backtrack(trellis, emissions, tokens, blank_id=0)
    assert len(path) == 10

    # Backtrack points match known frame assignments
    for pt in path[0:3]:
        assert pt.token_index == 0  # '|'
    for pt in path[3:6]:
        assert pt.token_index == 1  # 'c'
    for pt in path[6:8]:
        assert pt.token_index == 2  # 'a'
    for pt in path[8:10]:
        assert pt.token_index == 3  # 't'


def test_align_ctc_trellis_single_word() -> None:
    """Test full CTC Trellis word alignment from emissions to WordToken."""
    dictionary = {"*": 0, "|": 1, "c": 2, "a": 3, "t": 4}
    num_frames = 10
    num_classes = 5

    emissions = np.full((num_frames, num_classes), -50.0, dtype=np.float64)
    emissions[0:3, 1] = 0.0  # '|'
    emissions[3:6, 2] = 0.0  # 'c'
    emissions[6:8, 3] = 0.0  # 'a'
    emissions[8:10, 4] = 0.0  # 't'

    words = align_ctc_trellis(
        emissions=emissions,
        tokens="cat",
        dictionary=dictionary,
        frame_duration=0.02,
    )

    assert len(words) == 1
    w = words[0]
    assert w.text == "cat"
    assert w.start == round(3 * 0.02, 4)  # 0.06s
    assert w.end == round(9 * 0.02, 4)  # 0.18s (precedes trailing boundary separator at frame 9)
    assert w.confidence > 0.99


def test_align_ctc_trellis_multiple_words() -> None:
    """Test CTC Trellis multi-word alignment with intermediate boundary separator."""
    dictionary = {"*": 0, "|": 1, "c": 2, "a": 3, "t": 4, "d": 5, "o": 6, "g": 7}
    num_frames = 20
    num_classes = 8

    emissions = np.full((num_frames, num_classes), -50.0, dtype=np.float64)
    # "|cat|dog|"
    emissions[0:2, 1] = 0.0  # '|'
    emissions[2:4, 2] = 0.0  # 'c'
    emissions[4:6, 3] = 0.0  # 'a'
    emissions[6:8, 4] = 0.0  # 't'
    emissions[8:11, 1] = 0.0  # '|'
    emissions[11:14, 5] = 0.0  # 'd'
    emissions[14:17, 6] = 0.0  # 'o'
    emissions[17:20, 7] = 0.0  # 'g'

    words = align_ctc_trellis(
        emissions=emissions,
        tokens="cat dog",
        dictionary=dictionary,
        frame_duration=0.02,
    )

    assert len(words) == 2
    assert words[0].text == "cat"
    assert words[0].start == round(2 * 0.02, 4)  # 0.04s
    assert words[0].end == round(8 * 0.02, 4)  # 0.16s

    assert words[1].text == "dog"
    assert words[1].start == round(11 * 0.02, 4)  # 0.22s
    # Precedes trailing boundary separator at frame 19
    assert words[1].end == round(19 * 0.02, 4)  # 0.38s
    assert words[1].start >= words[0].end


def test_ctc_trellis_audio_too_short() -> None:
    """Verify that audio frame count shorter than token count raises ValueError."""
    emissions = np.zeros((3, 5), dtype=np.float64)  # 3 frames
    tokens = [1, 2, 3, 4]  # 4 tokens
    with pytest.raises(ValueError) as exc_info:
        get_trellis(emissions, tokens)
    assert "cannot be less than" in str(exc_info.value)


# ============================================================================
# TorchAudioAligner Offline Guard Tests
# ============================================================================


def test_torch_audio_aligner_lazy_init() -> None:
    """Verify TorchAudioAligner does not attempt torch imports on instantiation."""
    aligner = TorchAudioAligner(device="cpu")
    assert aligner._model is None
    assert aligner._dictionary is None


def test_torch_audio_aligner_unavailable_guard() -> None:
    """Verify TorchAudioAligner raises CTCAlignerUnavailableError when torch is absent."""
    aligner = TorchAudioAligner(device="cpu")
    # In base environment without torch, loading model raises CTCAlignerUnavailableError
    with pytest.raises(CTCAlignerUnavailableError) as exc_info:
        aligner._ensure_model()
    assert "required" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()


# ============================================================================
# ForcedAligner Facade Tests
# ============================================================================


def test_forced_aligner_empty_chunks(tmp_path: Path) -> None:
    audio_wav = tmp_path / "audio.wav"
    create_dummy_wav(audio_wav)
    assert align_chunks([], audio_wav) == []


def test_forced_aligner_missing_audio(tmp_path: Path) -> None:
    missing_wav = tmp_path / "non_existent.wav"
    chunk = AudioChunk(
        id="c0",
        index=0,
        start=0.0,
        end=1.0,
        padded_start=0.0,
        padded_end=1.5,
        text="hello",
    )
    with pytest.raises(FileNotFoundError):
        align_chunks([chunk], missing_wav)


def test_forced_aligner_transcript_length_mismatch(tmp_path: Path) -> None:
    audio_wav = tmp_path / "audio.wav"
    create_dummy_wav(audio_wav)
    chunk = AudioChunk(
        id="c0",
        index=0,
        start=0.0,
        end=1.0,
        padded_start=0.0,
        padded_end=1.5,
        text="hello",
    )
    with pytest.raises(ValueError) as exc_info:
        align_chunks([chunk], audio_wav, transcripts=["hello", "world"])
    assert "count" in str(exc_info.value)


def test_forced_aligner_mfa_missing_no_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    audio_wav = tmp_path / "audio.wav"
    create_dummy_wav(audio_wav)
    chunk = AudioChunk(
        id="c0",
        index=0,
        start=0.0,
        end=1.0,
        padded_start=0.0,
        padded_end=1.5,
        text="hello",
    )

    with pytest.raises(MFANotFoundError):
        align_chunks([chunk], audio_wav, engine="mfa", fallback_to_ctc=False)


def test_forced_aligner_mfa_success_mock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/mfa")
    audio_wav = tmp_path / "audio.wav"
    create_dummy_wav(audio_wav, duration_sec=5.0)

    # 2 chunks with overlap padding
    chunks = [
        AudioChunk(
            id="c0",
            index=0,
            start=0.0,
            end=2.0,
            padded_start=0.0,
            padded_end=2.5,
            text="hello world",
        ),
        AudioChunk(
            id="c1",
            index=1,
            start=2.0,
            end=4.0,
            padded_start=1.5,
            padded_end=4.5,
            text="goodbye friend",
        ),
    ]

    praat_tg_c0 = """File type = "ooTextFile"
Object class = "TextGrid"
xmin = 0.0
xmax = 2.5
tiers? <exists>
size = 1
item []:
    item [1]:
        class = "IntervalTier"
        name = "words"
        xmin = 0.0
        xmax = 2.5
        intervals: size = 2
        intervals [1]:
            xmin = 0.2
            xmax = 0.8
            text = "hello"
        intervals [2]:
            xmin = 1.0
            xmax = 1.8
            text = "world"
"""

    praat_tg_c1 = """File type = "ooTextFile"
Object class = "TextGrid"
xmin = 0.0
xmax = 3.0
tiers? <exists>
size = 1
item []:
    item [1]:
        class = "IntervalTier"
        name = "words"
        xmin = 0.0
        xmax = 3.0
        intervals: size = 2
        intervals [1]:
            xmin = 0.8
            xmax = 1.5
            text = "goodbye"
        intervals [2]:
            xmin = 1.6
            xmax = 2.4
            text = "friend"
"""

    def mock_run_fn(cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
        out_arg = Path(cmd[5])
        (out_arg / "chunk_0000.TextGrid").write_text(praat_tg_c0, encoding="utf-8")
        (out_arg / "chunk_0001.TextGrid").write_text(praat_tg_c1, encoding="utf-8")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    mock_runner = MagicMock(spec=SubprocessRunner)
    mock_runner.run.side_effect = mock_run_fn

    aligner = ForcedAligner(mfa_runner=mock_runner)
    reconciled = aligner.align_chunks(chunks, audio_wav, engine="mfa")

    assert len(reconciled) == 4
    texts = [w.text for w in reconciled]
    assert texts == ["hello", "world", "goodbye", "friend"]

    # Verify global coordinate translation:
    # Chunk 0 has padded_start = 0.0
    assert reconciled[0].start == 0.2
    assert reconciled[0].end == 0.8
    assert reconciled[1].start == 1.0
    assert reconciled[1].end == 1.8

    # Chunk 1 has padded_start = 1.5
    # goodbye was at [0.8, 1.5] relative -> [1.5 + 0.8, 1.5 + 1.5] = [2.3, 3.0]
    assert reconciled[2].start == 2.3
    assert reconciled[2].end == 3.0
    # friend was at [1.6, 2.4] relative -> [1.5 + 1.6, 1.5 + 2.4] = [3.1, 3.9]
    assert reconciled[3].start == 3.1
    assert reconciled[3].end == 3.9

    # Monotonicity holds
    for i in range(len(reconciled) - 1):
        assert reconciled[i + 1].start >= reconciled[i].end


def test_forced_aligner_auto_fallback_to_mocked_ctc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify that when MFA is absent, 'auto' transparently falls back to CTC aligner."""
    monkeypatch.setattr("shutil.which", lambda _: None)
    audio_wav = tmp_path / "audio.wav"
    create_dummy_wav(audio_wav, duration_sec=3.0)

    chunk = AudioChunk(
        id="c0",
        index=0,
        start=0.0,
        end=2.0,
        padded_start=0.0,
        padded_end=2.5,
        text="test word",
    )

    # Mock CTC aligner
    mock_ctc = MagicMock(spec=TorchAudioAligner)
    mock_ctc.align.return_value = [
        WordToken(
            id="w0",
            text="test",
            normalized="test",
            start=0.2,
            end=0.6,
            confidence=0.98,
        ),
        WordToken(
            id="w1",
            text="word",
            normalized="word",
            start=0.7,
            end=1.2,
            confidence=0.97,
        ),
    ]

    aligner = ForcedAligner(ctc_aligner=mock_ctc)
    reconciled = aligner.align_chunks([chunk], audio_wav, engine="auto", fallback_to_ctc=True)

    assert len(reconciled) == 2
    assert reconciled[0].text == "test"
    assert reconciled[1].text == "word"
    assert mock_ctc.align.call_count == 1

    # Also verify string path support
    reconciled_str = aligner.align_chunks([chunk], str(audio_wav), engine="auto")
    assert len(reconciled_str) == 2


def test_slice_wav_duration_bounds(tmp_path: Path) -> None:
    """Verify slice_wav raises ValueError when start_sec exceeds audio duration."""
    from subtitle_workbench.audio import slice_wav

    audio_wav = tmp_path / "bounds_audio.wav"
    create_dummy_wav(audio_wav, duration_sec=2.0)
    out_slice = tmp_path / "slice.wav"

    with pytest.raises(ValueError) as exc_info:
        slice_wav(audio_wav, out_slice, start_sec=2.5, end_sec=3.0)
    assert "strictly less than audio duration" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        slice_wav(audio_wav, out_slice, start_sec=-0.5, end_sec=1.0)
    assert "non-negative" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        slice_wav(audio_wav, out_slice, start_sec=1.0, end_sec=0.5)
    assert "strictly greater" in str(exc_info.value)
