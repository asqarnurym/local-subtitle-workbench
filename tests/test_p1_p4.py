"""Tests for the P-1...P-4 exploratory analyses (scripts/p1_p4_analyses.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import p1_p4_analyses as p  # noqa: E402
from subtitle_workbench.models import WordToken  # noqa: E402
from subtitle_workbench.refiner import roc_auc  # noqa: E402


def w(i: int, text: str, start: float, end: float, conf: float = 1.0) -> WordToken:
    return WordToken(f"w{i}", text, text, start, end, conf)


def test_ref_matches_maps_reference_indices_across_insertions() -> None:
    ref = [w(0, "a", 0.0, 0.1), w(1, "b", 0.1, 0.2), w(2, "c", 0.2, 0.3)]
    pred = [w(0, "a", 0.0, 0.1), w(1, "x", 0.1, 0.15), w(2, "c", 0.2, 0.3)]
    m = p.ref_matches(pred, ref)
    assert sorted(m) == [0, 2]
    assert m[2][0] == 2


def test_boundary_errors_are_start_and_end_in_ms() -> None:
    ref = [w(0, "a", 1.0, 2.0)]
    pred = [w(0, "a", 1.01, 1.97)]
    assert np.allclose(p.boundary_errors_ms(pred, ref), [10.0, 30.0])


def test_auc_fast_matches_reference_with_ties() -> None:
    rng = np.random.default_rng(0)
    y = rng.random(500) < 0.3
    s = np.round(rng.random(500) + y * 0.3, 1)
    assert abs(p.auc_fast(y, s) - roc_auc(y, s)) < 1e-12


def test_percentile_rank_averages_ties() -> None:
    r = p.percentile_rank(np.array([1.0, 1.0, 3.0, 2.0]))
    assert np.allclose(r, [1.5 / 4, 1.5 / 4, 4 / 4, 3 / 4])


def test_snap_moves_boundary_to_flux_peak_and_keeps_order() -> None:
    times = np.arange(0.0, 1.0, 0.0025)
    flux = np.zeros_like(times)
    flux[np.argmin(np.abs(times - 0.512))] = 5.0
    words = [w(0, "a", 0.1, 0.5), w(1, "b", 0.5, 0.9)]
    out, _ = p.snap_words(words, times, flux, 0.02, 1.0)
    assert abs(out[0].end - 0.512) < 0.002
    assert out[0].end == out[1].start
    assert all(x.start < x.end for x in out)
    half, _ = p.snap_words(words, times, flux, 0.02, 0.5)
    assert abs(half[0].end - 0.506) < 0.002


def test_snap_outside_window_and_empty_flux_change_nothing() -> None:
    words = [w(0, "a", 0.1, 0.5)]
    times = np.array([0.8, 0.9])
    flux = np.array([1.0, 2.0])
    out, _ = p.snap_words(words, times, flux, 0.02, 1.0)
    assert (out[0].start, out[0].end) == (0.1, 0.5)
    out, _ = p.snap_words(words, np.zeros(0), np.zeros(0), 0.02, 1.0)
    assert (out[0].start, out[0].end) == (0.1, 0.5)


def test_snap_reverts_word_that_would_collapse() -> None:
    times = np.arange(0.0, 1.0, 0.0025)
    flux = np.zeros_like(times)
    flux[np.argmin(np.abs(times - 0.30))] = 5.0
    words = [w(0, "a", 0.29, 0.31)]
    out, _ = p.snap_words(words, times, flux, 0.02, 1.0)
    assert out[0].start < out[0].end


def test_spectral_flux_peaks_at_onset() -> None:
    x = np.zeros(p.SR, dtype=np.float32)
    x[p.SR // 2 :] = np.sin(2 * np.pi * 440 * np.arange(p.SR // 2) / p.SR)
    times, flux = p.spectral_flux(x)
    assert abs(times[int(np.argmax(flux))] - 0.5) < 0.03
    assert len(times) == len(flux)


def test_oracle_pair_is_never_worse_than_either_side() -> None:
    class U:
        def __init__(self, uid, spk, ref):
            self.id, self.speaker_id, self.ref_words = uid, spk, ref

    utts, preds = {}, {"c": {}, "m": {}}
    rng = np.random.default_rng(1)
    for k in range(12):
        uid = f"u{k}"
        ref = [w(i, f"t{i}", 0.1 + i * 0.3, 0.3 + i * 0.3) for i in range(5)]
        utts[uid] = U(uid, f"s{k % 6}", ref)
        for mode in ("c", "m"):
            preds[mode][uid] = [
                w(i, r.text, r.start + rng.normal(0, 0.02), r.end + rng.normal(0, 0.02) + 0.05)
                for i, r in enumerate(ref)
            ]
    ok = {"c": set(utts), "m": set(utts)}
    res = p.oracle_pair(utts, preds, ok, "c", "m")
    mae = res["pooled_mae_ms"]
    assert mae["oracle"] <= min(mae["mfa"], mae["ctc"]) + 1e-9
    assert res["share_of_mfa_boundaries_in_common_set"] == 1.0
