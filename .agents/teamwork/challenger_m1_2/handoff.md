# Adversarial Challenge Handoff Report: Evaluation Metrics and Statistical Analysis

**Agent:** challenger_m1_2  
**Role:** EMPIRICAL CHALLENGER (critic, specialist)  
**Date:** 2026-10-26T03:49:30Z  
**Target:** `src/subtitle_workbench/metrics.py` (Worker: worker_m1_1, Milestone 1)  
**Verdict:** REQUEST_CHANGES  

---

## Challenge Summary

**Overall risk assessment**: HIGH

Empirical testing confirmed robust performance on high-volume inputs (100,000 synthetic boundary tokens evaluated in 0.08 seconds in $O(N)$ linear time), valid division-by-zero defenses on empty inputs, deterministic cluster-bootstrap resampling across seeds, and boundary metrics on extreme offsets (1,000s).

However, adversarial stress-testing identified two mathematically invalid implementations:
1. **Acc@20ms / Acc@50ms / Acc@100ms Floating-Point Epsilon Leak**: Exact boundary offsets calculated from integer audio sample counts (e.g., 320 samples at 16 kHz = 20.0 ms) produce 1-ULP floating point representation artifacts ($20.000000000000018$ ms at $t=1.0$ s). Because line 254 checks `errors <= 20.0` without an epsilon tolerance, boundary errors that are mathematically exactly 20.0 ms evaluate to `False`, causing `Acc@20ms` to drop from 100.0% to 0.0%.
2. **Paired Wilcoxon Signed-Rank Test Continuity Correction Inversion**: Line 428 calculates $z = (|W - \mu_W| - 0.5) / \sigma_W$, and line 430 takes `abs(z)`. When paired differences are symmetric around zero ($|W - \mu_W| = 0$), $(0 - 0.5)$ evaluates to $-0.5$, which `abs(z)` converts to $+0.5 / \sigma_W$. This inflates the z-score and depresses the two-sided p-value from 1.0 to 0.8527 (or 0.637 for $N=2$). Furthermore, a dataset with deviation 0.5 receives $p=1.0$, while a dataset with deviation 0.0 receives $p < 1.0$, creating an inverted significance ordering.

---

## 1. Observation

### 1.1 Direct Tool Execution Results

#### Verification 1: High Volume (100,000 Tokens) Fast Path
Command:
```powershell
uv run python -c "import time; from subtitle_workbench.models import WordToken; from subtitle_workbench.metrics import evaluate_alignment_boundaries; N=100000; ref=[WordToken(id=f'w_{i}', text='w', normalized='w', start=float(i), end=float(i)+0.5, confidence=1.0) for i in range(N)]; pred=[WordToken(id=f'w_{i}', text='w', normalized='w', start=float(i)+0.015, end=float(i)+0.515, confidence=1.0) for i in range(N)]; t0=time.perf_counter(); res=evaluate_alignment_boundaries(pred, ref); elapsed=time.perf_counter()-t0; print(f'100k tokens in {elapsed:.4f}s, MAE={res.mae:.2f}ms, Acc@20ms={res.acc_20ms:.1f}%')"
```
Output:
```
100k tokens in 0.0798s, MAE=15.00ms, Acc@20ms=100.0%
```

#### Verification 2: Empty Input Protection
Command:
```powershell
uv run python -c "from subtitle_workbench.metrics import evaluate_alignment_boundaries, MetricComputationError; from subtitle_workbench.models import WordToken; w=WordToken(id='w0', text='w', normalized='w', start=0.0, end=0.5, confidence=1.0); evaluate_alignment_boundaries([], [w])"
```
Output:
```
MetricComputationError: pred_tokens list is empty
```

#### Verification 3: Extreme Boundary Discrepancies (1000s off)
Command:
```powershell
uv run python -c "from subtitle_workbench.models import WordToken; from subtitle_workbench.metrics import evaluate_alignment_boundaries; ref=[WordToken(id='w0', text='w', normalized='w', start=0.0, end=0.5, confidence=1.0)]; pred=[WordToken(id='w0', text='w', normalized='w', start=1000.0, end=1000.5, confidence=1.0)]; res=evaluate_alignment_boundaries(pred, ref); print('MAE:', res.mae, 'Acc@20ms:', res.acc_20ms)"
```
Output:
```
MAE: 1000000.0 Acc@20ms: 0.0
```

#### Verification 4: Bug Reproduction 1 — Exact 20.0ms Shift at Non-Zero Timestamp
File: `src/subtitle_workbench/metrics.py:254-256`
Lines in file:
```python
254:     acc_20 = float(np.mean(errors <= 20.0) * 100.0)
255:     acc_50 = float(np.mean(errors <= 50.0) * 100.0)
256:     acc_100 = float(np.mean(errors <= 100.0) * 100.0)
```
Command:
```powershell
uv run python -c "from subtitle_workbench.models import WordToken; from subtitle_workbench.metrics import evaluate_alignment_boundaries; ref=WordToken(id='w0', text='w', normalized='w', start=16000/16000, end=24000/16000, confidence=1.0); pred=WordToken(id='w0', text='w', normalized='w', start=16320/16000, end=24320/16000, confidence=1.0); res=evaluate_alignment_boundaries([pred], [ref]); print('Boundary errors:', res.boundary_errors_ms); print('Acc@20ms:', res.acc_20ms)"
```
Output:
```
Boundary errors: [20.000000000000018, 20.000000000000018]
Acc@20ms: 0.0
```
Verbatim Error: 320 samples at 16 kHz is mathematically exactly 0.020 s (20.0 ms). At timestamp $t=1.0$ s ($16000/16000$), $16320/16000 - 1.0 = 0.020000000000000018$ s. Because `errors <= 20.0` has no numerical tolerance, `20.000000000000018 <= 20.0` is `False`. The evaluated accuracy drops from 100.0% to 0.0%.

#### Verification 5: Bug Reproduction 2 — Wilcoxon Signed-Rank Continuity Correction Inversion
File: `src/subtitle_workbench/metrics.py:428-430`
Lines in file:
```python
428:         z = (abs(w_stat - mean_w) - 0.5) / math.sqrt(var_w)
429:         # Two-sided p-value via math.erf
430:         p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
```
Command:
```powershell
uv run python -c "from subtitle_workbench.metrics import paired_wilcoxon_test; res_zero=paired_wilcoxon_test([11, 9, 12, 8], [10, 10, 10, 10]); print('Diffs [+1, -1, +2, -2] (deviation 0.0): W =', res_zero.statistic, 'p =', res_zero.p_value); res_half=paired_wilcoxon_test([11, 12, 7, 14, 5], [10, 10, 10, 10, 10]); print('Diffs [+1, +2, -3, +4, -5] (deviation 0.5): W =', res_half.statistic, 'p =', res_half.p_value)"
```
Output:
```
Diffs [+1, -1, +2, -2] (deviation 0.0): W = 5.0 p = 0.8526836843346426
Diffs [+1, +2, -3, +4, -5] (deviation 0.5): W = 7.0 p = 1.0
```
Verbatim Result: A dataset perfectly adhering to $H_0$ ($W = 5.0, \mu_W = 5.0$, deviation 0.0) yields $p = 0.8527$ instead of 1.0. A dataset with deviation 0.5 ($W = 7.0, \mu_W = 7.5$) yields $p = 1.0$.

---

## 2. Logic Chain

1. From Observation 1.1 (Verification 4), floating-point arithmetic on seconds converts to milliseconds via `abs(pred.start - ref.start) * 1000.0`. In standard IEEE-754 double precision, numbers such as $1.02$ cannot be represented exactly in binary floating point ($1.02_{10} = 1.019999999999999906...$).
2. When subtracting reference timestamp $1.0$ from prediction timestamp $1.02$, `1.02 - 1.0` yields `0.020000000000000018`. Multiplied by 1000.0, the resulting boundary error is $20.000000000000018$ ms.
3. In `evaluate_alignment_boundaries`, line 254 computes `acc_20 = float(np.mean(errors <= 20.0) * 100.0)`. Because $20.000000000000018 > 20.0$, the comparison evaluates to `False`. Therefore, ground truth alignment predictions shifted by exactly the benchmark threshold (20 ms, 50 ms, 100 ms) fail to count toward alignment accuracy whenever timestamps occur at non-zero temporal coordinates.
4. From Observation 1.1 (Verification 5), the standard continuity-corrected normal approximation of the Wilcoxon signed-rank test models discrete deviations toward the null mean $\mu_W$:
   $$\Delta_{\text{corrected}} = \max\left(0, |W - \mu_W| - 0.5\right)$$
   $$z = \frac{\Delta_{\text{corrected}}}{\sqrt{\text{Var}(W)}}$$
5. In `paired_wilcoxon_test`, lines 428-430 omit `max(0, ...)`:
   When $|W - \mu_W| < 0.5$, $|W - \mu_W| - 0.5$ is strictly negative. Applying `abs(z)` in `math.erf(abs(z) / math.sqrt(2.0))` reflects the negative term into a positive deviation $+0.5 / \sqrt{\text{Var}(W)}$.
6. Consequently, when the data conforms exactly to the null hypothesis ($|W - \mu_W| = 0.0$), the z-score is artificially non-zero ($z = 0.5 / \sigma$), causing the two-sided p-value to drop from 1.0 to $< 1.0$ (e.g. 0.8527). Furthermore, smaller deviations from the mean receive lower p-values than larger deviations, invalidating statistical tests in publication tables.

---

## 3. Adversarial Challenges

### [High] Challenge 1: Boundary Threshold Floating-Point Epsilon Precision Leak

- **Assumption challenged**: `errors <= 20.0`, `errors <= 50.0`, and `errors <= 100.0` reliably classify boundary alignments at the required standard acoustic thresholds.
- **Attack scenario**: Ground-truth tokens from TIMIT Core Test (16 kHz) positioned at $t \ge 1.0$ s with an alignment error of exactly 320 samples (20.0 ms) or 800 samples (50.0 ms).
- **Blast radius**: `Acc@20ms` and `Acc@50ms` falsely penalize mathematically exact alignments. Published benchmark tables in Paper 2 would report artificially degraded or jittery accuracy figures depending on utterance position.
- **Mitigation**: Introduce a numerical tolerance epsilon (e.g. `1e-4` ms) or round boundary errors before thresholding:
  ```python
  acc_20 = float(np.mean(errors <= 20.0 + 1e-4) * 100.0)
  acc_50 = float(np.mean(errors <= 50.0 + 1e-4) * 100.0)
  acc_100 = float(np.mean(errors <= 100.0 + 1e-4) * 100.0)
  ```

### [High] Challenge 2: Wilcoxon Continuity Correction Inversion on Null Deviations

- **Assumption challenged**: Continuity correction $(|W - \mu| - 0.5)/\sigma$ followed by `abs(z)` correctly computes two-sided p-values for all paired difference distributions.
- **Attack scenario**: Paired baseline and proposed benchmark runs producing symmetric rank differences where $|W_{\text{stat}} - \mu_W| < 0.5$.
- **Blast radius**: The test falsely rejects $H_0$ with $p < 1.0$ when the two models perform identically, and exhibits inverted monotonicity where a deviation of 0.0 receives a lower p-value than a deviation of 0.5.
- **Mitigation**: Clamp negative deviations to zero prior to z-score computation:
  ```python
  dev = max(0.0, abs(w_stat - mean_w) - 0.5)
  z = dev / math.sqrt(var_w)
  ```

---

## 4. Stress Test Results

| Test Scenario | Target Function | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|---|
| Empty `pred_tokens` | `evaluate_alignment_boundaries` | Raise `MetricComputationError` | Raised `MetricComputationError` | [PASS] |
| Empty `ref_tokens` | `evaluate_alignment_boundaries` | Raise `MetricComputationError` | Raised `MetricComputationError` | [PASS] |
| Empty both `pred` and `ref` | `evaluate_alignment_boundaries` | Raise `MetricComputationError` | Raised `MetricComputationError` | [PASS] |
| Zero duration ($start == end$) | `evaluate_alignment_boundaries` | Compute without ZeroDivisionError | Computed clean MAE=0.0, Acc@20=100% | [PASS] |
| Extreme discrepancy (1000s off) | `evaluate_alignment_boundaries` | Compute without float overflow | MAE=1,000,000.0 ms, Acc@20=0% | [PASS] |
| High volume (100k tokens) | `evaluate_alignment_boundaries` | Fast path in $O(N)$ linear time | 100k tokens evaluated in 0.0798s | [PASS] |
| Accuracy on discrete error distribution | `evaluate_alignment_boundaries` | Acc@20=20%, Acc@50=40%, Acc@100=80% | Exact match to expected percentages | [PASS] |
| Exact 20.0ms sample shift at $t=1.0$s | `evaluate_alignment_boundaries` | Acc@20ms == 100.0% | Acc@20ms == 0.0% ($20.000000000000018 > 20.0$) | [FAIL] |
| Cluster bootstrap reproducibility | `clustered_bootstrap_ci` | Identical seed yields identical CI | Exact identical CI produced across runs | [PASS] |
| Cluster bootstrap seed sensitivity | `clustered_bootstrap_ci` | Distinct seeds yield distinct CIs | Different seeds yield distinct percentiles | [PASS] |
| Identical paired arrays | `paired_wilcoxon_test` | Cliff's Delta == 0.0, p-value == 1.0 | Cliff's Delta = 0.0, p-value = 1.0 | [PASS] |
| Completely separated arrays ($x > y$) | `paired_wilcoxon_test` | Cliff's Delta == 1.0 | Cliff's Delta = 1.0, effect="large" | [PASS] |
| Completely separated arrays ($x < y$) | `paired_wilcoxon_test` | Cliff's Delta == -1.0 | Cliff's Delta = -1.0, effect="large" | [PASS] |
| Perfectly symmetric diffs ($|W-\mu|=0$) | `paired_wilcoxon_test` | p-value == 1.0 | p-value = 0.8527 (inverted continuity) | [FAIL] |

---

## 5. Caveats

1. Real TIMIT and Buckeye corpus files require university licensing; tests were verified against mathematically constructed synthetic utterances and exact discrete distributions.
2. In `_align_token_sequences`, Needleman-Wunsch fallback scales as $O(N \times M)$ when token sequences differ in text or length. For 2,000 mismatched tokens, execution took 2.52 seconds. In normal benchmark usage, utterances are segmented per sentence (5-30 tokens), where execution is $< 1$ ms.
3. Tests in `tests/test_metrics_stress.py` have been written cleanly and passed through `ruff check` and `ruff format`. The two identified bugs are documented via `@pytest.mark.xfail(strict=True)` to allow regression testing without blocking CI.

---

## 6. Conclusion

**Verdict: REQUEST_CHANGES**

The implementation in `src/subtitle_workbench/metrics.py` satisfies core performance and contract requirements, but contains two critical mathematical bugs that compromise scientific rigor:
1. `evaluate_alignment_boundaries` lacks epsilon tolerance on boundary thresholds, causing exact 20.0 ms, 50.0 ms, and 100.0 ms alignments to be counted as failures on non-zero timestamps.
2. `paired_wilcoxon_test` computes continuity correction without clamping negative deviations to zero, causing data consistent with $H_0$ to produce $p < 1.0$ and inverting p-value ordering.

Worker must apply the recommended mitigations in `src/subtitle_workbench/metrics.py`.

---

## 7. Verification Method

1. Run the adversarial stress-test suite:
   ```powershell
   uv run --locked pytest tests/test_metrics_stress.py -v
   ```
   Expected: 8 passed, 2 xfailed (reproducing both defects).

2. Run full test regression:
   ```powershell
   uv run --locked pytest
   ```
   Expected: 661 passed, 1 skipped, 2 xfailed in ~15s.

3. Verify zero linter warnings and clean formatting:
   ```powershell
   uv run --locked ruff check src tests
   uv run --locked ruff format --check src tests
   ```

Invalidation Conditions:
- `Acc@20ms` evaluating to 100.0% on `test_evaluate_alignment_boundaries_exact_sample_shift_xfail` without fixing line 254.
- `paired_wilcoxon_test([11, 9, 12, 8], [10, 10, 10, 10])` producing $p = 1.0$ without fixing line 428.
