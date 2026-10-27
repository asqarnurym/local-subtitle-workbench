"""Adversarial stress-test suite for subtitle_workbench.metrics.

Authored by challenger_m1_2.
Verifies boundary evaluation, clustered bootstrap, paired Wilcoxon tests,
and empirically documents edge cases and failure modes.
"""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

from subtitle_workbench.metrics import (
    BoundaryEvaluation,
    MetricComputationError,
    WilcoxonTestResult,
    clustered_bootstrap_ci,
    evaluate_alignment_boundaries,
    paired_wilcoxon_test,
)
from subtitle_workbench.models import WordToken


def _make_tokens(
    count: int,
    start_offset: float = 0.0,
    duration: float = 0.5,
    gap: float = 0.1,
    shift_sec: float = 0.0,
) -> list[WordToken]:
    """Helper to generate sequential non-overlapping WordTokens."""
    tokens: list[WordToken] = []
    current = start_offset
    for i in range(count):
        s = current + shift_sec
        e = current + duration + shift_sec
        tokens.append(
            WordToken(
                id=f"w_{i:06d}",
                text="word",
                normalized="word",
                start=round(s, 6),
                end=round(e, 6),
                confidence=1.0,
            )
        )
        current += duration + gap
    return tokens


# ---------------------------------------------------------------------------
# 1. evaluate_alignment_boundaries Stress Tests
# ---------------------------------------------------------------------------


def test_evaluate_alignment_boundaries_empty_inputs() -> None:
    """Empty predicted tokens, empty reference tokens, or both must raise MetricComputationError."""
    token = WordToken(id="w0", text="hi", normalized="hi", start=0.0, end=0.5, confidence=1.0)

    # Empty prediction
    with pytest.raises(MetricComputationError, match="pred_tokens list is empty"):
        evaluate_alignment_boundaries([], [token])

    # Empty reference
    with pytest.raises(MetricComputationError, match="ref_tokens list is empty"):
        evaluate_alignment_boundaries([token], [])

    # Empty both
    with pytest.raises(MetricComputationError, match="pred_tokens list is empty"):
        evaluate_alignment_boundaries([], [])


def test_evaluate_alignment_boundaries_zero_duration() -> None:
    """Tokens with zero duration (start == end) must not crash boundary evaluation."""
    w_ref = WordToken(id="w0", text="a", normalized="a", start=1.0, end=1.5, confidence=1.0)
    w_pred = WordToken(id="w0", text="a", normalized="a", start=1.0, end=1.5, confidence=1.0)

    object.__setattr__(w_ref, "end", 1.0)
    object.__setattr__(w_pred, "end", 1.0)

    res = evaluate_alignment_boundaries([w_pred], [w_ref])
    assert isinstance(res, BoundaryEvaluation)
    assert res.mae == 0.0
    assert res.acc_20ms == 100.0


def test_evaluate_alignment_boundaries_extreme_discrepancy() -> None:
    """Extreme boundary discrepancies (1000s off) must compute without overflow."""
    ref = [WordToken(id="w0", text="test", normalized="test", start=0.0, end=0.5, confidence=1.0)]
    pred = [
        WordToken(id="w0", text="test", normalized="test", start=1000.0, end=1000.5, confidence=1.0)
    ]

    res = evaluate_alignment_boundaries(pred, ref)
    assert math.isclose(res.mae, 1_000_000.0, abs_tol=1e-3)
    assert res.acc_20ms == 0.0


def test_evaluate_alignment_boundaries_high_volume_100k() -> None:
    """Verify O(N) linear performance for 100,000 synthetic boundary tokens."""
    n = 100_000
    ref = _make_tokens(n, shift_sec=0.0)
    pred = _make_tokens(n, shift_sec=0.015)  # +15 ms shift

    t0 = time.perf_counter()
    res = evaluate_alignment_boundaries(pred, ref)
    elapsed = time.perf_counter() - t0

    assert res.num_matched == n
    assert res.num_unmatched == 0
    assert math.isclose(res.mae, 15.0, abs_tol=1e-4)
    assert math.isclose(res.acc_20ms, 100.0, abs_tol=1e-4)
    assert elapsed < 1.5, f"100k token evaluation took too long: {elapsed:.2f}s"


def test_evaluate_alignment_boundaries_distribution_accuracy() -> None:
    """Verify mathematical accuracy of MAE and Acc@20ms on constructed distribution."""
    # 5 tokens -> 10 boundaries:
    # 5.0, 15.0 (both <= 20ms) -> 2
    # 25.0, 45.0 (both <= 50ms) -> 2
    # 55.0, 75.0 (both <= 100ms) -> 2
    # 95.0, 99.9 (both <= 100ms) -> 2
    # 150.0, 300.0 (> 100ms) -> 2
    target_errors_ms = [5.0, 15.0, 25.0, 45.0, 55.0, 75.0, 95.0, 99.9, 150.0, 300.0]

    ref_tokens = []
    pred_tokens = []
    for idx in range(5):
        s_err = target_errors_ms[2 * idx] / 1000.0
        e_err = target_errors_ms[2 * idx + 1] / 1000.0
        base_s = float(idx * 2)
        base_e = base_s + 0.8
        ref_tokens.append(
            WordToken(
                id=f"w{idx}",
                text=f"w{idx}",
                normalized=f"w{idx}",
                start=base_s,
                end=base_e,
                confidence=1.0,
            )
        )
        pred_tokens.append(
            WordToken(
                id=f"w{idx}",
                text=f"w{idx}",
                normalized=f"w{idx}",
                start=round(base_s + s_err, 6),
                end=round(base_e + e_err, 6),
                confidence=1.0,
            )
        )

    res = evaluate_alignment_boundaries(pred_tokens, ref_tokens)
    assert math.isclose(res.acc_20ms, 20.0, abs_tol=1e-5)

    expected_mae = sum(target_errors_ms) / len(target_errors_ms)

    assert math.isclose(res.mae, expected_mae, abs_tol=1e-3)


def test_evaluate_alignment_boundaries_exact_sample_shift() -> None:
    """Exact 20.0ms shift (320 samples at 16kHz) at t=1.0s achieves Acc@20ms == 100.0%."""
    ref = WordToken(
        id="w0", text="w", normalized="w", start=16000 / 16000, end=24000 / 16000, confidence=1.0
    )
    # 320 samples at 16kHz is mathematically exactly 20.0 ms
    pred_20 = WordToken(
        id="w0", text="w", normalized="w", start=16320 / 16000, end=24320 / 16000, confidence=1.0
    )
    res_20 = evaluate_alignment_boundaries([pred_20], [ref])
    assert math.isclose(res_20.acc_20ms, 100.0, abs_tol=1e-5)


# ---------------------------------------------------------------------------
# 2. Clustered Bootstrap & Paired Wilcoxon Stress Tests
# ---------------------------------------------------------------------------


def test_clustered_bootstrap_reproducibility_and_variation() -> None:
    """Verify identical seed produces identical CI, while distinct seeds produce different CIs."""
    rng = np.random.default_rng(2026)
    clusters = np.repeat([f"speaker_{i}" for i in range(25)], 20)
    errors = rng.normal(loc=30.0, scale=8.0, size=len(clusters))

    ci_seed42_a = clustered_bootstrap_ci(errors, clusters, num_resamples=1000, seed=42)
    ci_seed42_b = clustered_bootstrap_ci(errors, clusters, num_resamples=1000, seed=42)
    ci_seed99 = clustered_bootstrap_ci(errors, clusters, num_resamples=1000, seed=99)

    assert ci_seed42_a == ci_seed42_b, "Identical seed did not produce identical CI!"
    assert ci_seed42_a != ci_seed99, "Different seeds produced identical CI unexpectedly!"
    assert ci_seed42_a[0] < ci_seed42_a[1], "Lower CI bound not strictly less than upper bound"


def test_paired_wilcoxon_identical_arrays() -> None:
    """Identical paired arrays yield Cliff's Delta == 0.0 and p-value == 1.0."""
    x = [5.0, 12.0, 18.0, 25.0, 40.0, 60.0]
    res = paired_wilcoxon_test(x, x)

    assert isinstance(res, WilcoxonTestResult)
    assert res.cliffs_delta == 0.0
    assert res.p_value == 1.0
    assert res.statistic == 0.0
    assert res.effect_size == "negligible"
    assert res.n_pairs == len(x)
    assert res.n_non_zero == 0


def test_paired_wilcoxon_completely_separated() -> None:
    """Completely separated distributions yield Cliff's Delta == 1.0 or -1.0."""
    high = [100.0, 110.0, 120.0, 130.0, 140.0, 150.0]
    low = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0]

    res_high_low = paired_wilcoxon_test(high, low)
    assert res_high_low.cliffs_delta == 1.0
    assert res_high_low.effect_size == "large"

    res_low_high = paired_wilcoxon_test(low, high)
    assert res_low_high.cliffs_delta == -1.0
    assert res_low_high.effect_size == "large"


def test_paired_wilcoxon_exact_null_symmetry_continuity_correction() -> None:
    """Perfect symmetry around zero has |W - mean| == 0 and evaluates to p-value == 1.0."""
    # 4 pairs with symmetric differences [+1, -1, +2, -2]
    # W+ = 1.5 + 3.5 = 5.0, W- = 1.5 + 3.5 = 5.0. W_stat = 5.0. mean_w = 4*5/4 = 5.0.
    # Deviation from mean is exactly 0.0. Under H0, p-value must be 1.0.
    base = [11.0, 9.0, 12.0, 8.0]
    prop = [10.0, 10.0, 10.0, 10.0]
    res = paired_wilcoxon_test(base, prop)
    assert math.isclose(res.p_value, 1.0, abs_tol=1e-5)
