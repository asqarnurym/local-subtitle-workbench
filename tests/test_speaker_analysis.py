"""Exact sign-rank inference and speaker bootstrap must respect their sampling units."""

import itertools
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.analyze_speaker_errors import (  # noqa: E402
    descriptive,
    exact_signed_rank,
    tier_summary,
)
from subtitle_workbench.metrics import clustered_bootstrap_ci  # noqa: E402


@pytest.mark.parametrize("d", [[1, 1, -2, 2], [0, 1, -1, 3], [1, 2, 3], [0, 0]])
def test_exact_signed_rank_against_exhaustive_signs(d):
    a = np.abs(np.array([v for v in d if v], dtype=float))
    ranks = np.array(
        [1 + np.count_nonzero(a < v) + 0.5 * (np.count_nonzero(a == v) - 1) for v in a]
    )
    observed = sum(rank for rank, v in zip(ranks, [v for v in d if v], strict=True) if v > 0)
    observed = min(observed, ranks.sum() - observed)
    null = [
        min(
            sum(r for r, bit in zip(ranks, bits, strict=True) if bit),
            sum(r for r, bit in zip(ranks, bits, strict=True) if not bit),
        )
        for bits in itertools.product([0, 1], repeat=len(a))
    ]
    assert exact_signed_rank(d)["p_value_raw"] == sum(v <= observed for v in null) / len(null)


def test_twenty_uniform_improvements_have_exact_nonzero_p_value():
    assert exact_signed_rank(range(1, 21))["p_value_raw"] == 2 / 2**20


def test_empty_descriptive_bin_is_retained_without_invented_metrics():
    assert descriptive([]) == {
        "n_boundaries": 0,
        "mae_ms": None,
        "mean_signed_error_ms": None,
        "acc_20ms": None,
    }


def test_bootstrap_ratio_matches_resampling_whole_unequal_speakers():
    errors, speakers = [0.0, 10.0, 20.0, 100.0], ["a", "a", "a", "b"]
    summary = tier_summary(errors, speakers, resamples=100, seed=42)
    assert np.allclose(
        summary["mae_ci_95_ms"],
        clustered_bootstrap_ci(errors, speakers, num_resamples=100, seed=42),
        rtol=0,
        atol=1e-12,
    )
    expected = np.array(
        clustered_bootstrap_ci(
            100.0 * (np.array(errors) <= 20.0001), speakers, num_resamples=100, seed=42
        )
    )
    assert np.allclose(summary["acc_20ms_ci_95"], expected, rtol=0, atol=1e-12)
