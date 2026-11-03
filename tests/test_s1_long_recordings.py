"""Tests for the S1 long-recording wrapper (scripts/s1_long_recordings.py)."""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.analyze_speaker_errors import exact_signed_rank  # noqa: E402
from scripts.s1_long_recordings import (  # noqa: E402
    MIN_PAIRS,
    NullTranscriber,
    brute_force_p,
    build_speaker,
    paired_test,
    read_pcm,
    word_errors,
)
from subtitle_workbench.anchoring import anchor_transcript  # noqa: E402
from subtitle_workbench.buckeye import Interval, _textgrid  # noqa: E402
from subtitle_workbench.corpora import parse_buckeye_textgrid  # noqa: E402
from subtitle_workbench.models import WordToken  # noqa: E402

SR = 16000


def _clip(directory: Path, clip_id: str, seconds: float, words: list[str], seed: int) -> None:
    n = int(seconds * SR)
    audio = (np.random.default_rng(seed).normal(0, 300, n)).astype(np.int16)
    with wave.open(str(directory / f"{clip_id}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(audio.tobytes())
    step = (seconds - 0.2) / len(words)
    ivs = [Interval(0.1 + k * step, 0.1 + (k + 1) * step, t) for k, t in enumerate(words)]
    phones = [Interval(iv.start, (iv.start + iv.end) / 2, "ah") for iv in ivs] + [
        Interval((iv.start + iv.end) / 2, iv.end, "t") for iv in ivs
    ]
    phones.sort(key=lambda p: p.start)
    (directory / f"{clip_id}.TextGrid").write_text(
        _textgrid(ivs, phones, 0.0, seconds), encoding="utf-8"
    )


@pytest.fixture
def clips(tmp_path: Path) -> Path:
    src = tmp_path / "clips"
    src.mkdir()
    _clip(src, "s02a_0000", 1.0, ["one", "two"], 1)
    with wave.open(str(src / "s02a_0001.wav"), "wb") as w:  # empty clip: skipped
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
    (src / "s02a_0001.TextGrid").write_text("", encoding="utf-8")
    _clip(src, "s02a_0002", 1.5, ["three", "four", "five"], 2)
    _clip(src, "s02b_0000", 1.25, ["six", "seven"], 3)
    _clip(src, "s03a_0000", 2.0, ["other", "speaker"], 4)
    return src


def test_build_concatenates_nested_prefixes_exactly(clips: Path, tmp_path: Path) -> None:
    dest = tmp_path / "derived"
    entry = build_speaker(clips, "s02", dest, {"short": 1.0, "long": 3.0})
    assert entry["skipped_clips"] == {"s02a_0001": "empty audio"}
    short, long = entry["recordings"]["short"], entry["recordings"]["long"]
    assert short["clip_ids"] == ["s02a_0000"]
    assert long["clip_ids"] == ["s02a_0000", "s02a_0002", "s02b_0000"]
    assert long["duration_s"] == pytest.approx(3.75)
    # audio is the byte concatenation of the clips
    parts = b"".join(read_pcm(clips / f"{c}.wav")[1] for c in long["clip_ids"])
    assert read_pcm(dest / "long" / "s02_long.wav")[1] == parts
    # references are shifted by each clip's offset; the short recording is a prefix
    words = parse_buckeye_textgrid(dest / "long" / "s02_long.TextGrid")
    assert [w.text for w in words] == ["one", "two", "three", "four", "five", "six", "seven"]
    three = parse_buckeye_textgrid(clips / "s02a_0002.TextGrid")[0]
    assert words[2].start == pytest.approx(three.start + 1.0, abs=1e-6)
    assert words[5].phonemes[0].start == pytest.approx(
        parse_buckeye_textgrid(clips / "s02b_0000.TextGrid")[0].phonemes[0].start + 2.5, abs=1e-6
    )
    assert parse_buckeye_textgrid(dest / "short" / "s02_short.TextGrid") == words[:2]


def test_build_refuses_too_little_audio(clips: Path, tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="usable clips"):
        build_speaker(clips, "s03", tmp_path / "d", {"long": 5.0})


def test_null_transcriber_gives_proportional_placement_without_anchors() -> None:
    hyp = NullTranscriber().transcribe("any.wav")
    assert hyp == []
    res = anchor_transcript("aa bbbb aa bbbb", hyp, 12.0)
    assert res.n_anchors == 0
    assert res.words[0].start == 0.0 and res.words[-1].end == 12.0
    assert res.words[1].end - res.words[1].start == pytest.approx(4.0)


def test_word_errors_use_reference_positions() -> None:
    refs = [
        WordToken(f"r{i}", t, t, s, s + 0.2, 1.0) for i, (t, s) in enumerate([("a", 0), ("b", 1)])
    ]
    pred = [WordToken("p0", "b", "b", 1.01, 1.23, 1.0)]
    assert word_errors(pred, refs) == [(1, 1.0, pytest.approx(10.0), pytest.approx(30.0))]


def test_exact_test_matches_brute_force_including_ties() -> None:
    rng = np.random.default_rng(7)
    for n in (6, 9, 14):
        d = np.round(rng.normal(0.5, 2, n), 1).tolist() + [0.0]
        assert brute_force_p(d) == pytest.approx(exact_signed_rank(d)["p_value_raw"], abs=1e-12)
    assert brute_force_p([1.0] * 6) == pytest.approx(2 / 2**6)


def test_paired_test_excludes_missing_speakers_and_small_samples() -> None:
    base = {f"s{i:02d}": 10.0 for i in range(MIN_PAIRS)}
    cond = {k: 12.0 for k in base}
    full = paired_test(base, cond)
    assert full["testable"] and full["n_worse"] == MIN_PAIRS and full["excluded_speakers"] == []
    cond["s00"] = None
    small = paired_test(base, cond)
    assert not small["testable"] and small["excluded_speakers"] == ["s00"]


def test_max_deviation_rejects_label_changes_and_measures_time() -> None:
    from scripts.s1_long_recordings import max_deviation

    word = WordToken("w0", "a", "a", 1.0, 1.5, 1.0)
    assert max_deviation([word], [Interval(1.0, 1.5001, "a")], []) == pytest.approx(1e-4)
    assert max_deviation([word], [Interval(1.0, 1.5, "b")], []) == float("inf")
    assert max_deviation([word], [], []) == float("inf")


def test_isolating_aligner_records_chunking_errors_per_recording() -> None:
    from types import SimpleNamespace

    from scripts.s1_long_recordings import IsolatingAligner
    from subtitle_workbench.aligner import AlignmentFailure
    from subtitle_workbench.chunker import MonotonicityError

    class Inner:
        mfa_retries = ["kept"]

        def align_requests(self, requests, engine):
            if requests[0].audio_path == "bad.wav":
                raise MonotonicityError("Chronology corruption")
            if requests[0].audio_path == "crash.wav":
                raise RuntimeError("engine crash")
            return [["ok"]]

    aligner = IsolatingAligner(Inner())
    reqs = [SimpleNamespace(audio_path=p) for p in ("a.wav", "bad.wav", "b.wav")]
    out = aligner.align_requests(reqs, engine="ctc")
    assert out[0] == ["ok"] and out[2] == ["ok"] and isinstance(out[1], AlignmentFailure)
    assert aligner.isolated_failures[0]["audio"] == "bad.wav"
    assert aligner.mfa_retries == ["kept"]
    with pytest.raises(RuntimeError, match="engine crash"):
        aligner.align_requests([SimpleNamespace(audio_path="crash.wav")], engine="mfa")


def test_isolating_aligner_separates_no_alignments_from_mfa_crashes() -> None:
    from types import SimpleNamespace

    from scripts.s1_long_recordings import IsolatingAligner
    from subtitle_workbench.aligner import AlignmentFailure
    from subtitle_workbench.mfa_wrapper import MFAExecutionError

    class Inner:
        def align_requests(self, requests, engine):
            if requests[0].audio_path == "beam.wav":
                raise MFAExecutionError("exit code 1: ... NoAlignmentsError: no alignments")
            raise MFAExecutionError("exit code 3221226505: native crash")

    aligner = IsolatingAligner(Inner())
    out = aligner.align_requests([SimpleNamespace(audio_path="beam.wav")], engine="mfa")
    assert isinstance(out[0], AlignmentFailure)
    assert "NoAlignmentsError" in aligner.isolated_failures[0]["error"]
    with pytest.raises(MFAExecutionError, match="native crash"):
        aligner.align_requests([SimpleNamespace(audio_path="crash.wav")], engine="mfa")
