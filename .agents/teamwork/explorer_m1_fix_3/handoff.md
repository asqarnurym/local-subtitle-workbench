# Handoff Report: Wilcoxon Signed-Rank Continuity Correction Fix Strategy

**Agent:** explorer_m1_fix_3  
**Role:** EXPLORER (investigator, analyzer, synthesizer)  
**Parent Orchestrator:** d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Target:** Bug 2 in `src/subtitle_workbench/metrics.py:428-430`  
**Date:** 2026-10-26T03:53:30Z  
**Type:** Hard handoff (Task complete)  

---

## 1. Observation

### 1.1 Direct File Inspection
File: `src/subtitle_workbench/metrics.py`  
Lines: 420-432  
Verbatim content:
```python
420:     mean_w = (n_r * (n_r + 1)) / 4.0
421:     tie_term = sum((t**3 - t) for t in tie_counts) / 48.0
422:     var_w = (n_r * (n_r + 1) * (2 * n_r + 1)) / 24.0 - tie_term
423: 
424:     if var_w <= 0.0:
425:         p_val = 1.0
426:     else:
427:         # Continuity-corrected z-score
428:         z = (abs(w_stat - mean_w) - 0.5) / math.sqrt(var_w)
429:         # Two-sided p-value via math.erf
430:         p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
431:         p_val = max(0.0, min(1.0, float(p_val)))
```

### 1.2 Verbatim Tool Execution Outputs
Tool command:
```powershell
uv run python -c "from subtitle_workbench.metrics import paired_wilcoxon_test; res1 = paired_wilcoxon_test([11.0, 9.0, 12.0, 8.0], [10.0, 10.0, 10.0, 10.0]); print('4-pair sym:', res1); res2 = paired_wilcoxon_test([11.0, 9.0, 12.0, 8.0, 13.0, 7.0], [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]); print('6-pair sym:', res2)"
```
Output:
```
4-pair sym: WilcoxonTestResult(statistic=5.0, p_value=0.8526836843346426, cliffs_delta=0.0, effect_size='negligible', n_pairs=4, n_non_zero=4)
6-pair sym: WilcoxonTestResult(statistic=10.5, p_value=0.9158177742866465, cliffs_delta=0.0, effect_size='negligible', n_pairs=6, n_non_zero=6)
```

Tool command (comparing dev=0.0 vs dev=0.5):
```powershell
uv run python -c "from subtitle_workbench.metrics import paired_wilcoxon_test; res_zero=paired_wilcoxon_test([11, 9, 12, 8], [10, 10, 10, 10]); print('Diffs [+1, -1, +2, -2] (deviation 0.0): W =', res_zero.statistic, 'p =', res_zero.p_value); res_half=paired_wilcoxon_test([11, 12, 7, 14, 5], [10, 10, 10, 10, 10]); print('Diffs [+1, +2, -3, +4, -5] (deviation 0.5): W =', res_half.statistic, 'p =', res_half.p_value)"
```
Output:
```
Diffs [+1, -1, +2, -2] (deviation 0.0): W = 5.0 p = 0.8526836843346426
Diffs [+1, +2, -3, +4, -5] (deviation 0.5): W = 7.0 p = 1.0
```

Tool command (stress test xfail status):
```powershell
uv run --locked pytest tests/test_metrics_stress.py -k wilcoxon
```
Output:
```
tests/test_metrics_stress.py::test_paired_wilcoxon_identical_arrays PASSED [ 33%]
tests/test_metrics_stress.py::test_paired_wilcoxon_completely_separated PASSED [ 66%]
tests/test_metrics_stress.py::test_paired_wilcoxon_exact_null_symmetry_continuity_correction_xfail XFAIL [100%]
```

---

## 2. Logic Chain

1. From Observation 1.1, line 428 calculates $z = (|W_{\text{stat}} - \mu_W| - 0.5) / \sqrt{\text{Var}(W)}$.
2. When paired error samples exhibit complete symmetry around zero, $W^+ = W^- = W_{\text{stat}} = \mu_W$, so $|W_{\text{stat}} - \mu_W| = 0.0$.
3. When $|W_{\text{stat}} - \mu_W| = 0.0$, line 428 computes $0.0 - 0.5 = -0.5$. Dividing by standard error yields a negative z-score: $z = -0.5 / \sigma_W$.
4. In line 430, `math.erf(abs(z) / math.sqrt(2.0))` takes `abs(z) = +0.5 / \sigma_W > 0`. Because `abs(z) > 0`, `math.erf` is strictly positive, forcing `p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(...))) < 1.0`.
5. From Observation 1.2, this depresses the p-value under exact symmetry to $0.8527$ ($N=4$) and $0.9158$ ($N=6$).
6. Furthermore, from Observation 1.2, a dataset with deviation $|W_{\text{stat}} - \mu_W| = 0.5$ produces $0.5 - 0.5 = 0.0 \implies z = 0.0 \implies p = 1.0$, whereas a dataset with deviation $0.0$ produces $p = 0.8527$. This produces an inverted statistical significance ordering where closer adherence to $H_0$ receives a lower p-value than looser adherence.
7. Clamping the continuity-corrected deviation with $\max\left(0.0, |W_{\text{stat}} - \mu_W| - 0.5\right)$ ensures that whenever $|W_{\text{stat}} - \mu_W| \le 0.5$, $\text{deviation} = 0.0$, $z = 0.0$, and $p = 1.0$.

---

## 3. Caveats

1. The exact permutation test for small $N \le 20$ without normal approximation is not part of Increment 6 requirements; the normal approximation with continuity correction and tie adjustment is the specified standard across all sample sizes.
2. The fix preserves the property that for $|W_{\text{stat}} - \mu_W| \le 0.5$, the continuity correction floors the z-score at zero ($p = 1.0$), which is the standard behavior in SciPy (`scipy.stats.wilcoxon`) and R (`wilcox.test`).
3. No caveats regarding implementation complexity: the fix is a two-line replacement and completely local to `src/subtitle_workbench/metrics.py:428`.

---

## 4. Conclusion

The fix strategy for Bug 2 is unambiguous and mathematically verified:

### 4.1 Production Code Change in `src/subtitle_workbench/metrics.py`
Replace line 428:
```python
<<<<
        # Continuity-corrected z-score
        z = (abs(w_stat - mean_w) - 0.5) / math.sqrt(var_w)
====
        # Continuity-corrected z-score
        deviation = max(0.0, abs(w_stat - mean_w) - 0.5)
        z = deviation / math.sqrt(var_w)
>>>>
```

### 4.2 Test Additions in `tests/test_benchmark.py`
Add `test_paired_wilcoxon_symmetric_differences_exact_null` to `tests/test_benchmark.py`:
```python
def test_paired_wilcoxon_symmetric_differences_exact_null() -> None:
    """Verify paired Wilcoxon test yields p = 1.0 on symmetric non-zero error distributions."""
    # 4 pairs with symmetric non-zero errors: diffs [+1, -1, +2, -2]
    # W+ = 1.5 + 3.5 = 5.0, W- = 1.5 + 3.5 = 5.0 -> W_stat = 5.0, mean_W = 5.0
    # Deviation from mean is exactly 0.0; under H0, p-value must be 1.0
    base_4 = [11.0, 9.0, 12.0, 8.0]
    prop_4 = [10.0, 10.0, 10.0, 10.0]
    res_4 = paired_wilcoxon_test(base_4, prop_4)
    assert res_4.statistic == 5.0
    assert res_4.p_value == 1.0
    assert res_4.cliffs_delta == 0.0
    assert res_4.effect_size == "negligible"
    assert res_4.n_pairs == 4
    assert res_4.n_non_zero == 4

    # 6 pairs with symmetric non-zero errors: diffs [+1, -1, +2, -2, +3, -3]
    # W_stat = 10.5, mean_W = 10.5 -> deviation = 0.0 -> p = 1.0
    base_6 = [11.0, 9.0, 12.0, 8.0, 13.0, 7.0]
    prop_6 = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    res_6 = paired_wilcoxon_test(base_6, prop_6)
    assert res_6.statistic == 10.5
    assert res_6.p_value == 1.0
    assert res_6.cliffs_delta == 0.0
    assert res_6.effect_size == "negligible"

    # Near-null symmetry where |W - mean_W| == 0.5: diffs [+1, +2, -3, +4, -5]
    # W_stat = 7.0, mean_W = 7.5 -> deviation = max(0.0, 0.5 - 0.5) = 0.0 -> p = 1.0
    base_5 = [11.0, 12.0, 7.0, 14.0, 5.0]
    prop_5 = [10.0, 10.0, 10.0, 10.0, 10.0]
    res_5 = paired_wilcoxon_test(base_5, prop_5)
    assert res_5.statistic == 7.0
    assert res_5.p_value == 1.0

    # Asymmetric distribution where |W - mean_W| > 0.5: p-value must be < 1.0
    base_asym = [15.0, 16.0, 17.0, 18.0, 10.0]
    prop_asym = [10.0, 10.0, 10.0, 10.0, 10.0]
    res_asym = paired_wilcoxon_test(base_asym, prop_asym)
    assert res_asym.p_value < 1.0
```

### 4.3 Test Update in `tests/test_metrics_stress.py`
In `tests/test_metrics_stress.py`:
Remove `@pytest.mark.xfail(strict=True, ...)` from `test_paired_wilcoxon_exact_null_symmetry_continuity_correction_xfail` and rename it to `test_paired_wilcoxon_exact_null_symmetry_continuity_correction`.

---

## 5. Verification Method

1. Independent formula verification via Python CLI:
   ```powershell
   uv run python -c "from subtitle_workbench.metrics import paired_wilcoxon_test; res = paired_wilcoxon_test([11.0, 9.0, 12.0, 8.0], [10.0, 10.0, 10.0, 10.0]); assert res.p_value == 1.0, f'Expected 1.0, got {res.p_value}'"
   ```

2. Run test benchmark suite:
   ```powershell
   uv run --locked pytest tests/test_benchmark.py -v
   ```

3. Run stress test suite:
   ```powershell
   uv run --locked pytest tests/test_metrics_stress.py -v
   ```

4. Code formatting and linting:
   ```powershell
   uv run --locked ruff check src tests
   uv run --locked ruff format --check src tests
   ```

Invalidation Conditions:
- `paired_wilcoxon_test([11.0, 9.0, 12.0, 8.0], [10.0, 10.0, 10.0, 10.0]).p_value` evaluating to any value other than `1.0`.
- Any non-monotonic p-value relationship where $|W - \mu_W| = 0.0$ yields a smaller p-value than $|W - \mu_W| = 0.5$.
