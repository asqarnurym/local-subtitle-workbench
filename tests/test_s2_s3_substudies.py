"""Tests for the S2/S3 sub-study wrappers (scripts/s2_s3_substudies.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import s2_s3_substudies as sub  # noqa: E402


def test_buckeye_selection_is_seeded_ten_per_test_speaker() -> None:
    ids = sub.s2_buckeye_ids()
    sample = set(json.loads((PROJECT_ROOT / sub.BUCKEYE_SAMPLE).read_text())["utterance_ids"])
    speakers = {i[:3] for i in ids}
    assert len(ids) == 10 * len(speakers) == 200 and set(ids) <= sample
    assert ids == sub.s2_buckeye_ids()


def test_timit_sample_indices_follow_the_tempo_map(tmp_path: Path) -> None:
    src, dst = tmp_path / "a.wrd", tmp_path / "b.wrd"
    src.write_text("0 3200 she\n3200 8000 had\n", encoding="utf-8")
    sub._scale_sample_file(src, dst, 1.25)
    assert dst.read_text(encoding="utf-8").split("\n")[:2] == ["0 2560 she", "2560 6400 had"]


def _rows(mode: str, maes: dict[str, list[float | None]]) -> list[dict]:
    return [
        {
            "mode": mode,
            "speaker": s,
            "word_mae_ms": v,
            "word_acc_20ms": None if v is None else 0.5,
            "word_matched": 0 if v is None else 4,
            "word_reference": 5,
        }
        for s, vals in maes.items()
        for v in vals
    ]


def test_summary_is_speaker_level_with_coverage_and_failures() -> None:
    got = sub.summarize_rows(_rows("A2_proposed", {"s01": [10.0, 20.0], "s02": [30.0, None]}))
    m = got["A2_proposed"]
    assert m["speaker_mae_ms"] == {"s01": 15.0, "s02": 30.0}
    assert m["mean_speaker_mae_ms"] == 22.5 and m["n_failed"] == 1
    assert m["word_coverage"] == 12 / 20


def test_holm_is_monotone_and_skips_missing() -> None:
    adj = sub.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": None})
    assert adj["d"] is None
    assert adj["a"] == 0.03 and adj["c"] == 0.06 and adj["b"] == 0.06


def test_compare_pairs_speakers_against_the_base() -> None:
    spk = {f"s{i:02d}": [10.0 + i] for i in range(10)}
    worse = {f"s{i:02d}": [12.0 + i] for i in range(10)}
    base = sub.summarize_rows(_rows("B2_proposed", spk))
    conds = {"slow": sub.summarize_rows(_rows("B2_proposed", worse))}
    tests = sub.compare(base, conds, ["B2_proposed", "A2_proposed"])
    t = tests["B2_proposed"]["slow"]
    assert t["n_pairs"] == 10 and t["mean_difference_ms"] == 2.0 and t["n_worse"] == 10
    assert t["p_value_holm"] == t["p_value_raw"] < 0.01
    assert "A2_proposed" not in tests
