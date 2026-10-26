# Technical Analysis: Wilcoxon Signed-Rank Continuity Correction Inversion Fix

**Author:** explorer_m1_fix_3  
**Target:** `src/subtitle_workbench/metrics.py:426-432` (`paired_wilcoxon_test`)  
**Parent Task:** Bug 2 reported by challenger_m1_2  
**Constraint:** Pure ASCII formatting ([+], [-], [*], [OK], [FAIL], ->, |). Zero-Emoji rule strictly enforced.  

---

## 1. Executive Summary

In `src/subtitle_workbench/metrics.py`, the paired Wilcoxon signed-rank test implementation (`paired_wilcoxon_test`) applies a continuity correction to the normal approximation of the test statistic:
```python
z = (abs(w_stat - mean_w) - 0.5) / math.sqrt(var_w)
p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
```

When sample error distributions are symmetric around zero under the null hypothesis $H_0$, $|W_{\text{stat}} - \mu_W| = 0.0$. Subtracting the continuity correction ($0.5$) yields $-0.5$, which the subsequent `abs(z)` evaluation reflects into a positive z-score:
$$z = \frac{|0.0 - 0.5|}{\sqrt{\text{Var}(W)}} = \frac{+0.5}{\sigma_W} > 0$$

This non-zero z-score depresses the two-sided p-value from $1.0$ down to $0.8527$ ($N=4$), $0.9158$ ($N=6$), or $0.9592$ ($N=10$). Furthermore, a dataset with deviation $|W - \mu_W| = 0.5$ receives $p = 1.0$, while a dataset with $|W - \mu_W| = 0.0$ receives $p = 0.8527$. This produces an inverted statistical significance ordering where datasets adhering more closely to $H_0$ appear more statistically significant (lower p-value).

The exact mathematical fix clamps negative continuity-corrected deviations to zero before dividing by standard error:
```python
deviation = max(0.0, abs(w_stat - mean_w) - 0.5)
z = deviation / math.sqrt(var_w)
```

This guarantees that when $|W_{\text{stat}} - \mu_W| \le 0.5$, $z = 0.0$ and $p = 1.0$.

---

## 2. Mathematical Root Cause Analysis

### 2.1 Theoretical Background
The Wilcoxon signed-rank test evaluates paired observations $(X_i, Y_i)$ with differences $D_i = X_i - Y_i$. Non-zero differences $|D_i|$ are ranked with average ranks assigned to ties. The test statistic $W$ is:
$$W = \min(W^+, W^-)$$
where $W^+ = \sum_{D_i > 0} R_i$ and $W^- = \sum_{D_i < 0} R_i$.

Under $H_0$ (symmetric distribution around zero):
$$\mu_W = \frac{n_r (n_r + 1)}{4}$$
$$\text{Var}(W) = \frac{n_r (n_r + 1)(2n_r + 1)}{24} - \sum_{k} \frac{t_k^3 - t_k}{48}$$

Because $W$ is discrete (taking integer or half-integer values), the normal approximation uses a continuity correction to approximate the discrete distribution. The continuity correction shifts the observed test statistic by $0.5$ toward the mean $\mu_W$:
- If $W > \mu_W$, evaluate $W - 0.5$
- If $W < \mu_W$, evaluate $W + 0.5$
- In terms of absolute deviation, $|W - \mu_W|$ is shifted by $-0.5$ towards $0$:
$$\text{deviation} = \max\left(0.0, |W - \mu_W| - 0.5\right)$$

### 2.2 The Inversion Defect in Existing Code
In `src/subtitle_workbench/metrics.py:428-430`:
```python
z = (abs(w_stat - mean_w) - 0.5) / math.sqrt(var_w)
p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
```

Consider the case where differences are balanced/symmetric:
Example 1: 4 pairs with differences $[+1.0, -1.0, +2.0, -2.0]$
- $n_r = 4$, $\mu_W = 4 \times 5 / 4 = 5.0$
- Ranks for $|1|$ are $1$ and $2$ -> average rank $1.5$ (tie of length 2)
- Ranks for $|2|$ are $3$ and $4$ -> average rank $3.5$ (tie of length 2)
- $W^+ = 1.5 + 3.5 = 5.0$, $W^- = 1.5 + 3.5 = 5.0$
- $W_{\text{stat}} = \min(5.0, 5.0) = 5.0$
- Absolute deviation: $|W_{\text{stat}} - \mu_W| = |5.0 - 5.0| = 0.0$
- Tie adjustment: $\text{tie\_term} = 2 \times (2^3 - 2)/48 = 12/48 = 0.25$
- $\text{Var}(W) = (4 \times 5 \times 9)/24 - 0.25 = 7.5 - 0.25 = 7.25$
- $\sigma_W = \sqrt{7.25} \approx 2.69258$

Current computation:
$$z = \frac{0.0 - 0.5}{2.69258} = -0.185695$$
Because line 430 computes `abs(z)`:
$$\text{abs}(z) = +0.185695$$
$$\text{erf}\left(\frac{0.185695}{\sqrt{2}}\right) = \text{erf}(0.131306) \approx 0.147316$$
$$p = 2.0 \times \left(1.0 - 0.5 \times (1.0 + 0.147316)\right) = 2.0 \times (1.0 - 0.573658) = 0.852684$$

Result: Under complete symmetry ($H_0$ is exact), $p = 0.8527 \neq 1.0$.

Example 2: 5 pairs with differences $[+1.0, +2.0, -3.0, +4.0, -5.0]$
- $W^+ = 1 + 2 + 4 = 7.0$
- $W^- = 3 + 5 = 8.0$
- $W_{\text{stat}} = 7.0$
- $\mu_W = 5 \times 6 / 4 = 7.5$
- $|W_{\text{stat}} - \mu_W| = 0.5$
- Line 428 computes: $z = (0.5 - 0.5)/\sigma_W = 0.0$
- Line 430 computes: $p = 1.0$

Comparison:
- Deviation = 0.0 -> $p = 0.8527$
- Deviation = 0.5 -> $p = 1.0000$

The ordering is inverted: a larger deviation from the null mean produces a higher p-value than zero deviation.

---

## 3. Formulated Exact Fix

### 3.1 Code Change in `src/subtitle_workbench/metrics.py`

Location: Lines 426-432
Before:
```python
    if var_w <= 0.0:
        p_val = 1.0
    else:
        # Continuity-corrected z-score
        z = (abs(w_stat - mean_w) - 0.5) / math.sqrt(var_w)
        # Two-sided p-value via math.erf
        p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
        p_val = max(0.0, min(1.0, float(p_val)))
```

After:
```python
    if var_w <= 0.0:
        p_val = 1.0
    else:
        # Continuity-corrected z-score
        deviation = max(0.0, abs(w_stat - mean_w) - 0.5)
        z = deviation / math.sqrt(var_w)
        # Two-sided p-value via math.erf
        p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
        p_val = max(0.0, min(1.0, float(p_val)))
```

### 3.2 Mathematical Verification of the Fix
With `deviation = max(0.0, abs(w_stat - mean_w) - 0.5)`:
1. When $|W_{\text{stat}} - \mu_W| = 0.0$:
   $$\text{deviation} = \max(0.0, 0.0 - 0.5) = 0.0$$
   $$z = 0.0 / \sigma_W = 0.0$$
   $$\text{erf}(0.0) = 0.0$$
   $$p = 2.0 \times (1.0 - 0.5 \times (1.0 + 0.0)) = 2.0 \times 0.5 = 1.0$$
   [OK]

2. When $0.0 < |W_{\text{stat}} - \mu_W| \le 0.5$:
   $$\text{deviation} = \max(0.0, \le 0.0) = 0.0 \implies z = 0.0 \implies p = 1.0$$
   [OK]

3. When $|W_{\text{stat}} - \mu_W| > 0.5$:
   $$\text{deviation} = |W_{\text{stat}} - \mu_W| - 0.5 > 0.0 \implies z > 0.0 \implies p < 1.0$$
   Monotonically decreasing as deviation increases.
   [OK]

---

## 4. Test Suite Formulation

### 4.1 Unit Test in `tests/test_benchmark.py`

Add the following standalone test function to `tests/test_benchmark.py`:

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

### 4.2 Updating Existing Stress Test in `tests/test_metrics_stress.py`

In `tests/test_metrics_stress.py`, lines 244-258 currently have an `@pytest.mark.xfail(strict=True, ...)` decorator:
```python
@pytest.mark.xfail(
    strict=True,
    reason="Continuity correction inversion bug: |W - mean| == 0 produces z = -0.5/se -> p < 1.0",
)
def test_paired_wilcoxon_exact_null_symmetry_continuity_correction_xfail() -> None: ...
```

Once the worker applies `deviation = max(0.0, abs(w_stat - mean_w) - 0.5)`, this test will pass. The worker should remove the `@pytest.mark.xfail` decorator and rename the function to:
```python
def test_paired_wilcoxon_exact_null_symmetry_continuity_correction() -> None:
    """Perfect symmetry around zero has |W - mean| == 0 and yields p-value == 1.0."""
    base = [11.0, 9.0, 12.0, 8.0]
    prop = [10.0, 10.0, 10.0, 10.0]
    res = paired_wilcoxon_test(base, prop)
    assert math.isclose(res.p_value, 1.0, abs_tol=1e-5)
```

---

## 5. Risk Assessment and Impact

- **Production code change**: exactly 2 lines in `src/subtitle_workbench/metrics.py` (lines 428-429).
- **Blast radius**: isolated to `paired_wilcoxon_test` normal approximation branch.
- **Existing test suite**: zero regressions. The existing test `test_paired_wilcoxon_test_significance` in `tests/test_benchmark.py` uses 100 randomly sampled points with large difference (`p < 0.001`), and identical arrays (`p = 1.0` via early return at line 388), both of which continue to pass identically.
- **Downstream impact**: Milestone 2 runner (`scripts/speech_benchmark.py`) and Milestone 3 paper table generator (`scripts/generate_paper_tables.py`) generate Table 3 (Statistical Significance). Ensuring that models with identical or symmetric performance produce $p = 1.0$ prevents false significance claims in the academic paper.
