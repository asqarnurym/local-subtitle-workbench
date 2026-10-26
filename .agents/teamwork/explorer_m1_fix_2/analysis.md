# Technical Analysis: IEEE-754 Precision Bug in Alignment Boundary Accuracy

**Author:** explorer_m1_fix_2  
**Role:** Teamwork Explorer (Investigator & Synthesizer)  
**Date:** 2026-10-26T03:54:00Z  
**Target:** `src/subtitle_workbench/metrics.py` (lines 223-270, `evaluate_alignment_boundaries`)  
**Status:** COMPLETE (Ready for Implementation)  

---

## 1. Executive Summary

Empirical challenge testing by `challenger_m1_2` revealed that `evaluate_alignment_boundaries` in `src/subtitle_workbench/metrics.py` strictly evaluates boundary thresholds without numerical tolerance (`errors <= 20.0`, `errors <= 50.0`, `errors <= 100.0`). When alignment timestamps are derived from standard discrete audio sample counts (e.g. 320 samples at 16 kHz = 20.0 ms) at non-zero temporal coordinates (such as $t = 1.0$ s), standard IEEE-754 binary floating-point subtraction yields $20.000000000000018$ ms. Because $20.000000000000018 > 20.0$, the comparison evaluates to `False`, causing Acc@20ms to drop from 100.0% to 0.0%.

This report provides the exhaustive IEEE-754 binary analysis, evaluates fix strategies, formulates the exact production code modification, and provides unit tests for `tests/test_benchmark.py`.

---

## 2. Review of `src/subtitle_workbench/metrics.py`

### 2.1 Function Context: Lines 223-270
The function `evaluate_alignment_boundaries` calculates start and end boundary discrepancies between predicted tokens and ground-truth reference tokens:

```python
223: def evaluate_alignment_boundaries(
224:     pred_tokens: list[WordToken] | list[PhonemeCue],
225:     ref_tokens: list[WordToken] | list[PhonemeCue],
226:     tolerance_ms: float = 20.0,
227: ) -> BoundaryEvaluation:
...
243:     boundary_errors: list[float] = []
244:     for pred, ref in matched_pairs:
245:         start_err = abs(pred.start - ref.start) * 1000.0
246:         end_err = abs(pred.end - ref.end) * 1000.0
247:         boundary_errors.append(start_err)
248:         boundary_errors.append(end_err)
249: 
250:     errors = np.asarray(boundary_errors, dtype=np.float64)
251:     mae = float(np.mean(errors))
252:     medae = float(np.median(errors))
253:     rmse = float(np.sqrt(np.mean(errors**2)))
254:     acc_20 = float(np.mean(errors <= 20.0) * 100.0)
255:     acc_50 = float(np.mean(errors <= 50.0) * 100.0)
256:     acc_100 = float(np.mean(errors <= 100.0) * 100.0)
```

### 2.2 Mechanism of Failure
1. `pred.start` and `ref.start` are floating-point seconds (`float64`).
2. Lines 245-246 compute the absolute difference in seconds and scale by 1000.0 to convert to milliseconds.
3. Summary metrics `mae`, `medae`, and `rmse` are continuous averages and medians. In test suites and reports, they are evaluated with floating-point tolerances (e.g. `math.isclose(mae, 20.0, abs_tol=1e-3)`).
4. In contrast, lines 254-256 compute threshold indicator ratios using strict boolean inequalities (`errors <= 20.0`, `errors <= 50.0`, `errors <= 100.0`).
5. A step function $I(x \le \theta)$ has zero tolerance for positive numerical noise: if $x = \theta + \delta$ where $\delta = 1.78 \times 10^{-14}$, $I(x \le \theta)$ abruptly drops from $1$ to $0$.

---

## 3. Mathematical and IEEE-754 Root Cause Analysis

### 3.1 Binary Floating-Point Representation (IEEE-754 binary64)
In 64-bit double precision, numbers are stored with 1 sign bit, 11 exponent bits (bias 1023), and 52 fraction bits (53 bits of precision):
$$x = (-1)^s \times 2^{e - 1023} \times (1.f_1 f_2 \dots f_{52})_2$$

Consider audio sampled at standard speech benchmark rate $f_s = 16000$ Hz (TIMIT / Buckeye):
- Reference onset at $t = 1.0$ s corresponds to sample 16000:
  $$t_{\text{ref}} = \frac{16000}{16000} = 1.0 = \text{0x1.0000000000000p+0}$$
  Bit pattern: `0x3ff0000000000000`. Exponent is $2^0$.
- Offset of exactly 20.0 ms = 0.020 seconds:
  $$\text{samples} = 0.020 \times 16000 = 320$$
  $$t_{\text{pred}} = \frac{16320}{16000} = 1.020\text{ s}$$

### 3.2 Loss of Precision during Addition to Exponent $2^0$
In decimal, $0.02 = 1/50$. In binary, $1/50$ is a repeating fraction:
$$0.02_{10} = 2^{-6} \times 1.28_{10} = 2^{-6} \times (1.0100011110101110000101000111101011100001010001111010\dots)_2$$
Stand-alone representation of $0.02$ in float64:
- Hexadecimal: `0x1.47ae147ae147bp-6` (ends with `7b`).

When $0.02$ is added to $1.0$:
- Exponent of $1.0$ is $2^0$.
- Exponent of $0.02$ is $2^{-6}$.
- To add significands, the significand of $0.02$ must be shifted right by 6 bit positions.
- The 6 least significant bits fall beyond the 53-bit mantissa window. Rounding to nearest even alters the trailing bits.
- Stored representation of $1.02$:
  - Hexadecimal: `0x1.051eb851eb852p+0`.
  - Exact decimal stored value:
    $$1.020000000000000017763568394002504646778106689453125$$

### 3.3 Catastrophic Subtraction and Scaling
When subtracting `pred.start - ref.start` in float64:
$$1.02 - 1.0 = \text{0x1.051eb851eb852p+0} - \text{0x1.0000000000000p+0} = \text{0x0.051eb851eb852p+0}$$
Normalizing by shifting left 6 bits (multiplying by $2^6$):
$$\text{normalized difference} = \text{0x1.47ae147ae1480p-6}$$
Notice the trailing nibbles: `480` vs the original `47b`. The difference has gained an artifact of:
$$\Delta = \text{0x1.47ae147ae1480p-6} - \text{0x1.47ae147ae147bp-6} = 5 \times 2^{-58} \approx 1.73 \times 10^{-17}\text{ s}$$

Now multiplying by $1000.0$ ($= \text{0x1.f4p+9}$):
$$\text{err\_ms} = \text{0x1.47ae147ae1480p-6} \times \text{0x1.f4p+9} = \text{0x1.4000000000005p+4}$$
Whereas the constant $20.0$ is:
$$20.0 = 1.25 \times 2^4 = \text{0x1.4000000000000p+4}$$

Subtracting the two:
$$\text{err\_ms} - 20.0 = \text{0x0.0000000000005p+4} = 5 \times 2^{-48} \approx 1.77635683940025 \times 10^{-14}\text{ ms}$$
In Python:
```python
>>> (16320 / 16000 - 1.0) * 1000.0
20.000000000000018
>>> 20.000000000000018 <= 20.0
False
```

### 3.4 Pervasiveness Across Thresholds and Audio Offsets
This issue is not isolated to 20 ms or $t = 1.0$ s:
- 50.0 ms (800 samples at 16 kHz) at $t = 1.0$ s:
  `((16800 / 16000) - 1.0) * 1000.0` = `50.00000000000004` ms ($> 50.0$ ms) -> `False`.
- 100.0 ms (1600 samples at 16 kHz) at $t = 1.0$ s:
  `((17600 / 16000) - 1.0) * 1000.0` = `100.00000000000009` ms ($> 100.0$ ms) -> `False`.
- Multiple timestamps:
  At $t = 1.0$ s: error is $+1.78 \times 10^{-14}$ ms (fails).
  At $t = 2.0$ s: error is $+1.78 \times 10^{-14}$ ms (fails).
  At $t = 5.0$ s: error is $-4.26 \times 10^{-14}$ ms (passes).
  At $t = 60.0$ s: error is $+3.13 \times 10^{-12}$ ms (fails).
  At $t = 300.0$ s: error is $+1.14 \times 10^{-11}$ ms (fails).

Because speech sentences occur at arbitrary timeline coordinates, this artifact introduces spurious timestamp-dependent jitter into published benchmark metrics.

---

## 4. Evaluation of Fix Strategies

| Strategy | Implementation | Pros | Cons | Verdict |
|---|---|---|---|---|
| **Strategy A: Epsilon in Inequality (Recommended)** | `errors <= 20.0 + EPSILON_MS` with `EPSILON_MS = 1e-4` | Vectorized $O(N)$, zero allocations, pure scalar addition, physically principled tolerance. | None. | **ACCEPTED** |
| **Strategy B: Array Rounding** | `np.round(errors, decimals=4) <= 20.0` | Eliminates representation noise. | Allocates temporary float64 array of size $2N$; slower. | Rejected |
| **Strategy C: Scalar Rounding in Loop** | `round(abs(pred.start - ref.start) * 1000.0, 4)` | Rounds errors before list insertion. | Modifies continuous raw error values; alters exact float MAE/RMSE calculations. | Rejected |
| **Strategy D: Integer Sample Math** | Track integer sample indices instead of seconds | Exact integer arithmetic. | Breaks models.py contract (`start: float`, `end: float` in seconds). | Rejected |

### 4.1 Physical Grounding of $\epsilon = 10^{-4}$ ms
- `1e-4` ms = $0.0001$ ms = $0.1$ microseconds = $100$ nanoseconds.
- Double-precision representation noise at $t \le 3600$ s is $< 10^{-9}$ ms. Therefore, `1e-4` ms is $> 100,000\times$ larger than maximum representation noise.
- Single audio sample intervals across common sample rates:
  - At 16 kHz: 1 sample = $62.5\,\mu\text{s} = 0.0625$ ms ($625\times$ larger than $\epsilon$).
  - At 48 kHz: 1 sample = $20.83\,\mu\text{s} \approx 0.0208$ ms ($208\times$ larger than $\epsilon$).
  - At 96 kHz: 1 sample = $10.42\,\mu\text{s} \approx 0.0104$ ms ($104\times$ larger than $\epsilon$).
  - At 192 kHz: 1 sample = $5.21\,\mu\text{s} \approx 0.0052$ ms ($52\times$ larger than $\epsilon$).
- Conclusion: An alignment that is off by even a single sample ($+1$ sample) will exceed the threshold by at least $52\times \epsilon$, guaranteeing 100% rejection. No false positive is mathematically possible.

---

## 5. Exact Proposed Code Changes

### 5.1 File: `src/subtitle_workbench/metrics.py`

#### Constant Addition (near top of module or right above `evaluate_alignment_boundaries`)
```python
# Numerical tolerance (0.1 microseconds = 1e-4 ms) for boundary threshold comparisons
# to absorb IEEE-754 binary floating-point representation artifacts (ULP noise).
# 1e-4 ms is >100,000x larger than float64 ULP noise and >50x smaller than 1 sample at 192 kHz.
BOUNDARY_EPSILON_MS: float = 1e-4
```

#### Lines 254-256 Replacement
```python
<<<<
    acc_20 = float(np.mean(errors <= 20.0) * 100.0)
    acc_50 = float(np.mean(errors <= 50.0) * 100.0)
    acc_100 = float(np.mean(errors <= 100.0) * 100.0)
====
    acc_20 = float(np.mean(errors <= 20.0 + BOUNDARY_EPSILON_MS) * 100.0)
    acc_50 = float(np.mean(errors <= 50.0 + BOUNDARY_EPSILON_MS) * 100.0)
    acc_100 = float(np.mean(errors <= 100.0 + BOUNDARY_EPSILON_MS) * 100.0)
>>>>
```

### 5.2 File: `src/subtitle_workbench/__init__.py`
Export `BOUNDARY_EPSILON_MS` in `__init__.py` if useful for external inspections (optional, but clean practice).

### 5.3 File: `tests/test_metrics_stress.py`
Remove `@pytest.mark.xfail(strict=True)` decorator from `test_evaluate_alignment_boundaries_exact_sample_shift_xfail` (lines 178-181) and rename to `test_evaluate_alignment_boundaries_exact_sample_shift`.

---

## 6. Formulated Unit Tests for `tests/test_benchmark.py`

The following tests must be appended to `tests/test_benchmark.py` under the boundary evaluation section:

```python
# ---------------------------------------------------------------------------
# Exact Sample Boundary Tests at Integer Seconds (Bug 1 Regression Suite)
# ---------------------------------------------------------------------------


def test_boundary_evaluation_exact_sample_boundaries_integer_seconds() -> None:
    """Exact sample shifts (320, 800, 1600 samples at 16kHz) at integer seconds

    must achieve exactly 100.0% accuracy for Acc@20ms, Acc@50ms, and Acc@100ms
    without floating-point representation failure.
    """
    sr = 16000
    # Create tokens positioned at integer seconds: 1.0s, 2.0s, 5.0s, 10.0s
    timestamps = [1.0, 2.0, 5.0, 10.0]
    ref_tokens = [
        WordToken(
            id=f"w{idx}",
            text=f"word{idx}",
            normalized=f"word{idx}",
            start=float(t),
            end=float(t) + 0.5,
            confidence=1.0,
        )
        for idx, t in enumerate(timestamps)
    ]

    # Case 1: Exact 20.0 ms shift (320 samples / 16000 Hz = 0.020 s)
    pred_20ms = [
        WordToken(
            id=w.id,
            text=w.text,
            normalized=w.normalized,
            start=w.start + (320 / sr),
            end=w.end + (320 / sr),
            confidence=1.0,
        )
        for w in ref_tokens
    ]
    eval_20 = evaluate_alignment_boundaries(pred_20ms, ref_tokens)
    assert math.isclose(eval_20.mae, 20.0, abs_tol=1e-3)
    assert eval_20.acc_20ms == 100.0
    assert eval_20.acc_50ms == 100.0
    assert eval_20.acc_100ms == 100.0

    # Case 2: Exact 50.0 ms shift (800 samples / 16000 Hz = 0.050 s)
    pred_50ms = [
        WordToken(
            id=w.id,
            text=w.text,
            normalized=w.normalized,
            start=w.start + (800 / sr),
            end=w.end + (800 / sr),
            confidence=1.0,
        )
        for w in ref_tokens
    ]
    eval_50 = evaluate_alignment_boundaries(pred_50ms, ref_tokens)
    assert math.isclose(eval_50.mae, 50.0, abs_tol=1e-3)
    assert eval_50.acc_20ms == 0.0
    assert eval_50.acc_50ms == 100.0
    assert eval_50.acc_100ms == 100.0

    # Case 3: Exact 100.0 ms shift (1600 samples / 16000 Hz = 0.100 s)
    pred_100ms = [
        WordToken(
            id=w.id,
            text=w.text,
            normalized=w.normalized,
            start=w.start + (1600 / sr),
            end=w.end + (1600 / sr),
            confidence=1.0,
        )
        for w in ref_tokens
    ]
    eval_100 = evaluate_alignment_boundaries(pred_100ms, ref_tokens)
    assert math.isclose(eval_100.mae, 100.0, abs_tol=1e-3)
    assert eval_100.acc_20ms == 0.0
    assert eval_100.acc_50ms == 0.0
    assert eval_100.acc_100ms == 100.0


def test_boundary_evaluation_sample_excess_discrimination() -> None:
    """A shift exceeding threshold by 1 sample (e.g. 321 samples = 20.0625ms)

    must evaluate to 0.0% accuracy, verifying that BOUNDARY_EPSILON_MS
    does not introduce false positives.
    """
    sr = 16000
    ref_tokens = [
        WordToken(
            id="w0",
            text="word",
            normalized="word",
            start=1.0,
            end=1.5,
            confidence=1.0,
        )
    ]

    # 321 samples at 16kHz = 20.0625 ms (> 20.0 ms threshold)
    pred_20_plus_1 = [
        WordToken(
            id="w0",
            text="word",
            normalized="word",
            start=1.0 + (321 / sr),
            end=1.5 + (321 / sr),
            confidence=1.0,
        )
    ]
    eval_res = evaluate_alignment_boundaries(pred_20_plus_1, ref_tokens)
    assert eval_res.acc_20ms == 0.0
    assert eval_res.acc_50ms == 100.0

    # 801 samples at 16kHz = 50.0625 ms (> 50.0 ms threshold)
    pred_50_plus_1 = [
        WordToken(
            id="w0",
            text="word",
            normalized="word",
            start=1.0 + (801 / sr),
            end=1.5 + (801 / sr),
            confidence=1.0,
        )
    ]
    eval_res_50 = evaluate_alignment_boundaries(pred_50_plus_1, ref_tokens)
    assert eval_res_50.acc_50ms == 0.0
    assert eval_res_50.acc_100ms == 100.0


def test_boundary_evaluation_phoneme_cues_exact_sample_boundaries() -> None:
    """Verify PhonemeCue boundaries at integer seconds with exact 320-sample shifts."""
    sr = 16000
    ref_phones = [
        PhonemeCue(phoneme="sh", start=1.0, end=1.2, confidence=1.0),
        PhonemeCue(phoneme="iy", start=1.2, end=1.4, confidence=1.0),
    ]
    pred_phones = [
        PhonemeCue(phoneme="sh", start=1.0 + (320 / sr), end=1.2 + (320 / sr), confidence=1.0),
        PhonemeCue(phoneme="iy", start=1.2 + (320 / sr), end=1.4 + (320 / sr), confidence=1.0),
    ]

    res = evaluate_alignment_boundaries(pred_phones, ref_phones)
    assert math.isclose(res.mae, 20.0, abs_tol=1e-3)
    assert res.acc_20ms == 100.0
    assert res.acc_50ms == 100.0
```

---

## 7. Synthesized Conclusion

1. **Root cause confirmed:** IEEE-754 representation of $(t + 0.02) - t$ at non-zero $t$ incurs 1-ULP upward rounding error ($20.000000000000018$ ms), causing strict `<=` comparison to fail.
2. **Identified blast radius:** Affects Acc@20ms, Acc@50ms, and Acc@100ms across all audio files whenever speech boundaries align with discrete sample boundaries.
3. **Recommended fix:** Introduce `BOUNDARY_EPSILON_MS = 1e-4` in `metrics.py` lines 254-256. This is optimal in speed, memory, and physical correctness.
4. **Test strategy formulated:** Three new unit test functions in `tests/test_benchmark.py` covering exact sample shifts at integer seconds, sample excess rejection (anti-false-positive check), and phoneme cues.
