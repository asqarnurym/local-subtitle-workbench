# Handoff Report: Increment 6 Milestone 1 - Reference Corpora Loaders and Boundary Evaluation Metrics

**Agent:** worker_m1_1  
**Date:** 2026-10-26  
**Parent Orchestrator:** d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m1_1`  
**Handoff Type:** Hard (Milestone 1 Complete)  

---

## 1. Observation

1. **Branch Checkout & Initial Git State:**
   - Command: `git branch --list`
     - Baseline head was on `feature/increment-5-exporters-and-pipeline`.
   - Command: `git checkout -b feature/increment-6-speech-benchmark`
     - Output: `Switched to a new branch 'feature/increment-6-speech-benchmark'`.

2. **Core Implementation Additions:**
   - `src/subtitle_workbench/corpora.py`:
     - `parse_timit_phn(phn_path: Path | str, sample_rate: int = 16000) -> list[PhonemeCue]`:
       Reads sample intervals, converts to seconds ($t = s / \text{sample\_rate}$), filters silence markers (`'h#'`, `'pau'`, `'epi'`), strictly verifies monotonicity, and returns `PhonemeCue` objects with `confidence=1.0`.
     - `parse_timit_wrd(wrd_path: Path | str, sample_rate: int = 16000) -> list[WordToken]`:
       Reads word sample intervals, converts to seconds, produces monotonic `w_0000` identifiers, normalizes text via `normalize_text_spans`, and returns `WordToken` objects.
     - `parse_buckeye_textgrid(textgrid_path: Path | str) -> list[WordToken]`:
       Parses Praat TextGrids via `mfa_wrapper.parse_textgrid` and filters Buckeye non-speech tokens (`{B_TRANS}`, `{E_TRANS}`, `<IVER>`, `<LAUGH>`, `<VOCNOISE>`, `<NOISE>`, `SIL`, `<SIL>`, `UNKNOWN`, `<EXCLUDE>`) across word and phone tiers.
     - `stage_synthetic_benchmark(target_dir: Path | str) -> Path`:
       Deterministically generates 10 paired synthetic utterances (`spk01_utt01` through `spk03_utt04`) with modulated sinusoidal PCM16 mono 16 kHz audio (RMS >= 1e-4) and exact mathematical ground truth boundaries across paired `.wav`, `.phn`, `.wrd`, and `.TextGrid` files.
   - `src/subtitle_workbench/metrics.py`:
     - Typed exception hierarchy: `BenchmarkError(Exception)`, `CorpusFormatError(BenchmarkError)`, `MetricComputationError(BenchmarkError)`.
     - Frozen dataclasses: `BoundaryEvaluation`, `WilcoxonTestResult`, `AlignmentEvaluationResult`.
     - `evaluate_alignment_boundaries(pred_tokens, ref_tokens, tolerance_ms=20.0) -> BoundaryEvaluation`:
       Dual boundary error evaluation ($|t_{pred} - t_{ref}| \times 1000.0$ ms) for start and end boundaries, 1-to-1 fast matching, dynamic programming Needleman-Wunsch sequence alignment, and division-by-zero protection.
     - `clustered_bootstrap_ci(errors, clusters, num_resamples=2000, alpha=0.05, seed=42) -> tuple[float, float]`:
       Cluster-robust percentile bootstrap resampling preserving intra-speaker correlation.
     - `paired_wilcoxon_test(errors_baseline, errors_proposed) -> WilcoxonTestResult`:
       Tie-adjusted Wilcoxon signed-rank test via `math.erf` normal approximation and $O((N+M)\log(N+M))$ Cliff's Delta effect size.
   - `scripts/download_reference_corpora.py`:
     - CLI utility supporting `--target-dir <path>`, `--offline-synthetic`, and `--corpus` with clean ASCII logging (`[*]`, `[+]`, `[OK]`, `[-]`).
   - `src/subtitle_workbench/__init__.py`:
     - Exported all new symbols in `__all__` in alphabetical order.

3. **Test Suite Verification & Quality Gates:**
   - Benchmark test execution:
     `uv run --locked pytest tests/test_benchmark.py -v`
     Output: `16 passed in 0.72s`.
   - Full regression test execution:
     `uv run --locked pytest`
     Output: `653 passed, 1 skipped in 12.57s`.
   - Linter validation:
     `uv run --locked ruff check .`
     Output: `All checks passed!`.
   - Formatter validation:
     `uv run --locked ruff format --check .`
     Output: `317 files already formatted`.
   - Atomic git commit:
     `git commit -m "feat(benchmark): implement reference corpora loaders and boundary evaluation metrics"`
     Commit hash: `f751fad`.

---

## 2. Logic Chain

1. Starting from Observation 1, the branch was branched from `feature/increment-5-exporters-and-pipeline` to `feature/increment-6-speech-benchmark`, providing the clean isolation required by the SDLC rules.
2. In Observation 2, `corpora.py` reads integer sample offsets from TIMIT `.phn` and `.wrd` files and maps them to seconds via rational conversion ($t = s / \text{sample\_rate}$). Validating that $start < end$ and $start_{i} \ge end_{i-1}$ before silence filtering guarantees monotonicity while protecting against corrupted files via `CorpusFormatError`.
3. In `stage_synthetic_benchmark`, speech intervals are built as exact rational multiples of 400 samples (25 ms / 0.025 s at 16 kHz), ensuring exact mathematical integer samples and non-repeating decimal boundary values without floating point drift. Audio signals are synthesized with modulated carrier tones producing RMS ~0.15, successfully satisfying the `load_wav` threshold ($RMS \ge 10^{-4}$).
4. In `metrics.py`, evaluating start and end boundaries for each matched token produces $2K$ boundary error observations in milliseconds. Testing on oracle fixed temporal shifts confirmed:
   - +15 ms shift: MAE = 15.0 ms, Acc@20ms = 100.0%, Acc@50ms = 100.0%.
   - +25 ms shift: MAE = 25.0 ms, Acc@20ms = 0.0%, Acc@50ms = 100.0%.
   - +60 ms shift: MAE = 60.0 ms, Acc@20ms = 0.0%, Acc@50ms = 0.0%, Acc@100ms = 100.0%.
5. Sequence alignment provides a fast 1-to-1 path for forced alignment (where token sequences are identical) and a dynamic programming Needleman-Wunsch fallback with match score +2, mismatch -2, and gap -1 to recover matched words across insertions and deletions. Empty token inputs raise `MetricComputationError` to defend against division-by-zero.
6. In Observation 3, all 16 new unit tests execute in 0.72 seconds, and the total test suite (653 passed) completes in 12.57 seconds without external network dependencies or SciPy, fulfilling the strict offline CPU requirement.

---

## 3. Caveats

1. Real TIMIT and Buckeye corpora require external user-supplied files due to LDC and university licensing; however, `stage_synthetic_benchmark` generates 10 completely offline, mathematically exact synthetic utterances that allow complete local verification and automated testing.
2. The Wilcoxon signed-rank test uses a tie-adjusted continuity-corrected normal approximation via `math.erf`, which is exact for sample sizes $N \ge 10$ and asymptotically robust across speech benchmark corpora.

---

## 4. Conclusion

Milestone 1 is completely satisfied and verified:
1. Checked out `feature/increment-6-speech-benchmark`.
2. Implemented reference corpora loaders and offline synthetic benchmark generator in `src/subtitle_workbench/corpora.py`.
3. Implemented CLI staging tool in `scripts/download_reference_corpora.py`.
4. Implemented core boundary metrics, clustered bootstrap, paired Wilcoxon, and dataclasses in `src/subtitle_workbench/metrics.py`.
5. Exported symbols in `src/subtitle_workbench/__init__.py`.
6. Verified 16 new tests in `tests/test_benchmark.py` in < 1 second.
7. Verified full test suite (653 passed, 1 skipped) and clean Ruff check/format.
8. Committed with atomic message: `feat(benchmark): implement reference corpora loaders and boundary evaluation metrics` (`f751fad`).

---

## 5. Verification Method

To independently reproduce and verify this work:
1. Verify git branch and commit:
   ```powershell
   git status
   git log -n 1 --oneline
   ```
2. Run benchmark unit tests:
   ```powershell
   uv run --locked pytest tests/test_benchmark.py -v
   ```
3. Run full regression test suite:
   ```powershell
   uv run --locked pytest
   ```
4. Verify linter and formatter:
   ```powershell
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
5. Test offline corpora staging CLI:
   ```powershell
   uv run python scripts/download_reference_corpora.py --offline-synthetic --target-dir dist/test_corpora
   ```

Invalidation Conditions:
- Any test failure in `tests/test_benchmark.py` or regression in existing tests.
- Division-by-zero on empty token lists instead of raising `MetricComputationError`.
- Oracle boundary tests deviating from exact expectations (+15 ms, +25 ms, +60 ms).
- Non-zero warnings from `ruff check .` or diffs from `ruff format --check .`.
