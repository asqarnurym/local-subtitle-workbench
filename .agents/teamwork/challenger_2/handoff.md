# Handoff Report: Increment 3 (`reconcile_chunk_alignments`)

**Agent**: `challenger_2` (critic, specialist)  
**Date**: 2026-10-20T15:23:00Z  
**Target Module**: `src/subtitle_workbench/chunker.py` (`reconcile_chunk_alignments`)  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

### Obs 1: Code Under Review (`src/subtitle_workbench/chunker.py`)
Lines 288–325 in `reconcile_chunk_alignments`:
```python
287:     # Monotonicity Verification & Resolution
288:     for i in range(len(reconciled) - 1):
289:         prev_w = reconciled[i]
290:         curr_w = reconciled[i + 1]
291: 
292:         # Onset corruption
293:         if curr_w.start < prev_w.start:
294:             raise MonotonicityError(...)
...
301:         if curr_w.start < prev_w.end:
302:             overlap = round(prev_w.end - curr_w.start, 4)
303:             if overlap <= 0.05:
304:                 # Nudge prev_w.end to eliminate overlap
305:                 new_prev_end = curr_w.start
306:                 if new_prev_end <= prev_w.start:
307:                     new_prev_end = round(prev_w.start + 0.005, 4)
308:                 reconciled[i] = WordToken(..., end=new_prev_end, ...)
309:             else:
310:                 raise MonotonicityError(...)
```

### Obs 2: Empirical Test of Simultaneous Word Onsets
Command run:
```powershell
uv run python -c "
from subtitle_workbench.models import AudioChunk, WordToken
from subtitle_workbench.chunker import reconcile_chunk_alignments

c = AudioChunk('c0', 0, 0.0, 10.0, 0.0, 10.5, 'text')
w0 = WordToken('w0', 'first', 'first', 1.0, 1.04, 0.9)
w1 = WordToken('w1', 'second', 'second', 1.0, 1.04, 0.9)
res = reconcile_chunk_alignments([c], [[w0, w1]])
print([(w.id, w.start, w.end) for w in res])
print('Is monotonic?', res[0].end <= res[1].start)
"
```
Direct output:
```
[('w0', 1.0, 1.005), ('w1', 1.0, 1.04)]
Is monotonic? False
```

### Obs 3: Empirical Test of Sub-0.1ms PhonemeCue Collapse
Command run:
```powershell
uv run python -c "
from subtitle_workbench.models import AudioChunk, PhonemeCue, WordToken
from subtitle_workbench.chunker import reconcile_chunk_alignments

c = AudioChunk('c0', 0, 0.0, 10.0, 0.0, 10.5, 'text')
p = PhonemeCue('P', 0.10001, 0.10004, 0.9)
w = WordToken('w0', 'text', 'text', 0.1, 0.2, 0.9, phonemes=[p])
reconcile_chunk_alignments([c], [[w]])
"
```
Direct output:
```
CRASH: ValueError: start must be strictly less than end
```

### Obs 4: Empirical Test Harness Execution (`scripts/stress_reconcile.py`)
Command: `uv run python scripts/stress_reconcile.py`
Direct output:
```
STRESS HARNESS COMPLETE: 21 PASSED, 0 FAILED, 3 FINDINGS
```
- Scalability: 20,000 words across 1,000 chunks (8.3h audio) reconciled in 296.8ms ($O(N)$ execution time).
- 100/100 randomized word order shuffles correctly triggered `MonotonicityError`.
- Padding seam words and redundant IDs across heavy (50%) overlaps are cleanly pruned.

---

## 2. Logic Chain

1. **Contract Invariant**: R2 specifies: *"Guarantee strict global monotonicity (`word[i+1].start >= word[i].end` or onset order); raise `MonotonicityError` if chronology is corrupted."*
2. **Detection Gap**: When $w_{i+1}.\text{start} == w_i.\text{start}$, line 293 evaluates `curr_w.start < prev_w.start` as `False`, bypassing the `MonotonicityError` branch (Obs 1, Obs 2).
3. **Flawed Mitigation**: In the subsequent coarticulation resolution branch, `new_prev_end` is assigned `curr_w.start`, which is $\le w_i.\text{start}$. Lines 306–307 artificially clamp `new_prev_end = round(prev_w.start + 0.005, 4)` to avoid `ValueError` on `WordToken` initialization (Obs 1).
4. **Monotonicity Breakdown**: This produces $w_i.\text{end} = 1.005 > w_{i+1}.\text{start} = 1.0$. Downstream pairwise order is broken without an exception being raised (Obs 2).
5. **Phoneme Rounding Vulnerability**: Lines 264–270 round phoneme start and end independently to 4 decimal places without the duration clamping safeguard present for `WordToken` on lines 239–240. Micro-phonemes ($< 0.1$ms) collapse and raise raw `ValueError` instead of being safely handled (Obs 3).

---

## 3. Caveats

- In practice, neural ASR aligners (Faster-Whisper / CTC forced aligners) output words with non-zero durations and positive inter-word shifts in the vast majority of clean recordings. The equal onset scenario is an adversarial edge case (e.g., overlapping speaker crosstalk or aligner token collisions).
- The test harness `scripts/stress_reconcile.py` was executed directly against pure Python data structures with zero mocks, strictly validating business logic invariants.

---

## 4. Conclusion

**REQUEST_CHANGES**  
The implementation in `src/subtitle_workbench/chunker.py` is robust across standard and boundary workflows (21/21 stress scenarios passed, linear scalability validated). However, changes are requested to address the monotonicity violation on equal word onsets and the micro-phoneme rounding exception:

1. **Line 293 in `src/subtitle_workbench/chunker.py`**:
   Change `if curr_w.start < prev_w.start:` to:
   ```python
   if curr_w.start <= prev_w.start:
       raise MonotonicityError(
           f"Chronology corruption at index {i + 1}: word '{curr_w.text}' "
           f"(start={curr_w.start:.4f}) starts before or simultaneously with previous word '{prev_w.text}' "
           f"(start={prev_w.start:.4f})"
       )
   ```
2. **Lines 264–270 in `src/subtitle_workbench/chunker.py`**:
   Ensure `p_end > p_start` after rounding:
   ```python
   reconciled_phonemes = []
   for p in w.phonemes:
       p_start = round(base_offset + p.start, 4)
       p_end = round(base_offset + p.end, 4)
       if p_end <= p_start:
           p_end = round(p_start + 0.001, 4)
       reconciled_phonemes.append(
           PhonemeCue(phoneme=p.phoneme, start=p_start, end=p_end, confidence=p.confidence)
       )
   ```

---

## 5. Verification Method

To independently verify these findings:

1. **Run full regression suite**:
   ```powershell
   uv run --locked pytest
   ```
   (Expect 403 passed, 1 skipped)

2. **Run the empirical stress test harness**:
   ```powershell
   uv run python scripts/stress_reconcile.py
   ```
   (Expect 21 PASS, 3 FINDINGS output)

3. **Verify Equal Onset Collision Reproduction**:
   ```powershell
   uv run python -c "from subtitle_workbench.models import AudioChunk, WordToken; from subtitle_workbench.chunker import reconcile_chunk_alignments; c = AudioChunk('c0', 0, 0.0, 10.0, 0.0, 10.5, 'text'); w0 = WordToken('w0', 'a', 'a', 1.0, 1.04, 0.9); w1 = WordToken('w1', 'b', 'b', 1.0, 1.04, 0.9); res = reconcile_chunk_alignments([c], [[w0, w1]]); print('Non-monotonic result:', res[0].end, '>', res[1].start)"
   ```
   (Outputs `Non-monotonic result: 1.005 > 1.0`)

4. **Verify Sub-0.1ms Phoneme Crash Reproduction**:
   ```powershell
   uv run python -c "from subtitle_workbench.models import AudioChunk, PhonemeCue, WordToken; from subtitle_workbench.chunker import reconcile_chunk_alignments; c = AudioChunk('c0', 0, 0.0, 10.0, 0.0, 10.5, 'text'); p = PhonemeCue('P', 0.10001, 0.10004, 0.9); w = WordToken('w0', 'text', 'text', 0.1, 0.2, 0.9, phonemes=[p]); reconcile_chunk_alignments([c], [[w]])"
   ```
   (Outputs `ValueError: start must be strictly less than end`)
