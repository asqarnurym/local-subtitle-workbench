# Analysis: Alignment Metrics and Statistical Analysis Module (Requirement R2)

Date: 2026-10-26
Agent: explorer_inc6_2
Scope: Mathematical, statistical, and architectural survey for src/subtitle_workbench/metrics.py

---

## 1. Executive Summary

Requirement R2 of Increment 6 introduces the empirical evaluation and statistical validation core for the "Local Subtitle Alignment Workbench" project. This module (src/subtitle_workbench/metrics.py) evaluates boundary precision against phonetic and word ground truth, quantifies speaker-level uncertainty via clustered bootstrap confidence intervals, and performs paired non-parametric hypothesis testing (Wilcoxon signed-rank test with Cliff's Delta effect size) to evaluate proposed hybrid alignment against Whisper baseline and CTC Trellis.

Key Architectural Decisions:
1. Pure NumPy and Standard Library Implementation: The project environment does not include SciPy (ModuleNotFoundError on `import scipy`). Base packaging constraints require the workbench to remain lightweight and runnable offline on CPU in < 5 seconds. All statistical algorithms (Wilcoxon signed-rank test, tie-aware ranking, Gaussian CDF via math.erf, Cliff's Delta, and Clustered Bootstrap) can and must be implemented natively in pure NumPy and standard library.
2. Dual Boundary Precision Accounting: Each aligned token contributes two distinct boundary errors: start boundary |t_pred_start - t_ref_start| and end boundary |t_pred_end - t_ref_end|, scaled to milliseconds (ms).
3. Robust Sequence Alignment: Token matching provides a fast 1-to-1 path for identical word transcripts (forced alignment modes) and a dynamic programming Needleman-Wunsch fallback to handle insertions, deletions, and substitutions (Whisper baseline mode).
4. Deterministic Clustered Bootstrap: Resampling entire speaker/utterance clusters with replacement prevents variance underestimation due to intra-speaker correlation. Pre-vectorized execution of 2000 resamples runs in < 20 ms.
5. Strict Division-by-Zero and Contract Protection: Defensively validates inputs via models.finite_number, preventing NaN/inf propagation, and raises typed exceptions (BenchmarkError, CorpusFormatError, MetricComputationError).

---

## 2. Dependency Audit and Environment Constraints

### 2.1 Inspection of pyproject.toml
```toml
[project]
dependencies = ["numpy>=2.1,<3"]

[project.optional-dependencies]
speech = [
    "faster-whisper>=1.0.0",
    "torch>=2.2.0",
]

[dependency-groups]
dev = ["pytest>=8.3,<9", "ruff>=0.11,<1", "build>=1.2,<2", "hatchling==1.32.4"]
```

Observations:
- `scipy` is NOT listed in `project.dependencies`, `optional-dependencies`, or `dependency-groups`.
- Direct execution test: `uv run python -c "import scipy"` raises `ModuleNotFoundError: No module named 'scipy'`.
- Running `uv run --locked pytest` succeeds with 637 passed, 1 skipped (test_asr.py skips because faster-whisper is an optional dependency).
- Adding `scipy` to pyproject.toml would invalidate `uv.lock` or violate the requirement that the base package remain lightweight without external scientific bloat.

Conclusion on Dependencies:
- All statistical routines in `src/subtitle_workbench/metrics.py` MUST be implemented in pure NumPy (>= 2.1) and Python standard library (`math`, `typing`, `dataclasses`, `collections`, `random`).
- An optional delegation to `scipy.stats.wilcoxon` can be guarded by a `try ... except ImportError` block, but the primary, fully-tested implementation must be self-contained in pure NumPy + stdlib.

---

## 3. Data Contracts and Exception Hierarchy

### 3.1 Exception Hierarchy
In accordance with ECC Error Handling standards:
```
Exception
  └── BenchmarkError
        ├── CorpusFormatError
        └── MetricComputationError
```

Definitions:
- `BenchmarkError(Exception)`: Root exception for all speech benchmark, boundary evaluation, and statistical analysis operations.
- `CorpusFormatError(BenchmarkError)`: Raised when reference corpus files (TIMIT .phn, TIMIT .wrd, Buckeye Praat TextGrid) are malformed, missing required tiers, or have unparseable timestamps.
- `MetricComputationError(BenchmarkError)`: Raised when metric computation encounters invalid inputs (e.g. empty token lists, mismatched array lengths, negative tolerances, or zero matched boundaries).

### 3.2 Dataclass AlignmentEvaluationResult
An immutable, frozen dataclass capturing comprehensive evaluation results across word and phoneme tiers, runtime resource metrics, and confidence intervals:

```python
@dataclass(frozen=True)
class AlignmentEvaluationResult:
    # Word-level accuracy metrics (in milliseconds or percent)
    word_mae: float
    word_medae: float
    word_rmse: float
    word_acc_20ms: float
    word_acc_50ms: float
    word_acc_100ms: float

    # Phoneme-level accuracy metrics (in milliseconds or percent)
    phone_mae: float
    phone_medae: float
    phone_rmse: float
    phone_acc_20ms: float
    phone_acc_50ms: float
    phone_acc_100ms: float

    # Computational efficiency metrics
    rtf: float  # Real-Time Factor: audio_duration / processing_time
    peak_vram_mb: float  # Peak GPU memory allocated in MB (0.0 if CPU)
    peak_ram_mb: float = 0.0  # Peak host RAM in MB

    # 95% Confidence Intervals mapping metric_name -> (ci_lower, ci_upper)
    bootstrap_ci_95: dict[str, tuple[float, float]] = field(default_factory=dict)

    # Metadata and sample counts
    evaluated_words: int = 0
    evaluated_phones: int = 0
    total_audio_duration_sec: float = 0.0
    method: str = ""
    corpus: str = ""
```

Invariants and Validation:
- All float metrics are validated via `finite_number` helper from `models.py`.
- Error metrics (`mae`, `medae`, `rmse`) must be non-negative: `>= 0.0`.
- Accuracy metrics (`acc_20ms`, `acc_50ms`, `acc_100ms`) must satisfy: `0.0 <= acc <= 100.0`.
- `rtf` and `peak_vram_mb` must be non-negative: `>= 0.0`.
- Immutability enforced through `frozen=True` and assignment via `object.__setattr__` in `__post_init__`.
- Serializability: provides `to_dict() -> dict[str, Any]` and `from_dict(data: dict[str, Any]) -> AlignmentEvaluationResult` for clean JSON ingestion in `scripts/speech_benchmark.py` and `scripts/generate_paper_tables.py`.

### 3.3 Dataclass BoundaryEvaluation
For single-tier boundary evaluations (either words or phonemes):

```python
@dataclass(frozen=True)
class BoundaryEvaluation:
    mae: float
    medae: float
    rmse: float
    acc_20ms: float
    acc_50ms: float
    acc_100ms: float
    acc_tolerance: float
    tolerance_ms: float
    boundary_count: int
    matched_tokens: int
    errors: np.ndarray  # Shape (boundary_count,), errors in milliseconds
    start_errors: np.ndarray  # Shape (matched_tokens,), start errors in ms
    end_errors: np.ndarray  # Shape (matched_tokens,), end errors in ms
```

### 3.4 Dataclass WilcoxonTestResult
```python
@dataclass(frozen=True)
class WilcoxonTestResult:
    statistic: float  # W-statistic (min(W+, W-))
    p_value: float  # Two-sided p-value
    cliffs_delta: float  # Cliff's Delta effect size [-1.0, 1.0]
    effect_size: (
        str  # "negligible" (< 0.147), "small" (< 0.33), "medium" (< 0.474), "large" (>= 0.474)
    )
    n_pairs: int  # Total number of pairs evaluated
    n_non_zero: int  # Number of non-zero differences
```

---

## 4. Boundary Comparison and Matching Mathematics

### 4.1 Boundary Error Equations
Let a matched pair of predicted token $P$ and reference token $R$ have time boundaries in seconds:
- $P = (t_{P, start}, t_{P, end})$
- $R = (t_{R, start}, t_{R, end})$

The absolute boundary errors in milliseconds are:
$$e_{start} = |t_{P, start} - t_{R, start}| \times 1000.0$$
$$e_{end} = |t_{P, end} - t_{R, end}| \times 1000.0$$

Each matched token contributes two boundary errors:
$E = \{ e_{start, 1}, e_{end, 1}, e_{start, 2}, e_{end, 2}, \dots, e_{start, K}, e_{end, K} \}$
where $K$ is the number of matched tokens, resulting in $M = 2K$ total boundary evaluation points.

### 4.2 Aggregation Metrics
1. Mean Absolute Error (MAE):
   $$\text{MAE} = \frac{1}{M} \sum_{m=1}^M e_m$$
2. Median Absolute Error (MedAE):
   $$\text{MedAE} = \text{median}(E)$$
3. Root Mean Square Error (RMSE):
   $$\text{RMSE} = \sqrt{\frac{1}{M} \sum_{m=1}^M e_m^2}$$
4. Accuracy at tolerance $\tau$ ms ($\text{Acc@}\tau\text{ms}$):
   $$\text{Acc@}\tau\text{ms} = \frac{1}{M} \sum_{m=1}^M \mathbb{I}(e_m \le \tau) \times 100.0$$
   Standard tolerances: $\tau \in \{20.0, 50.0, 100.0\}$ ms.

### 4.3 Theoretical Verification on Oracle Offsets
Applying fixed temporal shift $\Delta t$ to reference boundaries:
- Offset $\Delta t = +15$ ms:
  All $e_m = 15.0$ ms.
  MAE = 15.0 ms, MedAE = 15.0 ms, RMSE = 15.0 ms.
  Acc@20ms = 100.0%, Acc@50ms = 100.0%, Acc@100ms = 100.0%.
- Offset $\Delta t = +25$ ms:
  All $e_m = 25.0$ ms.
  MAE = 25.0 ms, MedAE = 25.0 ms, RMSE = 25.0 ms.
  Acc@20ms = 0.0%, Acc@50ms = 100.0%, Acc@100ms = 100.0%.
- Offset $\Delta t = +60$ ms:
  All $e_m = 60.0$ ms.
  MAE = 60.0 ms, MedAE = 60.0 ms, RMSE = 60.0 ms.
  Acc@20ms = 0.0%, Acc@50ms = 0.0%, Acc@100ms = 100.0%.

This guarantees exact alignment with the test requirements in `tests/test_benchmark.py`.

### 4.4 Token Matching Algorithm
Tokens may come from forced alignment (where reference and predicted tokens have identical text sequences) or autonomous ASR (Whisper, where insertions, deletions, and substitutions occur).

Algorithm:
1. Fast Path (1-to-1 Match):
   If `len(pred_tokens) == len(ref_tokens)` and text labels match:
   Pair `(pred[k], ref[k])` for all $k \in [0, K-1]$.
2. Dynamic Programming Fallback (Needleman-Wunsch Sequence Alignment):
   When lengths differ or labels do not match:
   - Extract normalized token labels $L_{pred}$ and $L_{ref}$.
   - Score matrix: Match = +2, Mismatch = -1, Gap (Insertion/Deletion) = -1.
   - Traceback recovers the optimal alignment sequence.
   - Matched pairs with identical labels are retained. Insertions and deletions are logged.
3. Label-Free Fallback:
   If tokens have no textual labels (e.g., bare interval tuples), pair by chronological order if equal length, or maximum temporal overlap (IoU) if lengths differ.
4. Division-by-Zero and Empty Handling:
   - If `len(ref_tokens) == 0`: raise `MetricComputationError("Reference tokens list is empty")`.
   - If `len(pred_tokens) == 0`: raise `MetricComputationError("Predicted tokens list is empty")`.
   - If zero tokens could be matched: raise `MetricComputationError("Zero token matches between prediction and reference")`.
   - If `tolerance_ms <= 0.0`: raise `MetricComputationError("tolerance_ms must be positive")`.

---

## 5. Clustered Bootstrap Resampling Architecture

### 5.1 Rationale in Speech Corpora
In speech recognition and alignment benchmarks (TIMIT Core Test: 24 speakers, 192 sentences; Buckeye Speech Corpus: 40 speakers), individual boundary errors within an utterance or from a single speaker are statistically dependent due to speaker vocal tract characteristics, speaking rate, and microphone acoustics.
Resampling individual boundary errors independently (i.i.d. bootstrap) violates exchangeability and leads to severely underestimated standard errors and invalid confidence intervals.
Clustered bootstrap resamples entire clusters (speakers or utterances) with replacement, preserving intra-cluster acoustic dependence.

### 5.2 Algorithm Formulation
Input:
- `errors`: 1D array of boundary errors, length $N$.
- `clusters`: 1D array of cluster IDs (e.g. speaker ID "fadg0"), length $N$.
- `num_resamples`: integer, default 2000.
- `alpha`: float, default 0.05 ($1 - \alpha = 0.95$ for 95% CI).
- `seed`: int, default 42.
- `statistic_fn`: function mapping error array to scalar, default `np.mean`.

Procedure:
1. Validate `len(errors) == len(clusters)` and `len(errors) > 0`. Raise `MetricComputationError` on mismatch or empty input.
2. Group error indices by cluster:
   Identify unique clusters $C = \{c_1, \dots, c_K\}$.
   Group error sub-arrays: $E_k = \text{errors}[\text{clusters} == c_k]$ for $k = 1, \dots, K$.
   If $K < 2$, raise `MetricComputationError("Clustered bootstrap requires at least 2 distinct clusters")`.
3. Initialize deterministic RNG: `rng = np.random.default_rng(seed)`.
4. Resampling:
   For $b = 1, \dots, \text{num\_resamples}$:
   - Draw $K$ cluster indices with replacement: $I_b \sim \text{Uniform}(\{1, \dots, K\}^K)$.
   - Concatenate errors: $E^*_b = \bigoplus_{j \in I_b} E_j$.
   - Compute replicate statistic: $\theta^*_b = \text{statistic\_fn}(E^*_b)$.
5. Confidence Interval Calculation:
   Compute empirical percentiles from distribution $\Theta^* = \{\theta^*_1, \dots, \theta^*_B\}$:
   $$\text{CI}_{lower} = \text{percentile}(\Theta^*, 100 \times \alpha / 2) = 2.5\%$$
   $$\text{CI}_{upper} = \text{percentile}(\Theta^*, 100 \times (1 - \alpha / 2)) = 97.5\%$$
   Return `(float(ci_lower), float(ci_upper))`.

Performance Profile:
Tested with $N = 1000, K = 24, B = 2000$: execution time is 0.0179 seconds (< 20 ms), fulfilling the < 5 second offline test execution requirement.

---

## 6. Paired Wilcoxon Signed-Rank Test and Cliff's Delta Effect Size

### 6.1 Paired Wilcoxon Signed-Rank Test
Given paired error observations $X = (x_1, \dots, x_N)$ (baseline errors) and $Y = (y_1, \dots, y_N)$ (proposed errors) on the same reference boundaries:

1. Differences:
   $$d_i = x_i - y_i, \quad i = 1, \dots, N$$
2. Non-zero Filtering (Wilcoxon method):
   Filter out ties with zero difference: $d'_j \in \{ d_i \mid d_i \ne 0 \}$, length $N_r$.
   If $N_r == 0$ (all paired errors are identical):
   Return statistic $W = 0.0$, $p = 1.0$, $\delta = 0.0$, effect size = "negligible".
3. Tie-Aware Fractional Ranking:
   Sort absolute non-zero differences $|d'_j|$.
   Assign fractional ranks to tied values: if $c$ values share rank range $[\text{start}, \text{start} + c - 1]$, each is assigned the average rank $\text{start} + (c - 1) / 2.0$.
4. Rank Sums:
   $$W^+ = \sum_{d'_j > 0} \text{rank}(|d'_j|)$$
   $$W^- = \sum_{d'_j < 0} \text{rank}(|d'_j|)$$
   Test statistic: $W = \min(W^+, W^-)$.
5. Variance with Tie Correction:
   Let $t_k$ be the count of tied values in tie group $k$:
   $$\mu = \frac{N_r (N_r + 1)}{4}$$
   $$\sigma^2 = \frac{N_r (N_r + 1)(2N_r + 1)}{24} - \sum_k \frac{t_k^3 - t_k}{48}$$
6. Z-Score and Two-Sided p-Value:
   With continuity correction:
   $$Z = \frac{|W - \mu| - 0.5}{\sigma}$$
   Compute standard normal cumulative distribution function $\Phi(z)$ via standard library `math.erf`:
   $$\Phi(z) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{z}{\sqrt{2}} \right) \right]$$
   $$p\text{-value} = 2.0 \times (1.0 - \Phi(|Z|))$$
   Clamped strictly within $[0.0, 1.0]$.

### 6.2 Cliff's Delta Effect Size
Cliff's Delta ($\delta$) is a non-parametric effect size measuring the probability that a value from the baseline group is larger than a value from the proposed group, minus the reverse:
$$\delta = \frac{\#\{x_i > y_j\} - \#\{x_i < y_j\}}{N \cdot M}$$

For paired baseline and proposed error samples:
We can compute the exact two-sample all-pairs Cliff's Delta efficiently using the Mann-Whitney $U$ rank relationship:
$$U = R_X - \frac{N(N + 1)}{2}$$
$$\delta = \frac{2U}{N \cdot M} - 1$$
which computes in $O((N + M) \log(N + M))$ time without allocating an $N \times M$ matrix.

Effect Size Thresholds (Romano et al., 2006):
- $|\delta| < 0.147$: "negligible"
- $0.147 \le |\delta| < 0.330$: "small"
- $0.330 \le |\delta| < 0.474$: "medium"
- $|\delta| \ge 0.474$: "large"

Directional interpretation:
When proposed errors are smaller than baseline errors, baseline > proposed dominates, so $\delta > 0$, indicating an improvement by the proposed method.

---

## 7. Public API and Export Architecture

The following symbols will be exported in `src/subtitle_workbench/__init__.py`:
- `AlignmentEvaluationResult`
- `BoundaryEvaluation`
- `WilcoxonTestResult`
- `BenchmarkError`
- `CorpusFormatError`
- `MetricComputationError`
- `evaluate_alignment_boundaries`
- `clustered_bootstrap_ci`
- `paired_wilcoxon_test`

Zero-Emoji Discipline:
All docstrings, log messages, exception messages, and outputs use clean ASCII formatting only (`[+]`, `[-]`, `[*]`, `[OK]`, `[FAIL]`, `->`, `|`).
