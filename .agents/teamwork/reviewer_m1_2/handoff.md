# Handoff Report: Review and Adversarial Critique of Milestone 1 Implementation

**Agent:** reviewer_m1_2  
**Role:** Reviewer & Adversarial Critic  
**Date:** 2026-10-26  
**Target Milestone:** Milestone 1 (Increment 6)  
**Parent Orchestrator:** d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\reviewer_m1_2`  
**Handoff Type:** Hard  

---

## Review Summary

**Verdict:** APPROVE  
**Integrity Status:** PASSED (Zero integrity violations; genuine implementation with independent execution verification)  
**Advisory Findings:** 1 (Minor / Non-blocking for Milestone 1; relevant to Milestone 2 statistical robustness)  

---

## 1. Observation

1. **Interface Contracts & Exception Hierarchy (`src/subtitle_workbench/metrics.py`):**
   - Lines 20-29:
     ```python
     class BenchmarkError(Exception):
         """Base exception for speech benchmark operations."""


     class CorpusFormatError(BenchmarkError):
         """Raised when speech corpus files are malformed or non-monotonic."""


     class MetricComputationError(BenchmarkError):
         """Raised when metric computation encounters invalid or empty inputs."""
     ```
   - Lines 32-73: `BoundaryEvaluation` is a `@dataclass(frozen=True)` capturing `mae`, `medae`, `rmse`, `acc_20ms`, `acc_50ms`, `acc_100ms`, `boundary_errors_ms: list[float]`, `num_matched: int`, `num_unmatched: int`, `tolerance_ms: float = 20.0`. Validates that metric values are finite non-negative numbers, accuracy values are in $[0.0, 100.0]$, and counts are non-negative integers via `models.finite_number`.
   - Lines 75-101: `WilcoxonTestResult` is a `@dataclass(frozen=True)` capturing `statistic`, `p_value`, `cliffs_delta`, `effect_size`, `n_pairs`, `n_non_zero`. Validates $0.0 \le p\_value \le 1.0$ and $-1.0 \le cliffs\_delta \le 1.0$.
   - Lines 103-152: `AlignmentEvaluationResult` is a `@dataclass(frozen=True)` capturing `word_metrics`, `phone_metrics`, `rtf`, `peak_vram_mb`, `peak_ram_mb`, `bootstrap_ci_95`, and `metadata`. Includes full JSON serialization via `to_dict()`.

2. **Boundary Metric Evaluation (`src/subtitle_workbench/metrics.py`):**
   - Lines 223-270 (`evaluate_alignment_boundaries`):
     - Empty input guards: checks `len(pred_tokens) == 0` and `len(ref_tokens) == 0`, raising `MetricComputationError`.
     - Zero matching guard: checks `not matched_pairs`, raising `MetricComputationError`.
     - Dual boundary evaluation:
       ```python
       boundary_errors: list[float] = []
       for pred, ref in matched_pairs:
           start_err = abs(pred.start - ref.start) * 1000.0
           end_err = abs(pred.end - ref.end) * 1000.0
           boundary_errors.append(start_err)
           boundary_errors.append(end_err)
       ```
     - Metric calculations: computes `mae` (mean), `medae` (median), `rmse` (root-mean-square error), `acc_20ms` (percentage $\le 20.0$ ms), `acc_50ms` (percentage $\le 50.0$ ms), `acc_100ms` (percentage $\le 100.0$ ms).
   - Lines 163-221 (`_align_token_sequences`):
     - Fast path: `if n == m and pred_keys == ref_keys: return list(zip(pred_tokens, ref_tokens, strict=True)), 0`
     - Dynamic programming fallback: $(n+1) \times (m+1)$ Needleman-Wunsch algorithm with match reward +2, mismatch penalty -2, gap penalty -1. Backtrace correctly returns matched pairs and counts unmatched tokens.

3. **Oracle Unit Tests (`tests/test_benchmark.py`):**
   - Lines 285-333:
     - +15 ms shift: verified `mae == 15.0`, `medae == 15.0`, `rmse == 15.0`, `acc_20ms == 100.0%`, `acc_50ms == 100.0%`, `acc_100ms == 100.0%`.
     - +25 ms shift: verified `mae == 25.0`, `medae == 25.0`, `rmse == 25.0`, `acc_20ms == 0.0%`, `acc_50ms == 100.0%`, `acc_100ms == 100.0%`.
     - +60 ms shift: verified `mae == 60.0`, `medae == 60.0`, `rmse == 60.0`, `acc_20ms == 0.0%`, `acc_50ms == 0.0%`, `acc_100ms == 100.0%`.
   - Lines 350-394: DP sequence matching tested across insertions/deletions, and empty inputs tested for division-by-zero protection.

4. **Execution of Automated Verification Gates:**
   - Command: `uv run --locked pytest tests/test_benchmark.py`
     Result: `16 passed in 0.70s` (Exit code 0).
   - Command: `uv run --locked pytest`
     Result: `653 passed, 1 skipped in 13.02s` (Exit code 0).
   - Command: `uv run --locked ruff check .`
     Result: `All checks passed!` (Exit code 0).
   - Command: `uv run --locked ruff format --check .`
     Result: `317 files already formatted` (Exit code 0).
   - Non-ASCII byte check across `src/subtitle_workbench/metrics.py`, `src/subtitle_workbench/corpora.py`, `src/subtitle_workbench/__init__.py`, `tests/test_benchmark.py`: 0 non-ASCII bytes found.

5. **Adversarial Stress-Testing Observation:**
   - In `src/subtitle_workbench/metrics.py`, line 406:
     In `paired_wilcoxon_test`, the tie-counting loop is:
     `while j < n_r and sorted_abs[j] == sorted_abs[i]: j += 1`
     Similarly in line 336 of `_cliffs_delta`:
     `while j < len(sorted_comb) and sorted_comb[j] == sorted_comb[i]: j += 1`
     If a caller passes an array containing `NaN`, IEEE 754 specifies `nan == nan` is `False`. Therefore, when `sorted_abs[i]` is `NaN`, `sorted_abs[j] == sorted_abs[i]` evaluates to `False` immediately when `j == i`. The inner loop does not increment `j`, so `j` remains equal to `i`. The subsequent statement `i = j` leaves `i` unchanged, resulting in an infinite while loop.

---

## 2. Logic Chain

1. From Observation 1, the exception classes `BenchmarkError`, `CorpusFormatError`, and `MetricComputationError` conform to the project error-handling hierarchy and interface contract in `SCOPE.md`.
2. The dataclasses `BoundaryEvaluation`, `WilcoxonTestResult`, and `AlignmentEvaluationResult` are immutable (`frozen=True`) and strictly validate their fields in `__post_init__` using `finite_number`, preventing NaN, infinite, or boolean corruption in reported metrics.
3. From Observation 2, `evaluate_alignment_boundaries` accurately implements dual boundary evaluation by computing both start and end boundary discrepancies in milliseconds ($|t_{pred} - t_{ref}| \times 1000.0$). For $K$ matched tokens, $2K$ boundary error observations are collected.
4. The fast-path optimization handles identical token sequences in $O(N)$ time, while the Needleman-Wunsch algorithm handles insertions, deletions, and substitutions in $O(N \times M)$ time. Both paths preserve token order and strictly terminate in finite steps.
5. In Observation 3, the oracle tests mathematically prove that fixed boundary shifts (+15 ms, +25 ms, +60 ms) match theoretical clinical and ITU-R threshold boundaries.
6. In Observation 4, all 16 new benchmark tests pass within 0.70 seconds on offline CPU, and all 653 tests across the entire repository pass without regression. Zero linter or formatting issues exist.
7. Checking for integrity violations:
   - There are zero hardcoded test outputs in source code.
   - Algorithms (Needleman-Wunsch, bootstrap resampling, Wilcoxon signed-rank, Cliff's Delta) are fully implemented without facade stubs or shortcuts.
   - Zero synthetic claims or fabricated logs exist.
8. From Observation 5, while Milestone 1's boundary evaluation functions produce purely finite values from validated `WordToken`/`PhonemeCue` objects, `paired_wilcoxon_test` and `clustered_bootstrap_ci` (scheduled for Milestone 2) would benefit from explicit `np.all(np.isfinite(...))` guards to prevent infinite loops when given NaN input. This is recorded as an advisory finding for Milestone 2.
9. Therefore, Milestone 1 implementation is completely verified, robust, and approved.

---

## 3. Caveats

1. The NaN edge case in `paired_wilcoxon_test` and `_cliffs_delta` does not affect Milestone 1 deliverables (`evaluate_alignment_boundaries`, data contracts, and `corpora.py`), because `WordToken` and `PhonemeCue` guarantee strictly finite timestamps.
2. Full ablation and CLI runner integration testing will occur in Milestone 2.

---

## 4. Conclusion

Milestone 1 is APPROVED. The data contracts, exception hierarchy, boundary evaluation engine, sequence alignment logic, and oracle unit tests meet all requirements and acceptance criteria without regression or integrity violations.

### Findings

#### [Advisory / Minor] Finding 1: Lack of `isfinite` Input Validation in Wilcoxon and Cliff's Delta
- **What:** If input error arrays contain `NaN`, `paired_wilcoxon_test` and `_cliffs_delta` enter an infinite loop because `nan == nan` evaluates to `False` in tie-counting loops.
- **Where:** `src/subtitle_workbench/metrics.py`, lines 336 and 406.
- **Why:** Tie detection assumes reflexivity (`x == x`), which fails for `NaN`.
- **Suggestion:** During Milestone 2, add defensive input check:
  `if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)): raise MetricComputationError("Input errors must be finite numbers")`.

---

## 5. Verification Method

To independently verify this evaluation:
1. Run benchmark unit tests:
   ```powershell
   uv run --locked pytest tests/test_benchmark.py -v
   ```
   Expected: 16 passed in < 1.0s.
2. Run full regression test suite:
   ```powershell
   uv run --locked pytest
   ```
   Expected: 653 passed, 1 skipped.
3. Run linter and formatter:
   ```powershell
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   Expected: 0 errors, 0 diffs.
4. Verify ASCII compliance:
   ```powershell
   uv run python -c "assert all(open(p, 'rb').read().isascii() for p in ['src/subtitle_workbench/metrics.py', 'tests/test_benchmark.py'])"
   ```
   Expected: Clean exit code 0.

Invalidation conditions:
- Any test failure or timeout in `tests/test_benchmark.py`.
- Any non-zero exit code from `ruff check` or `ruff format --check`.
- Any presence of emojis or graphical Unicode icons in code or reports.
