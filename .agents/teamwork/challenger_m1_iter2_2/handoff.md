# Handoff Report: Adversarial Verification of Metrics Fixes

**Agent**: challenger_m1_iter2_2  
**Parent Orchestrator**: d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Working Directory**: `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\challenger_m1_iter2_2`  
**Target Branch**: `feature/increment-6-speech-benchmark`  
**Date**: 2026-10-26  
**Handoff Type**: Hard  
**Verdict**: APPROVE  
**Discipline**: Pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |)  

---

## 1. Observation

1. **Re-Test Bug 1: Exact 20.0ms Sample Boundary Shifts vs 321 Samples Shift:**
   - Evaluated `evaluate_alignment_boundaries` on exact 320-sample shifts (mathematically $320 / 16000 = 0.020$ s $= 20.0$ ms) at $t = 1.0$s, $t = 2.0$s, and $t = 10.0$s:
     * $t = 1.0$s: `mae = 20.000000000000018 ms`, `acc_20ms = 100.0%`
     * $t = 2.0$s: `mae = 20.000000000000018 ms`, `acc_20ms = 100.0%`
     * $t = 10.0$s: `mae = 19.999999999999574 ms`, `acc_20ms = 100.0%`
   - Evaluated `evaluate_alignment_boundaries` on 321-sample shifts ($321 / 16000 = 0.0200625$ s $= 20.0625$ ms, strictly $> 20.0$ ms) at $t = 1.0$s, $t = 2.0$s, and $t = 10.0$s:
     * $t = 1.0$s: `mae = 20.062500000000092 ms`, `acc_20ms = 0.0%`
     * $t = 2.0$s: `mae = 20.062499999999872 ms`, `acc_20ms = 0.0%`
     * $t = 10.0$s: `mae = 20.062499999999872 ms`, `acc_20ms = 0.0%`
   - Evaluated exact 20.0ms shifts across alternative sampling rates ($8000$ Hz, $16000$ Hz, $22050$ Hz, $44100$ Hz, $48000$ Hz):
     * $f_s = 8000$ Hz (160 samples): `acc_20ms = 100.0%`
     * $f_s = 16000$ Hz (320 samples): `acc_20ms = 100.0%`
     * $f_s = 22050$ Hz (441 samples): `acc_20ms = 100.0%`
     * $f_s = 44100$ Hz (882 samples): `acc_20ms = 100.0%`
     * $f_s = 48000$ Hz (960 samples): `acc_20ms = 100.0%`
   - Implementation check: `src/subtitle_workbench/metrics.py` defines `BOUNDARY_EPSILON_MS: float = 1e-4` (0.1 microsecond) and evaluates:
     * `acc_20 = float(np.mean(errors <= (20.0 + BOUNDARY_EPSILON_MS)) * 100.0)`
     * `acc_50 = float(np.mean(errors <= (50.0 + BOUNDARY_EPSILON_MS)) * 100.0)`
     * `acc_100 = float(np.mean(errors <= (100.0 + BOUNDARY_EPSILON_MS)) * 100.0)`

2. **Re-Test Bug 2: Exact Null Symmetry in `paired_wilcoxon_test`:**
   - Evaluated paired differences with exact null symmetry:
     * Differences `[+1.0, -1.0, +2.0, -2.0]`:
       `statistic = 5.0`, `mean_w = 5.0`, `var_w = 7.125`, `deviation = 0.0`, `z = 0.0`, `p_value = 1.0`, `cliffs_delta = 0.0`
     * 6 symmetric differences `[+1.0, -1.0, +2.0, -2.0, +3.0, -3.0]`:
       `statistic = 10.5`, `mean_w = 10.5`, `deviation = 0.0`, `z = 0.0`, `p_value = 1.0`, `cliffs_delta = 0.0`
     * Minimal symmetric pair `[+1.0, -1.0]`: `statistic = 1.5`, `p_value = 1.0`
     * Continuous floating-point symmetric differences `[+0.1, -0.1, +0.2, -0.2, +0.5, -0.5]`: `statistic = 10.5`, `p_value = 1.0`
   - Monotonicity stress-test across perturbation delta $\delta \ge 0$:
     * $\delta = 0.0$: `stat = 5.0`, `p_val = 1.000000`
     * $\delta = 0.2$: `stat = 4.5`, `p_val = 1.000000`
     * $\delta = 0.5$: `stat = 4.5`, `p_val = 1.000000`
     * $\delta = 1.0$: `stat = 4.0`, `p_val = 0.850107`
     * $\delta = 2.0$: `stat = 3.5`, `p_val = 0.712702`
     * $\delta = 5.0$: `stat = 3.5`, `p_val = 0.712702`
     * Sequence of p-values is non-increasing ($p_{\delta=0} \ge p_{\delta=0.2} \ge \dots$), confirming complete elimination of the significance inversion bug.
   - Implementation check: `src/subtitle_workbench/metrics.py` applies:
     ```python
     deviation = max(0.0, abs(w_stat - mean_w) - 0.5)
     z = deviation / math.sqrt(var_w) if var_w > 0.0 else 0.0
     p_val = 2.0 * (1.0 - _standard_normal_cdf(abs(z)))
     p_val = max(0.0, min(1.0, float(p_val)))
     ```

3. **Metrics Stress Test Suite Execution (`tests/test_metrics_stress.py`):**
   - Executed: `uv run --locked pytest tests/test_metrics_stress.py -v`
   - Result:
     ```text
     tests/test_metrics_stress.py::test_evaluate_alignment_boundaries_empty_inputs PASSED [ 10%]
     tests/test_metrics_stress.py::test_evaluate_alignment_boundaries_zero_duration PASSED [ 20%]
     tests/test_metrics_stress.py::test_evaluate_alignment_boundaries_extreme_discrepancy PASSED [ 30%]
     tests/test_metrics_stress.py::test_evaluate_alignment_boundaries_high_volume_100k PASSED [ 40%]
     tests/test_metrics_stress.py::test_evaluate_alignment_boundaries_distribution_accuracy PASSED [ 50%]
     tests/test_metrics_stress.py::test_evaluate_alignment_boundaries_exact_sample_shift PASSED [ 60%]
     tests/test_metrics_stress.py::test_clustered_bootstrap_reproducibility_and_variation PASSED [ 70%]
     tests/test_metrics_stress.py::test_paired_wilcoxon_identical_arrays PASSED [ 80%]
     tests/test_metrics_stress.py::test_paired_wilcoxon_completely_separated PASSED [ 90%]
     tests/test_metrics_stress.py::test_paired_wilcoxon_exact_null_symmetry_continuity_correction PASSED [100%]
     10 passed in 2.25s (0 xfails, 0 failures)
     ```

4. **Benchmark Suite and Full Regression Execution:**
   - `uv run --locked pytest tests/test_benchmark.py -v`: 19 passed in 0.76s.
   - `uv run --locked pytest`: 666 passed, 1 skipped (optional faster-whisper model weight test) in 15.85s.
   - `uv run --locked ruff check .`: All checks passed (0 errors).
   - `uv run --locked ruff format --check .`: 361 files already formatted.
   - Pure ASCII byte check: 0 non-ASCII bytes across `src/subtitle_workbench/metrics.py`, `src/subtitle_workbench/corpora.py`, `tests/test_metrics_stress.py`, and `tests/test_benchmark.py`.

---

## 2. Logic Chain

1. In Observation 1, the failure mode of exact discrete audio sample shifts at 20.0ms was traced to binary64 floating point rounding: $(16320 / 16000 - 1.0) \times 1000.0 = 20.000000000000018$ ms.
   Because $20.000000000000018 > 20.0$, strict inequality rejected exact ground truth matches.
   Introducing $\epsilon = 10^{-4}$ ms ($0.1$ microsecond) absorbs rounding noise (on the order of $10^{-14}$ ms) while being three orders of magnitude smaller than a single 16 kHz sample ($62.5$ microseconds) or 48 kHz sample ($20.8$ microseconds).
   Empirical verification confirmed that 320-sample shifts pass at 100.0% accuracy across all time offsets ($1.0$s, $2.0$s, $10.0$s), while 321-sample shifts ($20.0625$ ms) fail at 0.0% accuracy. Thus, false rejections are eliminated with zero false acceptance leakage.
2. In Observation 2, under the null hypothesis of symmetric paired differences, $W = \mu_W$. Subtracting the continuity correction $0.5$ without a lower bound produced $-0.5$, which became $+0.5$ when taking $|z|$, penalizing symmetric null distributions ($p < 1.0$) and causing an inverted p-value relationship. Clamping the deviation at zero via $\max(0.0, |W - \mu_W| - 0.5)$ ensures that any difference satisfying $|W - \mu_W| \le 0.5$ yields $\text{deviation} = 0.0 \implies z = 0.0 \implies p = 1.0$. Perturbation tests verified that p-values decrease monotonically as asymmetry increases.
3. In Observations 3 and 4, all 10 stress tests in `tests/test_metrics_stress.py` pass without xfails, all 19 benchmark unit tests in `tests/test_benchmark.py` pass, and all 666 tests in the full project suite pass without regressions.
4. From all preceding points, both reported defects have been empirically verified as fully resolved, robust, and mathematically sound.

---

## 3. Caveats

1. The tolerance parameter `BOUNDARY_EPSILON_MS` applies strictly to discrete acceptance thresholding (`errors <= threshold + eps`); raw boundary error values, MAE, MedAE, and RMSE retain exact unpadded floating-point values.
2. The Wilcoxon test asymptotic normal approximation with continuity correction is valid for $N \ge 10$ non-zero pairs in production benchmarking; for smaller sample sizes under symmetry, the clamp reliably outputs $p = 1.0$.
3. No implementation source files were modified during this review, adhering strictly to review-only constraints.

---

## 4. Conclusion

The metrics fixes in `src/subtitle_workbench/metrics.py` satisfy all correctness, robustness, and mathematical criteria:
- Bug 1 (Sample boundary floating-point rounding): Fully resolved. Exact 20.0ms shifts yield Acc@20ms = 100.0%, 321-sample shifts yield Acc@20ms = 0.0%.
- Bug 2 (Wilcoxon continuity correction null inversion): Fully resolved. Exact null symmetries yield $z = 0.0$ and $p = 1.0$ with monotonic p-value decay under perturbations.
- Stress Test Suite: 10/10 tests in `tests/test_metrics_stress.py` pass cleanly with 0 xfails.
- Regression & Code Quality: Full test suite passes (666 passed, 1 skipped), 0 ruff errors, 0 format diffs, 100% pure ASCII.

**Verdict**: APPROVE.

---

## 5. Verification Method

To independently re-verify these empirical findings:

1. **Re-test boundary shift precision and 321-sample rejection:**
   ```powershell
   uv run python -c "import math; from subtitle_workbench.models import WordToken; from subtitle_workbench.metrics import evaluate_alignment_boundaries; [print(f't={t}s: 320 samples -> {evaluate_alignment_boundaries([WordToken(id=\"w\", text=\"w\", normalized=\"w\", start=(s+320)/16000, end=(s+8320)/16000, confidence=1.0)], [WordToken(id=\"w\", text=\"w\", normalized=\"w\", start=s/16000, end=(s+8000)/16000, confidence=1.0)]).acc_20ms}%') for t, s in [(1.0, 16000), (2.0, 32000), (10.0, 160000)]]"
   ```
   *Expected*: `100.0%` for all timestamps.

   ```powershell
   uv run python -c "import math; from subtitle_workbench.models import WordToken; from subtitle_workbench.metrics import evaluate_alignment_boundaries; [print(f't={t}s: 321 samples -> {evaluate_alignment_boundaries([WordToken(id=\"w\", text=\"w\", normalized=\"w\", start=(s+321)/16000, end=(s+8321)/16000, confidence=1.0)], [WordToken(id=\"w\", text=\"w\", normalized=\"w\", start=s/16000, end=(s+8000)/16000, confidence=1.0)]).acc_20ms}%') for t, s in [(1.0, 16000), (2.0, 32000), (10.0, 160000)]]"
   ```
   *Expected*: `0.0%` for all timestamps.

2. **Re-test Wilcoxon null symmetry:**
   ```powershell
   uv run python -c "from subtitle_workbench.metrics import paired_wilcoxon_test; r = paired_wilcoxon_test([11.0, 9.0, 12.0, 8.0], [10.0, 10.0, 10.0, 10.0]); print(f'stat={r.statistic}, p_val={r.p_value}, cliffs_d={r.cliffs_delta}'); assert r.p_value == 1.0 and r.statistic == 5.0"
   ```
   *Expected*: `stat=5.0, p_val=1.0, cliffs_d=0.0`.

3. **Run metrics stress test suite:**
   ```powershell
   uv run --locked pytest tests/test_metrics_stress.py -v
   ```
   *Expected*: `10 passed` with 0 xfails.

4. **Run full test suite and linters:**
   ```powershell
   uv run --locked pytest
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   *Expected*: 666 passed, 1 skipped; all checks passed; 361 files already formatted.

### Invalidation Conditions
- Any shift of exactly 320 samples at 16 kHz evaluating to Acc@20ms $< 100.0\%$.
- Any shift of 321 samples at 16 kHz evaluating to Acc@20ms $> 0.0\%$.
- Any symmetric paired difference set evaluating to Wilcoxon p-value $< 1.0$.
- Any failure or xfail in `tests/test_metrics_stress.py`.
