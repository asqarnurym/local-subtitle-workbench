"""Tests for the FA-Bench-style re-analyses (scripts/fa_extras.py)."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import fa_extras as x  # noqa: E402
from subtitle_workbench.models import WordToken  # noqa: E402


def w(i: int, text: str, start: float, end: float) -> WordToken:
    return WordToken(f"w{i}", text, text, start, end, 1.0)


REF = [w(0, "a", 0.10, 0.20), w(1, "b", 0.20, 0.30), w(2, "c", 0.30, 0.40)]


def test_groups_for_perfect_prediction() -> None:
    b, s, n_pred = x.clip_boundaries(list(REF), REF)
    assert [g for g, _ in b] == ["M1B", "M2I", "M2I", "M2I", "M2I", "M1E"]
    assert n_pred == 6 and len(s) == 3
    assert all(e == pytest.approx(0.0) for _, e in b)


def test_groups_around_a_misread_word() -> None:
    pred = [REF[0], w(1, "z", 0.20, 0.30), REF[2]]
    b, s, _ = x.clip_boundaries(pred, REF)
    assert [g for g, _ in b] == ["M1B", "M1I", "M1I", "M1I", "M1I", "M1E"]
    assert math.isnan(b[2][1]) and math.isnan(b[3][1])  # the misread word's own edges
    assert len(s) == 2


def test_failed_clip_puts_everything_in_m0() -> None:
    b, s, n_pred = x.clip_boundaries(None, REF)
    assert [g for g, _ in b] == ["M0B", "M0I", "M0I", "M0I", "M0I", "M0E"]
    assert n_pred == 0 and s == []


def test_signed_and_duration_errors() -> None:
    pred = [w(0, "a", 0.05, 0.16), REF[1], REF[2]]
    _, s, _ = x.clip_boundaries(pred, REF)
    es, ee, ed = s[0]
    assert es == pytest.approx(-50.0) and ee == pytest.approx(-40.0) and ed == pytest.approx(10.0)


def test_within_treats_nan_as_miss_and_is_inclusive() -> None:
    got = x.within(np.array([20.0, 20.001, float("nan")]), 20)
    assert got.tolist() == [True, False, False]


def test_sweep_matches_hand_count() -> None:
    d = {
        "speakers": ["s0", "s1"],
        "err": np.array([5.0, 15.0, 45.0, float("nan")]),
        "spk_b": np.array([0, 0, 1, 1]),
        "n_pred": np.array([2.0, 2.0]),
    }
    out = x.sweep(d, x.draws(2))
    assert out["10"]["f1"] == pytest.approx(2 * 1 / (4 + 4))
    assert out["50"]["recall"] == pytest.approx(3 / 4)
