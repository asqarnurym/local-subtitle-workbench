"""Unit and integration tests for Montreal Forced Aligner batch adapter and Praat parser.

Tests cover:
- check_mfa_available detection
- Pure-Python Praat TextGrid parser (long format and short format)
- Silence interval filtering ("", "<sil>", "sil", "sp")
- Phoneme-to-word containment association and micro-phoneme duration enforcement
- Temporal invariant enforcement (start < end, duration >= 1ms, monotonic progression)
- Edge cases: zero-duration intervals, missing tiers, scientific float notation
- Batch staging architecture: temporary corpus creation, single-batch subprocess execution,
  and cleanup in finally block
- Typed error handling: MFANotFoundError, MFATimeoutError, MFAExecutionError
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from subtitle_workbench.mfa_wrapper import (
    MFAExecutionError,
    MFANotFoundError,
    MFATimeoutError,
    SubprocessRunner,
    check_mfa_available,
    parse_textgrid,
    run_mfa_batch,
)
from subtitle_workbench.models import PhonemeCue, WordToken

# ============================================================================
# Praat TextGrid Sample Fixtures
# ============================================================================

PRAAT_LONG_TEXTGRID = """File type = "ooTextFile"
Object class = "TextGrid"

xmin = 0.0 
xmax = 2.5 
tiers? <exists> 
size = 2 
item []: 
    item [1]:
        class = "IntervalTier" 
        name = "words" 
        xmin = 0.0 
        xmax = 2.5 
        intervals: size = 4 
        intervals [1]:
            xmin = 0.0 
            xmax = 0.2 
            text = "" 
        intervals [2]:
            xmin = 0.2 
            xmax = 1.0 
            text = "hello" 
        intervals [3]:
            xmin = 1.0 
            xmax = 1.1 
            text = "sp" 
        intervals [4]:
            xmin = 1.1 
            xmax = 2.2 
            text = "world" 
    item [2]:
        class = "IntervalTier" 
        name = "phones" 
        xmin = 0.0 
        xmax = 2.5 
        intervals: size = 7 
        intervals [1]:
            xmin = 0.0 
            xmax = 0.2 
            text = "<sil>" 
        intervals [2]:
            xmin = 0.2 
            xmax = 0.5 
            text = "HH" 
        intervals [3]:
            xmin = 0.5 
            xmax = 1.0 
            text = "AH0" 
        intervals [4]:
            xmin = 1.0 
            xmax = 1.1 
            text = "sil" 
        intervals [5]:
            xmin = 1.1 
            xmax = 1.4 
            text = "W" 
        intervals [6]:
            xmin = 1.4 
            xmax = 1.8 
            text = "ER1" 
        intervals [7]:
            xmin = 1.8 
            xmax = 2.2 
            text = "L D" 
"""

PRAAT_SHORT_TEXTGRID = """File type = "ooTextFile"
Object class = "TextGrid"

0.0
2.5
<exists>
2
"IntervalTier"
"words"
0.0
2.5
4
0.0
0.2
""
0.2
1.0
"hello"
1.0
1.1
"sp"
1.1
2.2
"world"
"IntervalTier"
"phones"
0.0
2.5
7
0.0
0.2
"<sil>"
0.2
0.5
"HH"
0.5
1.0
"AH0"
1.0
1.1
"sil"
1.1
1.4
"W"
1.4
1.8
"ER1"
1.8
2.2
"L D"
"""


def create_dummy_wav(path: Path, duration_sec: float = 1.0, sample_rate: int = 16000) -> None:
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
# MFA Availability Tests
# ============================================================================


def test_check_mfa_available_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/local/bin/mfa" if cmd == "mfa" else None)
    assert check_mfa_available() is True


def test_check_mfa_available_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    assert check_mfa_available() is False


# ============================================================================
# TextGrid Parser Tests
# ============================================================================


def test_parse_textgrid_long_format() -> None:
    tokens = parse_textgrid(PRAAT_LONG_TEXTGRID)
    assert len(tokens) == 2

    # First word: hello [0.2, 1.0]
    w1 = tokens[0]
    assert isinstance(w1, WordToken)
    assert w1.text == "hello"
    assert w1.normalized == "hello"
    assert w1.start == 0.2
    assert w1.end == 1.0
    assert w1.confidence == 1.0
    assert len(w1.phonemes) == 2
    assert w1.phonemes[0] == PhonemeCue("HH", 0.2, 0.5, 1.0)
    assert w1.phonemes[1] == PhonemeCue("AH0", 0.5, 1.0, 1.0)

    # Second word: world [1.1, 2.2]
    w2 = tokens[1]
    assert isinstance(w2, WordToken)
    assert w2.text == "world"
    assert w2.normalized == "world"
    assert w2.start == 1.1
    assert w2.end == 2.2
    assert len(w2.phonemes) == 3
    assert w2.phonemes[0].phoneme == "W"
    assert w2.phonemes[1].phoneme == "ER1"
    assert w2.phonemes[2].phoneme == "L D"


def test_parse_textgrid_short_format() -> None:
    tokens = parse_textgrid(PRAAT_SHORT_TEXTGRID)
    assert len(tokens) == 2
    assert tokens[0].text == "hello"
    assert tokens[0].start == 0.2
    assert tokens[0].end == 1.0
    assert len(tokens[0].phonemes) == 2

    assert tokens[1].text == "world"
    assert tokens[1].start == 1.1
    assert tokens[1].end == 2.2
    assert len(tokens[1].phonemes) == 3


def test_parse_textgrid_silence_filtering() -> None:
    tg = """File type = "ooTextFile"
Object class = "TextGrid"
xmin = 0.0
xmax = 3.0
tiers? <exists>
size = 2
item []:
    item [1]:
        class = "IntervalTier"
        name = "words"
        xmin = 0.0
        xmax = 3.0
        intervals: size = 5
        intervals [1]:
            xmin = 0.0
            xmax = 0.5
            text = ""
        intervals [2]:
            xmin = 0.5
            xmax = 1.0
            text = "<sil>"
        intervals [3]:
            xmin = 1.0
            xmax = 1.5
            text = "speech"
        intervals [4]:
            xmin = 1.5
            xmax = 2.0
            text = "sp"
        intervals [5]:
            xmin = 2.0
            xmax = 3.0
            text = "sil"
    item [2]:
        class = "IntervalTier"
        name = "phones"
        xmin = 0.0
        xmax = 3.0
        intervals: size = 3
        intervals [1]:
            xmin = 0.0
            xmax = 1.0
            text = "<sil>"
        intervals [2]:
            xmin = 1.0
            xmax = 1.5
            text = "S"
        intervals [3]:
            xmin = 1.5
            xmax = 3.0
            text = "sp"
"""
    tokens = parse_textgrid(tg)
    assert len(tokens) == 1
    assert tokens[0].text == "speech"
    assert len(tokens[0].phonemes) == 1
    assert tokens[0].phonemes[0].phoneme == "S"


def test_parse_textgrid_zero_duration_intervals() -> None:
    tg = """File type = "ooTextFile"
Object class = "TextGrid"
xmin = 0.0
xmax = 2.0
tiers? <exists>
size = 2
item []:
    item [1]:
        class = "IntervalTier"
        name = "words"
        xmin = 0.0
        xmax = 2.0
        intervals: size = 3
        intervals [1]:
            xmin = 0.5
            xmax = 0.5
            text = "zero"
        intervals [2]:
            xmin = 0.6
            xmax = 0.5
            text = "inverted"
        intervals [3]:
            xmin = 0.8
            xmax = 1.5
            text = "valid"
    item [2]:
        class = "IntervalTier"
        name = "phones"
        xmin = 0.0
        xmax = 2.0
        intervals: size = 1
        intervals [1]:
            xmin = 0.8
            xmax = 1.5
            text = "V"
"""
    tokens = parse_textgrid(tg)
    assert len(tokens) == 1
    assert tokens[0].text == "valid"
    assert tokens[0].start == 0.8
    assert tokens[0].end == 1.5


def test_parse_textgrid_missing_phones_tier() -> None:
    tg = """File type = "ooTextFile"
Object class = "TextGrid"
xmin = 0.0
xmax = 1.0
tiers? <exists>
size = 1
item []:
    item [1]:
        class = "IntervalTier"
        name = "words"
        xmin = 0.0
        xmax = 1.0
        intervals: size = 1
        intervals [1]:
            xmin = 0.1
            xmax = 0.9
            text = "solitary"
"""
    tokens = parse_textgrid(tg)
    assert len(tokens) == 1
    assert tokens[0].text == "solitary"
    assert tokens[0].phonemes == []


def test_parse_textgrid_missing_words_tier() -> None:
    tg = """File type = "ooTextFile"
Object class = "TextGrid"
xmin = 0.0
xmax = 1.0
tiers? <exists>
size = 1
item []:
    item [1]:
        class = "IntervalTier"
        name = "phones"
        xmin = 0.0
        xmax = 1.0
        intervals: size = 1
        intervals [1]:
            xmin = 0.1
            xmax = 0.9
            text = "AA"
"""
    tokens = parse_textgrid(tg)
    assert tokens == []


def test_parse_textgrid_scientific_float_notation() -> None:
    tg = """File type = "ooTextFile"
Object class = "TextGrid"
xmin = 0.000000e+00
xmax = 2.500000e+00
tiers? <exists>
size = 2
item []:
    item [1]:
        class = "IntervalTier"
        name = "words"
        xmin = 0.000000e+00
        xmax = 2.500000e+00
        intervals: size = 1
        intervals [1]:
            xmin = 1.500000e-01
            xmax = 1.250000e+00
            text = "science"
    item [2]:
        class = "IntervalTier"
        name = "phones"
        xmin = 0.000000e+00
        xmax = 2.500000e+00
        intervals: size = 1
        intervals [1]:
            xmin = 1.500000e-01
            xmax = 1.250000e+00
            text = "S"
"""
    tokens = parse_textgrid(tg)
    assert len(tokens) == 1
    assert tokens[0].start == 0.15
    assert tokens[0].end == 1.25
    assert tokens[0].phonemes[0].start == 0.15
    assert tokens[0].phonemes[0].end == 1.25


def test_parse_textgrid_phone_clamping_to_word_boundaries() -> None:
    tg = """File type = "ooTextFile"
Object class = "TextGrid"
xmin = 0.0
xmax = 2.0
tiers? <exists>
size = 2
item []:
    item [1]:
        class = "IntervalTier"
        name = "words"
        xmin = 0.0
        xmax = 2.0
        intervals: size = 1
        intervals [1]:
            xmin = 0.5
            xmax = 1.0
            text = "clamp"
    item [2]:
        class = "IntervalTier"
        name = "phones"
        xmin = 0.0
        xmax = 2.0
        intervals: size = 1
        intervals [1]:
            xmin = 0.49
            xmax = 1.02
            text = "K"
"""
    tokens = parse_textgrid(tg)
    assert len(tokens) == 1
    assert tokens[0].start == 0.5
    assert tokens[0].end == 1.0
    assert tokens[0].phonemes[0].start == 0.5
    assert tokens[0].phonemes[0].end == 1.0


# ============================================================================
# Batch Subprocess & Corpus Staging Tests
# ============================================================================


def test_run_mfa_batch_empty() -> None:
    assert run_mfa_batch([]) == []


def test_run_mfa_batch_mfa_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    dummy_wav = tmp_path / "dummy.wav"
    create_dummy_wav(dummy_wav)

    with pytest.raises(MFANotFoundError) as exc_info:
        run_mfa_batch([(dummy_wav, "hello")])
    assert "conda" in str(exc_info.value).lower()
    assert "mfa" in str(exc_info.value).lower()


def test_run_mfa_batch_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/mfa")
    dummy_wav = tmp_path / "dummy.wav"
    create_dummy_wav(dummy_wav)

    mock_runner = MagicMock(spec=SubprocessRunner)
    mock_runner.run.side_effect = subprocess.TimeoutExpired(cmd=["mfa"], timeout=10)

    with pytest.raises(MFATimeoutError) as exc_info:
        run_mfa_batch([(dummy_wav, "hello")], runner=mock_runner)
    assert "timed out" in str(exc_info.value).lower()


def test_run_mfa_batch_execution_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/mfa")
    dummy_wav = tmp_path / "dummy.wav"
    create_dummy_wav(dummy_wav)

    mock_runner = MagicMock(spec=SubprocessRunner)
    mock_runner.run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["mfa"],
        stderr="Kaldi model acoustic failure",
    )

    with pytest.raises(MFAExecutionError) as exc_info:
        run_mfa_batch([(dummy_wav, "hello")], runner=mock_runner)
    assert "Kaldi model acoustic failure" in str(exc_info.value)


def test_run_mfa_batch_success_five_chunks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/mfa")

    # Prepare 5 chunk audio pairs
    chunk_pairs: list[tuple[Path, str]] = []
    for i in range(5):
        w_path = tmp_path / f"input_chunk_{i}.wav"
        create_dummy_wav(w_path, duration_sec=1.0)
        chunk_pairs.append((w_path, f"hello world {i}"))

    staging_dir_observed: list[Path] = []

    def mock_run_fn(cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
        # Validate CLI arguments
        assert cmd[0] == "mfa"
        assert cmd[1] == "align"
        corpus_arg = Path(cmd[2])
        out_arg = Path(cmd[5])
        assert "--clean" in cmd
        assert "--single_speaker" in cmd
        assert "--num_jobs" in cmd
        staging_dir_observed.append(corpus_arg.parent)

        # Check that corpus contains 5 wav and 5 lab files
        for i in range(5):
            wav_file = corpus_arg / f"chunk_{i:04d}.wav"
            lab_file = corpus_arg / f"chunk_{i:04d}.lab"
            assert wav_file.is_file()
            assert lab_file.is_file()
            assert lab_file.read_text(encoding="utf-8") == f"hello world {i}"

            # Write mock output TextGrid to out_arg
            tg_out = out_arg / f"chunk_{i:04d}.TextGrid"
            tg_out.write_text(PRAAT_LONG_TEXTGRID, encoding="utf-8")

        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="Success", stderr="")

    mock_runner = MagicMock(spec=SubprocessRunner)
    mock_runner.run.side_effect = mock_run_fn

    results = run_mfa_batch(chunk_pairs, runner=mock_runner)

    # Subprocess run exactly once for all 5 chunks
    assert mock_runner.run.call_count == 1
    assert len(results) == 5
    for chunk_tokens in results:
        assert len(chunk_tokens) == 2
        assert chunk_tokens[0].text == "hello"
        assert chunk_tokens[1].text == "world"

    # Verify staging directory was cleaned up
    assert len(staging_dir_observed) == 1
    assert not staging_dir_observed[0].exists()


def test_run_mfa_batch_custom_output_dir_preserved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/mfa")
    custom_out = tmp_path / "preserved_out"
    custom_out.mkdir()

    dummy_wav = tmp_path / "dummy.wav"
    create_dummy_wav(dummy_wav)

    def mock_run_fn(cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
        out_arg = Path(cmd[5])
        tg_out = out_arg / "chunk_0000.TextGrid"
        tg_out.write_text(PRAAT_SHORT_TEXTGRID, encoding="utf-8")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    mock_runner = MagicMock(spec=SubprocessRunner)
    mock_runner.run.side_effect = mock_run_fn

    results = run_mfa_batch([(dummy_wav, "hello world")], output_dir=custom_out, runner=mock_runner)
    assert len(results) == 1
    assert custom_out.exists()


def test_run_mfa_batch_passes_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/mfa")
    dummy_wav = tmp_path / "dummy.wav"
    create_dummy_wav(dummy_wav)

    mock_runner = MagicMock(spec=SubprocessRunner)
    mock_runner.run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )

    run_mfa_batch([(dummy_wav, "hello")], timeout=45.0, runner=mock_runner)
    assert mock_runner.run.call_count == 1
    _, kwargs = mock_runner.run.call_args
    assert kwargs.get("timeout") == 45.0
