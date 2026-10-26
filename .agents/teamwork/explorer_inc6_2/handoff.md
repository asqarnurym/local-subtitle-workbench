# Handoff Report: Alignment Metrics and Statistical Analysis Module (Requirement R2)

Date: 2026-10-26
Agent: explorer_inc6_2
Folder: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_inc6_2
Recipient: d7780ee7-0d12-43b1-8cad-0dd6f3550ad6 (Orchestrator)
Handoff Type: Hard

---

## 1. Observation

1. Dependency Configuration (`pyproject.toml:13-25`):
   - `pyproject.toml` declares:
     ```toml
     dependencies = ["numpy>=2.1,<3"]

     [project.optional-dependencies]
     speech = [
         "faster-whisper>=1.0.0",
         "torch>=2.2.0",
     ]

     [dependency-groups]
     dev = ["pytest>=8.3,<9", "ruff>=0.11,<1", "build>=1.2,<2", "hatchling==1.32.4"]
     ```
   - Running `uv run python -c "import scipy"` returned exit code 1 with:
     `ModuleNotFoundError: No module named 'scipy'`.

2. Existing Test Suite Execution:
   - Executing `uv run --locked pytest` completed in 12.09s with:
     `637 passed, 1 skipped in 12.09s`.
     The single skipped test is `tests\test_asr.py:1129: faster-whisper is not installed`.

3. Legacy Benchmark Implementation (`scripts/benchmark.py:20-29`):
   - Computes dual-boundary absolute errors:
     ```python
     errors.extend(
         [
             abs(clip["startOffset"] - cue["start"]),
             abs(clip["endOffset"] - cue["end"]),
         ]
     )
     ```
   - Computes:
     `mean_absolute_error_ms = float(np.mean(errors) * 1000)`
     `within_50ms_percent = float(np.mean(np.asarray(errors) <= 0.05) * 100)`

4. Existing Speech Contracts (`src/subtitle_workbench/models.py:7-16, 137-208`):
   - `finite_number` validates non-bool, non-NaN, non-inf real numbers.
   - `PhonemeCue` and `WordToken` are frozen dataclasses with `start` and `end` timestamps in seconds, where `0.0 <= start < end`.
   - `WordToken` has `text: str` and `normalized: str`.
   - `PhonemeCue` has `phoneme: str`.

5. Numerical Performance Benchmarking:
   - Running 2000 resamples of clustered bootstrap with $N = 1000$ points and 24 speaker clusters executed in 0.0179s using NumPy's `default_rng(42)`.
   - Pure-Python tie-aware ranking and normal approximation for Wilcoxon signed-rank test executed in < 0.005s.
   - Fast $O((N + M)\log(N + M))$ rank-based Cliff's Delta computation matched the $O(NM)$ outer difference formula to 8 decimal places.

---

## 2. Logic Chain

1. From Observation 1, `scipy` is not present in the runtime environment and is not declared in `pyproject.toml`. Adding it would alter locked dependencies and violate the core constraint that the base package must remain lightweight and installable without heavy scientific distributions. Therefore, all statistical routines in `src/subtitle_workbench/metrics.py` (Wilcoxon signed-rank test, tie-aware ranking, Cliff's Delta, Clustered Bootstrap, and Gaussian CDF) must be implemented natively in pure NumPy and Python standard library (`math`, `typing`, `dataclasses`).

2. From Observation 3 and prompt specifications, speech alignment evaluation measures two boundary errors for each token (start boundary |t_pred_start - t_ref_start| and end boundary |t_pred_end - t_ref_end|). When converted to milliseconds by multiplying seconds by 1000.0, errors directly match the prompt's oracle testing specifications (+15 ms shift yields MAE=15.0 ms, Acc@20ms=100.0%, Acc@50ms=100.0%; +25 ms shift yields MAE=25.0 ms, Acc@20ms=0.0%, Acc@50ms=100.0%; +60 ms shift yields MAE=60.0 ms, Acc@20ms=0.0%, Acc@50ms=0.0%, Acc@100ms=100.0%).

3. From Observation 4, `WordToken` has `normalized` and `text`, while `PhonemeCue` has `phoneme`. Tokens may differ between reference and prediction due to ASR deletion/insertion/substitution in Whisper baseline mode. Therefore, `evaluate_alignment_boundaries` requires a two-tiered matching algorithm: a fast 1-to-1 match for identical token sequences (forced alignment modes) and a dynamic programming Needleman-Wunsch sequence alignment fallback to pair identical text tokens across insertions and deletions.

4. In speech corpora (TIMIT Core Test: 24 speakers, 192 sentences; Buckeye: 40 speakers), boundary errors from the same speaker share acoustic variance. Standard i.i.d. bootstrap underestimates variance. Resampling entire clusters (speaker or utterance ID) with replacement preserves intra-cluster correlation. Using `np.random.default_rng(seed=42)` guarantees deterministic cross-platform reproducibility, and pre-vectorized concatenation of grouped cluster arrays ensures execution in < 20 ms (Observation 5).

5. The Wilcoxon signed-rank test and Cliff's Delta can be computed without external packages:
   - Wilcoxon: compute differences $d_i = x_i - y_i$, drop zeros ($d_i = 0$), sort $|d_i|$, compute average tie ranks, sum positive ranks $W^+$, sum negative ranks $W^-$, evaluate test statistic $W = \min(W^+, W^-)$, compute variance with tie correction $\sum (t_k^3 - t_k)/48$, and evaluate the two-sided p-value via normal approximation with continuity correction using standard library `math.erf`.
   - Cliff's Delta: evaluate $\delta = \frac{2U}{NM} - 1$ via rank sums in $O((N+M)\log(N+M))$ time, and classify effect size into "negligible" (< 0.147), "small" (< 0.33), "medium" (< 0.474), or "large" (>= 0.474).

6. To maintain consistency with ECC Error Handling conventions across the repository (`chunker.py`, `asr.py`, `mfa_wrapper.py`), a typed exception hierarchy must be rooted at `BenchmarkError(Exception)`, with specialized subclasses `CorpusFormatError(BenchmarkError)` and `MetricComputationError(BenchmarkError)`.

---

## 3. Caveats

1. Wilcoxon exact distribution for very small $N_r < 10$: For benchmark suites on TIMIT (192 sentences, thousands of word and phoneme boundaries), $N$ is well into the hundreds or thousands, where the normal approximation with continuity correction is asymptotically exact. For synthetic unit tests with small $N$, the normal approximation remains continuous and bounded in $[0.0, 1.0]$.
2. Token matching for partial word overlaps: If Whisper produces compound words or splits words (e.g. "cannot" vs "can not"), standard sequence alignment treats them as insertion/deletion unless normalized via `text_norm.normalize_transcript` prior to boundary evaluation. The pipeline runner in Requirement R3 should apply text normalization to transcripts before boundary evaluation.
3. No production or test files were modified during this investigation, adhering to the read-only explorer constraint.

---

## 4. Conclusion

The architectural, mathematical, and algorithmic requirements for `src/subtitle_workbench/metrics.py` (Requirement R2) are fully resolved:
1. Module implementation requires zero new external dependencies; pure NumPy and Python standard library are completely sufficient and verified to run in < 20 ms.
2. Data contracts:
   - `AlignmentEvaluationResult`: frozen dataclass holding word and phoneme MAE, MedAE, RMSE, Acc@20ms, Acc@50ms, Acc@100ms, RTF, peak VRAM, peak RAM, metadata, and a dictionary of 95% bootstrap confidence intervals.
   - `BoundaryEvaluation`: frozen dataclass holding metrics and raw boundary error arrays for a single tier.
   - `WilcoxonTestResult`: frozen dataclass holding W-statistic, two-sided p-value, Cliff's Delta, effect size magnitude, and pair counts.
3. Matching and boundary evaluation (`evaluate_alignment_boundaries`):
   - Calculates start and end boundary errors in milliseconds: $|t_{pred} - t_{ref}| \times 1000.0$.
   - Handles empty tokens by raising `MetricComputationError` to protect against division-by-zero.
   - Evaluates MAE, MedAE, RMSE, Acc@20ms, Acc@50ms, Acc@100ms.
4. Clustered Bootstrap (`clustered_bootstrap_ci`):
   - Resamples cluster groups (speaker/utterance) with replacement with `num_resamples=2000`, `alpha=0.05`, and `seed=42`.
   - Computes empirical percentiles (2.5% and 97.5%).
5. Paired Wilcoxon and Cliff's Delta (`paired_wilcoxon_test`):
   - Computes tie-adjusted Wilcoxon signed-rank test and p-value via `math.erf`.
   - Computes Cliff's Delta effect size using rank-based $O((N+M)\log(N+M))$ formulation.
6. Exception hierarchy:
   - `BenchmarkError(Exception)`
     - `CorpusFormatError(BenchmarkError)`
     - `MetricComputationError(BenchmarkError)`

---

## 5. Verification Method

1. Independent Syntax and Offline Import Verification:
   Inspect `src/subtitle_workbench/metrics.py` after implementation:
   ```bash
   uv run python -c "from subtitle_workbench.metrics import AlignmentEvaluationResult, evaluate_alignment_boundaries, clustered_bootstrap_ci, paired_wilcoxon_test, BenchmarkError, CorpusFormatError, MetricComputationError; print('[OK] Imports successful')"
   ```

2. Boundary Error Oracle Verification:
   Execute boundary evaluations with fixed offsets (+15ms, +25ms, +60ms) and verify:
   - +15 ms: MAE == 15.0, Acc@20ms == 100.0%, Acc@50ms == 100.0%
   - +25 ms: MAE == 25.0, Acc@20ms == 0.0%, Acc@50ms == 100.0%
   - +60 ms: MAE == 60.0, Acc@20ms == 0.0%, Acc@50ms == 0.0%, Acc@100ms == 100.0%

3. Statistical Determinism Verification:
   ```bash
   uv run python -c "import numpy as np; from subtitle_workbench.metrics import clustered_bootstrap_ci; errors = np.array([10.0, 20.0, 30.0, 15.0]); clusters = np.array(['s1', 's1', 's2', 's2']); ci1 = clustered_bootstrap_ci(errors, clusters, num_resamples=100, seed=42); ci2 = clustered_bootstrap_ci(errors, clusters, num_resamples=100, seed=42); assert ci1 == ci2; print('[OK] Deterministic bootstrap verified')"
   ```

4. Full Project Test Suite Verification:
   ```bash
   uv run --locked pytest
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```

Invalidation Conditions:
- Any requirement for `scipy` as a mandatory dependency that breaks `uv run --locked pytest`.
- Acc@Xms or MAE failing to match the oracle offsets (+15 ms, +25 ms, +60 ms).
- Division-by-zero error on empty token sequences instead of raising `MetricComputationError`.
