"""Empirical alignment benchmark metrics and statistical analysis module.

Provides boundary evaluation metrics (MAE, MedAE, RMSE, Acc@20ms/50ms/100ms),
clustered bootstrap confidence intervals for speaker/utterance correlation,
and paired non-parametric hypothesis testing (Wilcoxon signed-rank, Cliff's Delta).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .models import PhonemeCue, WordToken, finite_number


class BenchmarkError(Exception):
    """Base exception for speech benchmark operations."""


class CorpusFormatError(BenchmarkError):
    """Raised when speech corpus files are malformed or non-monotonic."""


class MetricComputationError(BenchmarkError):
    """Raised when metric computation encounters invalid or empty inputs."""


BOUNDARY_EPSILON_MS: float = 1e-4


@dataclass(frozen=True)
class BoundaryEvaluation:
    """Evaluation metrics for a single boundary tier (words or phonemes)."""

    mae: float
    medae: float
    rmse: float
    acc_20ms: float
    acc_50ms: float
    acc_100ms: float
    boundary_errors_ms: list[float]
    num_matched: int
    num_unmatched: int
    tolerance_ms: float = 20.0

    def __post_init__(self) -> None:
        mae = finite_number(self.mae, "mae")
        medae = finite_number(self.medae, "medae")
        rmse = finite_number(self.rmse, "rmse")
        acc_20 = finite_number(self.acc_20ms, "acc_20ms")
        acc_50 = finite_number(self.acc_50ms, "acc_50ms")
        acc_100 = finite_number(self.acc_100ms, "acc_100ms")
        tol = finite_number(self.tolerance_ms, "tolerance_ms")
        if mae < 0.0 or medae < 0.0 or rmse < 0.0:
            raise ValueError("Error metrics must be non-negative")
        for name, val in (("acc_20ms", acc_20), ("acc_50ms", acc_50), ("acc_100ms", acc_100)):
            if not (0.0 <= val <= 100.0):
                raise ValueError(f"{name} must be between 0.0 and 100.0")
        if not isinstance(self.boundary_errors_ms, list):
            raise ValueError("boundary_errors_ms must be a list of float errors")
        if not isinstance(self.num_matched, int) or self.num_matched < 0:
            raise ValueError("num_matched must be a non-negative integer")
        if not isinstance(self.num_unmatched, int) or self.num_unmatched < 0:
            raise ValueError("num_unmatched must be a non-negative integer")
        object.__setattr__(self, "mae", mae)
        object.__setattr__(self, "medae", medae)
        object.__setattr__(self, "rmse", rmse)
        object.__setattr__(self, "acc_20ms", acc_20)
        object.__setattr__(self, "acc_50ms", acc_50)
        object.__setattr__(self, "acc_100ms", acc_100)
        object.__setattr__(self, "tolerance_ms", tol)


@dataclass(frozen=True)
class WilcoxonTestResult:
    """Paired Wilcoxon signed-rank test and Cliff's Delta effect size result."""

    statistic: float
    p_value: float
    cliffs_delta: float
    effect_size: str
    n_pairs: int
    n_non_zero: int = 0

    def __post_init__(self) -> None:
        stat = finite_number(self.statistic, "statistic")
        pval = finite_number(self.p_value, "p_value")
        delta = finite_number(self.cliffs_delta, "cliffs_delta")
        if stat < 0.0:
            raise ValueError("statistic must be non-negative")
        if not (0.0 <= pval <= 1.0):
            raise ValueError("p_value must be between 0.0 and 1.0")
        if not (-1.0 <= delta <= 1.0):
            raise ValueError("cliffs_delta must be between -1.0 and 1.0")
        if self.effect_size not in ("negligible", "small", "medium", "large"):
            raise ValueError(f"Unknown effect size category: {self.effect_size}")
        object.__setattr__(self, "statistic", stat)
        object.__setattr__(self, "p_value", pval)
        object.__setattr__(self, "cliffs_delta", delta)


@dataclass(frozen=True)
class AlignmentEvaluationResult:
    """Full alignment evaluation result with word/phone metrics and hardware profiling."""

    word_metrics: BoundaryEvaluation
    phone_metrics: BoundaryEvaluation | None = None
    rtf: float = 0.0
    peak_vram_mb: float = 0.0
    peak_ram_mb: float = 0.0
    bootstrap_ci_95: dict[str, tuple[float, float]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.word_metrics, BoundaryEvaluation):
            raise ValueError("word_metrics must be an instance of BoundaryEvaluation")
        if self.phone_metrics is not None and not isinstance(
            self.phone_metrics, BoundaryEvaluation
        ):
            raise ValueError("phone_metrics must be None or an instance of BoundaryEvaluation")
        rtf = finite_number(self.rtf, "rtf")
        vram = finite_number(self.peak_vram_mb, "peak_vram_mb")
        ram = finite_number(self.peak_ram_mb, "peak_ram_mb")
        if rtf < 0.0 or vram < 0.0 or ram < 0.0:
            raise ValueError("Resource metrics must be non-negative")
        object.__setattr__(self, "rtf", rtf)
        object.__setattr__(self, "peak_vram_mb", vram)
        object.__setattr__(self, "peak_ram_mb", ram)

    def to_dict(self) -> dict[str, Any]:
        """Convert evaluation result to JSON-serializable dictionary."""
        return {
            "word_mae": self.word_metrics.mae,
            "word_medae": self.word_metrics.medae,
            "word_rmse": self.word_metrics.rmse,
            "word_acc_20ms": self.word_metrics.acc_20ms,
            "word_acc_50ms": self.word_metrics.acc_50ms,
            "word_acc_100ms": self.word_metrics.acc_100ms,
            "phone_mae": self.phone_metrics.mae if self.phone_metrics else None,
            "phone_medae": self.phone_metrics.medae if self.phone_metrics else None,
            "phone_rmse": self.phone_metrics.rmse if self.phone_metrics else None,
            "phone_acc_20ms": self.phone_metrics.acc_20ms if self.phone_metrics else None,
            "phone_acc_50ms": self.phone_metrics.acc_50ms if self.phone_metrics else None,
            "phone_acc_100ms": self.phone_metrics.acc_100ms if self.phone_metrics else None,
            "rtf": self.rtf,
            "peak_vram_mb": self.peak_vram_mb,
            "peak_ram_mb": self.peak_ram_mb,
            "bootstrap_ci_95": {k: [v[0], v[1]] for k, v in self.bootstrap_ci_95.items()},
            "metadata": self.metadata,
        }


def _token_key(token: WordToken | PhonemeCue) -> str:
    """Extract normalized text or phoneme label for sequence matching."""
    if isinstance(token, WordToken):
        return (token.normalized or token.text).strip().lower()
    if isinstance(token, PhonemeCue):
        return token.phoneme.strip().lower()
    raise MetricComputationError(f"Unsupported token type: {type(token).__name__}")


def _align_token_sequences(
    pred_tokens: list[WordToken] | list[PhonemeCue],
    ref_tokens: list[WordToken] | list[PhonemeCue],
) -> tuple[list[tuple[WordToken | PhonemeCue, WordToken | PhonemeCue]], int]:
    """Pair matching tokens between prediction and reference via 1-to-1 or Needleman-Wunsch."""
    n = len(pred_tokens)
    m = len(ref_tokens)

    pred_keys = [_token_key(t) for t in pred_tokens]
    ref_keys = [_token_key(t) for t in ref_tokens]

    # Fast path: identical length and identical keys
    if n == m and pred_keys == ref_keys:
        return list(zip(pred_tokens, ref_tokens, strict=True)), 0

    # Dynamic programming sequence alignment (Needleman-Wunsch)
    # Match reward = +2, Mismatch penalty = -2, Gap penalty = -1
    score = np.zeros((n + 1, m + 1), dtype=np.int32)
    for i in range(1, n + 1):
        score[i, 0] = score[i - 1, 0] - 1
    for j in range(1, m + 1):
        score[0, j] = score[0, j - 1] - 1

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if pred_keys[i - 1] == ref_keys[j - 1]:
                diag = score[i - 1, j - 1] + 2
            else:
                diag = score[i - 1, j - 1] - 2
            up = score[i - 1, j] - 1
            left = score[i, j - 1] - 1
            score[i, j] = max(diag, up, left)

    # Backtrace
    i, j = n, m
    matched_pairs: list[tuple[WordToken | PhonemeCue, WordToken | PhonemeCue]] = []
    unmatched = 0

    while i > 0 and j > 0:
        if pred_keys[i - 1] == ref_keys[j - 1] and score[i, j] == score[i - 1, j - 1] + 2:
            matched_pairs.append((pred_tokens[i - 1], ref_tokens[j - 1]))
            i -= 1
            j -= 1
        elif score[i, j] == score[i - 1, j] - 1:
            unmatched += 1
            i -= 1
        elif score[i, j] == score[i, j - 1] - 1:
            unmatched += 1
            j -= 1
        else:
            # Mismatch substitution
            unmatched += 2
            i -= 1
            j -= 1

    unmatched += i + j
    matched_pairs.reverse()
    return matched_pairs, unmatched


def evaluate_alignment_boundaries(
    pred_tokens: list[WordToken] | list[PhonemeCue],
    ref_tokens: list[WordToken] | list[PhonemeCue],
    tolerance_ms: float = 20.0,
) -> BoundaryEvaluation:
    """Evaluate start and end boundary absolute errors in milliseconds."""
    if not isinstance(pred_tokens, list) or not isinstance(ref_tokens, list):
        raise MetricComputationError("pred_tokens and ref_tokens must be lists")
    if len(pred_tokens) == 0:
        raise MetricComputationError("pred_tokens list is empty")
    if len(ref_tokens) == 0:
        raise MetricComputationError("ref_tokens list is empty")
    if tolerance_ms <= 0.0 or not math.isfinite(tolerance_ms):
        raise MetricComputationError("tolerance_ms must be positive and finite")

    matched_pairs, num_unmatched = _align_token_sequences(pred_tokens, ref_tokens)

    if not matched_pairs:
        raise MetricComputationError("Zero matching tokens found between prediction and reference")

    boundary_errors: list[float] = []
    for pred, ref in matched_pairs:
        start_err = abs(pred.start - ref.start) * 1000.0
        end_err = abs(pred.end - ref.end) * 1000.0
        boundary_errors.append(start_err)
        boundary_errors.append(end_err)

    errors = np.asarray(boundary_errors, dtype=np.float64)
    mae = float(np.mean(errors))
    medae = float(np.median(errors))
    rmse = float(np.sqrt(np.mean(errors**2)))
    acc_20 = float(np.mean(errors <= (20.0 + BOUNDARY_EPSILON_MS)) * 100.0)
    acc_50 = float(np.mean(errors <= (50.0 + BOUNDARY_EPSILON_MS)) * 100.0)
    acc_100 = float(np.mean(errors <= (100.0 + BOUNDARY_EPSILON_MS)) * 100.0)

    return BoundaryEvaluation(
        mae=mae,
        medae=medae,
        rmse=rmse,
        acc_20ms=acc_20,
        acc_50ms=acc_50,
        acc_100ms=acc_100,
        boundary_errors_ms=[float(x) for x in boundary_errors],
        num_matched=len(matched_pairs),
        num_unmatched=num_unmatched,
        tolerance_ms=float(tolerance_ms),
    )


def clustered_bootstrap_ci(
    errors: Sequence[float] | np.ndarray,
    clusters: Sequence[str | int] | np.ndarray,
    num_resamples: int = 2000,
    alpha: float = 0.05,
    seed: int = 42,
    statistic_fn: Callable[[np.ndarray], float] = np.mean,
) -> tuple[float, float]:
    """Compute cluster-robust bootstrap confidence interval (e.g. by speaker or utterance)."""
    err_arr = np.asarray(errors, dtype=np.float64)
    clust_arr = np.asarray(clusters)

    if err_arr.ndim != 1 or clust_arr.ndim != 1:
        raise MetricComputationError("errors and clusters must be 1D arrays")
    if len(err_arr) != len(clust_arr):
        raise MetricComputationError("errors and clusters must have identical length")
    if len(err_arr) == 0:
        raise MetricComputationError("errors array is empty")
    if not (0.0 < alpha < 1.0):
        raise MetricComputationError("alpha must be in (0.0, 1.0)")
    if num_resamples <= 0:
        raise MetricComputationError("num_resamples must be positive")

    unique_clusters = np.unique(clust_arr)
    k = len(unique_clusters)
    if k < 2:
        raise MetricComputationError("Clustered bootstrap requires at least 2 distinct clusters")

    # Group errors by cluster
    cluster_errors = [err_arr[clust_arr == c] for c in unique_clusters]

    rng = np.random.default_rng(seed)
    sampled_indices = rng.integers(0, k, size=(num_resamples, k))

    replicates = np.empty(num_resamples, dtype=np.float64)
    for b in range(num_resamples):
        chosen = [cluster_errors[idx] for idx in sampled_indices[b]]
        concat_sample = np.concatenate(chosen)
        replicates[b] = float(statistic_fn(concat_sample))

    lower_p = 100.0 * (alpha / 2.0)
    upper_p = 100.0 * (1.0 - alpha / 2.0)
    ci_lower = float(np.percentile(replicates, lower_p))
    ci_upper = float(np.percentile(replicates, upper_p))

    return ci_lower, ci_upper


def _cliffs_delta(x: np.ndarray, y: np.ndarray) -> tuple[float, str]:
    """Compute Cliff's Delta effect size in O((N+M)log(N+M)) time using Mann-Whitney U."""
    n = len(x)
    m = len(y)
    if n == 0 or m == 0:
        return 0.0, "negligible"

    # Combine and rank
    combined = np.concatenate([x, y])
    sort_order = np.argsort(combined)
    sorted_comb = combined[sort_order]
    ranks = np.empty(len(combined), dtype=np.float64)

    i = 0
    while i < len(sorted_comb):
        j = i
        while j < len(sorted_comb) and sorted_comb[j] == sorted_comb[i]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        ranks[i:j] = avg_rank
        i = j

    orig_ranks = np.empty_like(ranks)
    orig_ranks[sort_order] = ranks

    rank_x = np.sum(orig_ranks[:n])
    u_x = rank_x - (n * (n + 1)) / 2.0
    delta = float((2.0 * u_x) / (n * m) - 1.0)
    delta = max(-1.0, min(1.0, delta))

    abs_delta = abs(delta)
    if abs_delta < 0.147:
        category = "negligible"
    elif abs_delta < 0.330:
        category = "small"
    elif abs_delta < 0.474:
        category = "medium"
    else:
        category = "large"

    return delta, category


def _standard_normal_cdf(x: float) -> float:
    """Compute standard normal cumulative distribution function via math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def paired_wilcoxon_test(
    errors_baseline: Sequence[float] | np.ndarray,
    errors_proposed: Sequence[float] | np.ndarray,
) -> WilcoxonTestResult:
    """Perform tie-adjusted paired Wilcoxon signed-rank test and Cliff's Delta."""
    x = np.asarray(errors_baseline, dtype=np.float64)
    y = np.asarray(errors_proposed, dtype=np.float64)

    if x.ndim != 1 or y.ndim != 1:
        raise MetricComputationError("errors_baseline and errors_proposed must be 1D arrays")
    if len(x) != len(y):
        raise MetricComputationError("Input error arrays must have identical length")
    if len(x) == 0:
        raise MetricComputationError("Input error arrays are empty")

    n_pairs = len(x)
    diffs = x - y
    non_zero = diffs[diffs != 0.0]
    n_r = len(non_zero)

    cliffs_d, effect_sz = _cliffs_delta(x, y)

    if n_r == 0:
        return WilcoxonTestResult(
            statistic=0.0,
            p_value=1.0,
            cliffs_delta=0.0,
            effect_size="negligible",
            n_pairs=n_pairs,
            n_non_zero=0,
        )

    abs_diffs = np.abs(non_zero)
    sort_idx = np.argsort(abs_diffs)
    sorted_abs = abs_diffs[sort_idx]
    sorted_diffs = non_zero[sort_idx]

    ranks = np.empty(n_r, dtype=np.float64)
    tie_counts: list[int] = []

    i = 0
    while i < n_r:
        j = i
        while j < n_r and sorted_abs[j] == sorted_abs[i]:
            j += 1
        t_k = j - i
        if t_k > 1:
            tie_counts.append(t_k)
        avg_rank = (i + 1 + j) / 2.0
        ranks[i:j] = avg_rank
        i = j

    w_plus = float(np.sum(ranks[sorted_diffs > 0]))
    w_minus = float(np.sum(ranks[sorted_diffs < 0]))
    w_stat = min(w_plus, w_minus)

    # Variance with tie correction
    mean_w = (n_r * (n_r + 1)) / 4.0
    tie_term = sum((t**3 - t) for t in tie_counts) / 48.0
    var_w = (n_r * (n_r + 1) * (2 * n_r + 1)) / 24.0 - tie_term

    if var_w <= 0.0:
        p_val = 1.0
    else:
        # Continuity-corrected z-score with non-negative deviation clamp
        deviation = max(0.0, abs(w_stat - mean_w) - 0.5)
        z = deviation / math.sqrt(var_w) if var_w > 0.0 else 0.0
        # Two-sided p-value via math.erf
        p_val = 2.0 * (1.0 - _standard_normal_cdf(abs(z)))
        p_val = max(0.0, min(1.0, float(p_val)))

    return WilcoxonTestResult(
        statistic=w_stat,
        p_value=p_val,
        cliffs_delta=cliffs_d,
        effect_size=effect_sz,
        n_pairs=n_pairs,
        n_non_zero=n_r,
    )


def bonferroni_holm_adjustment(p_values: Sequence[float]) -> list[float]:
    """Apply the Bonferroni-Holm (Holm 1979) step-down multiple comparison adjustment.

    Controls the Family-Wise Error Rate (FWER) under arbitrary dependence.
    Given m hypothesis tests with unadjusted p-values:
    1. Sort p-values in ascending order: p_(1) <= p_(2) <= ... <= p_(m).
    2. Adjusted p-values: p'_(i) = min(1.0, max(p'_(i-1), (m - i + 1) * p_(i))),
       with p'_(1) = min(1.0, m * p_(1)).
    3. Restore original input ordering.
    """
    m = len(p_values)
    if m == 0:
        return []

    # Validate inputs
    for idx, p in enumerate(p_values):
        val = finite_number(p, f"p_values[{idx}]")
        if not (0.0 <= val <= 1.0):
            raise ValueError(f"p_value at index {idx} must be between 0.0 and 1.0, got {p}")

    # Indexed sort
    sorted_indices = sorted(range(m), key=lambda i: p_values[i])
    adjusted_sorted = [0.0] * m

    running_max = 0.0
    for rank_idx, orig_idx in enumerate(sorted_indices):
        # rank_idx is 0-based, multiplier is (m - rank_idx)
        mult = m - rank_idx
        adj_val = min(1.0, mult * float(p_values[orig_idx]))
        running_max = max(running_max, adj_val)
        adjusted_sorted[rank_idx] = running_max

    # Restore original ordering
    result = [0.0] * m
    for rank_idx, orig_idx in enumerate(sorted_indices):
        result[orig_idx] = adjusted_sorted[rank_idx]

    return result
