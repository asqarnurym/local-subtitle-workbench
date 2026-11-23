"""Tests for the boundary F1 analysis (scripts/f1_analysis.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import f1_analysis as f  # noqa: E402
from subtitle_workbench.models import WordToken  # noqa: E402


def w(i: int, text: str, start: float, end: float) -> WordToken:
    return WordToken(f"w{i}", text, text, start, end, 1.0)


REF = [w(0, "a", 0.10, 0.20), w(1, "b", 0.20, 0.30), w(2, "c", 0.30, 0.40)]


def test_perfect_prediction_scores_one() -> None:
    c = f.clip_counts(list(REF), REF)
    assert c == {"hits_edge20": 6, "hits_edge50": 6, "hits_ctx20": 6, "n_pred_bd": 6, "n_ref_bd": 6}
    assert f.f1_from(c, "hits_edge20")["f1"] == pytest.approx(1.0)


def test_failed_clip_misses_every_reference_boundary() -> None:
    c = f.clip_counts(None, REF)
    assert c["n_ref_bd"] == 6 and c["n_pred_bd"] == 0 and c["hits_edge20"] == 0
    total = f.add(f.add({}, f.clip_counts(list(REF), REF)), c)
    r = f.f1_from(total, "hits_edge20")
    assert r["recall"] == pytest.approx(0.5) and r["precision"] == pytest.approx(1.0)


def test_inserted_word_lowers_precision_only() -> None:
    pred = [REF[0], w(9, "x", 0.20, 0.21), REF[1], REF[2]]
    r = f.f1_from(f.clip_counts(pred, REF), "hits_edge20")
    assert r["recall"] == pytest.approx(1.0)
    assert r["precision"] == pytest.approx(6 / 8)


def test_misread_word_costs_its_boundaries_and_neighbour_context() -> None:
    pred = [REF[0], w(1, "z", 0.20, 0.30), REF[2]]
    c = f.clip_counts(pred, REF)
    assert c["hits_edge20"] == 4  # a and c keep both edges
    # a's end and c's start border the misread word, so context fails there
    assert c["hits_ctx20"] == 2


def test_tolerance_is_inclusive_and_fifty_counts_more() -> None:
    pred = [w(0, "a", 0.12, 0.20), w(1, "b", 0.24, 0.30), REF[2]]
    c = f.clip_counts(pred, REF)
    assert c["hits_edge20"] == 5  # 20 ms is a hit, 40 ms is not
    assert c["hits_edge50"] == 6


def test_speaker_bootstrap_is_deterministic_and_bounded() -> None:
    by = {
        f"s{i}": {
            "hits_edge20": 5 + i,
            "hits_edge50": 0,
            "hits_ctx20": 0,
            "n_pred_bd": 10,
            "n_ref_bd": 12,
        }
        for i in range(5)
    }
    a = f.speaker_bootstrap_f1(by, "hits_edge20")
    assert a == f.speaker_bootstrap_f1(by, "hits_edge20")
    assert 0.0 <= a[0] <= a[1] <= 1.0
