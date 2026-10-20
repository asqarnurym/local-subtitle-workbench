# Empirical Challenge Report: Increment 3 (`reconcile_chunk_alignments`)

**Agent**: `challenger_2` (critic, specialist)  
**Date**: 2026-10-20T15:20:00Z  
**Target Module**: `src/subtitle_workbench/chunker.py` (`reconcile_chunk_alignments`)  
**Test Harness**: `scripts/stress_reconcile.py` (21 executed test cases)  
**Verdict**: **REQUEST_CHANGES**

---

## Challenge Summary

- **Overall Risk Assessment**: **MEDIUM**
- **Core Functionality**: Coordinate translation ($t_{\text{global}} = \text{chunk.start} + t_{\text{local}}$), padding seam deduplication, duplicate ID suppression, and scaling over 20,000 words across 1,000 chunks (8.3 hours in 296ms) are empirically proven robust and performant.
- **Blocking Issue**: When two distinct word tokens have identical onset timestamps ($w_{i+1}.\text{start} == w_i.\text{start}$) and duration $\le 0.05$s, `reconcile_chunk_alignments` fails to raise `MonotonicityError`, attempts a coarticulation nudge that clamps $w_i.\text{end} = w_i.\text{start} + 0.005$s, and outputs non-monotonic, overlapping words ($w_i.\text{end} > w_{i+1}.\text{start}$) in direct violation of R2 and interface contracts.

---

## Challenges & Empirical Findings

### [Medium] Challenge 1: Equal Onset Collision Produces Non-Monotonic Output When Overlap $\le 50$ms

- **Assumption Challenged**: That the monotonicity verification loop in lines 288–325 strictly enforces $w_{i+1}.\text{start} \ge w_i.\text{end}$ and chronological order under all input permutations.
- **Attack Scenario**:
  Pass two distinct words with identical start times and short duration into `reconcile_chunk_alignments`:
  ```python
  c0 = AudioChunk("c0", 0, 0.0, 10.0, 0.0, 10.5, "two words")
  w0 = WordToken("w0", "word0", "word0", 1.0, 1.04, 0.9)
  w1 = WordToken("w1", "word1", "word1", 1.0, 1.04, 0.9)
  res = reconcile_chunk_alignments([c0], [[w0, w1]])
  ```
- **Observed Behavior**:
  1. Line 293: `if curr_w.start < prev_w.start:` evaluates `1.0 < 1.0` as `False`. `MonotonicityError` is NOT raised.
  2. Line 301: `if curr_w.start < prev_w.end:` evaluates `1.0 < 1.04` as `True`. Overlap is $0.04$s ($\le 0.05$s).
  3. Lines 305–307:
     ```python
     new_prev_end = curr_w.start  # 1.0
     if new_prev_end <= prev_w.start:  # 1.0 <= 1.0 is True!
         new_prev_end = round(prev_w.start + 0.005, 4)  # 1.005
     ```
  4. Returns `res[0].end = 1.005` and `res[1].start = 1.0`.
  5. Verification `res[0].end <= res[1].start` fails (`1.005 <= 1.0` is `False`).
- **Blast Radius**:
  Violates R2 contract: *"Guarantee strict global monotonicity (word[i+1].start >= word[i].end or onset order); raise MonotonicityError if chronology is corrupted."*
  Downstream subtitle generators and WebVTT exporters (`Cue` model requires strictly ordered non-overlapping intervals) will crash or emit overlapping visual subtitles.
- **Mitigation**:
  In `src/subtitle_workbench/chunker.py`, line 293:
  ```python
  # Change strict less-than to less-than-or-equal:
  if curr_w.start <= prev_w.start:
      raise MonotonicityError(
          f"Chronology corruption at index {i + 1}: word '{curr_w.text}' "
          f"(start={curr_w.start:.4f}) starts before or simultaneously with previous word '{prev_w.text}' "
          f"(start={prev_w.start:.4f})"
      )
  ```

---

### [Low] Challenge 2: Sub-0.1ms PhonemeCue Duration Rounding Collapse

- **Assumption Challenged**: That phoneme cues within valid `WordToken`s are safely translated without exceptions.
- **Attack Scenario**:
  A valid `PhonemeCue` with duration $< 0.0001$s (e.g., `start=0.10001, end=0.10004`, where `start < end` holds) is contained in a `WordToken`:
  ```python
  p = PhonemeCue("P", 0.10001, 0.10004, 0.9)
  w = WordToken("w0", "text", "text", 0.1, 0.2, 0.9, phonemes=[p])
  reconcile_chunk_alignments([c0], [[w]])
  ```
- **Observed Behavior**:
  Lines 264–268 round both timestamps to 4 decimal places:
  `round(0.0 + 0.10001, 4) == 0.1000`
  `round(0.0 + 0.10004, 4) == 0.1000`
  `PhonemeCue(phoneme='P', start=0.1, end=0.1, confidence=0.9)` raises `ValueError: start must be strictly less than end`.
  While `WordToken` has a safeguard (line 239: `if g_end <= g_start: g_end = round(g_start + 0.01, 4)`), `PhonemeCue` lacks a corresponding safeguard.
- **Blast Radius**: Unhandled `ValueError` crash during alignment reconciliation if acoustic aligner emits micro-phoneme frames.
- **Mitigation**:
  In `src/subtitle_workbench/chunker.py`, line 264, add a duration safeguard when creating reconciled phonemes:
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

### [Low] Challenge 3: Word End Nudging Leaves Nested Phonemes Outside Word Boundary

- **Assumption Challenged**: That coarticulation nudging preserves hierarchical containment invariants of child phonemes.
- **Attack Scenario**:
  Word `cat` spans `[1.0, 1.20]`, with trailing phoneme `T` at `[1.18, 1.20]`. Word `sat` starts at `1.17` (30ms overlap).
  `reconcile_chunk_alignments` nudges `cat` end to `1.17`, but copies `phonemes` unchanged:
  ```python
  reconciled[i] = WordToken(..., end=new_prev_end, phonemes=prev_w.phonemes, ...)
  ```
- **Observed Behavior**:
  Word ends at `1.17`s, but child phoneme `T` ends at `1.20`s.
- **Blast Radius**:
  Semantic desynchronization: child phonemes extend beyond parent word boundary. Does not crash `WordToken.__post_init__` because `WordToken` does not enforce phoneme bounding box, but may cause visual artifacts in phoneme-level highlight rendering.
- **Mitigation**:
  Clamp child phoneme end timestamps to `min(p.end, new_prev_end)` when nudging word end.

---

## Stress Test Results

Full execution output of `scripts/stress_reconcile.py`:

| # | Dimension | Scenario | Expected | Actual | Status |
|---|-----------|----------|----------|--------|--------|
| 1 | Coordinates | Standard coordinate translation ($t_{\text{global}} = \text{chunk.start} + t_{\text{local}}$) | Exact match | Exact match | **PASS** |
| 2 | Coordinates | Padded coordinate translation ($t_{\text{global}} = \text{chunk.padded\_start} + t_{\text{local}}$) | Exact match | Exact match | **PASS** |
| 3 | Coordinates | Nested phoneme coordinate translation | Cues translated and preserved | Translated and preserved | **PASS** |
| 4 | Coordinates | Deep metadata preservation (id, text, normalized, confidence, offsets) | All fields intact | All fields intact | **PASS** |
| 5 | Deduplication | Seam deduplication across overlapping chunks | Padding tokens discarded, duplicates dropped | Padding tokens dropped, duplicates dropped | **PASS** |
| 6 | Deduplication | Word exactly on seam midpoint ($mid == \text{chunk.start}$) | Discarded in leading, kept in trailing | Cleanly deduplicated | **PASS** |
| 7 | Deduplication | Heavy chunk overlap (50% overlap, 15s shared region) | Redundant IDs suppressed | Redundant IDs suppressed | **PASS** |
| 8 | Deduplication | Intermediate chunk with all words in padding seams | Intermediate padding words discarded | Cleanly discarded | **PASS** |
| 9 | Monotonicity | Intra-chunk inverted onset ($w_{i+1}.\text{start} < w_i.\text{start}$) | MonotonicityError | MonotonicityError raised | **PASS** |
| 10 | Monotonicity | Cross-chunk inverted onset | MonotonicityError | MonotonicityError raised | **PASS** |
| 11 | Monotonicity | Severe intra-chunk overlap (>50ms) | MonotonicityError | MonotonicityError raised | **PASS** |
| 12 | Monotonicity | Severe cross-chunk overlap (>50ms) | MonotonicityError | MonotonicityError raised | **PASS** |
| 13 | Monotonicity | Disordered words (100 random permutations) | 100/100 raise error | 100/100 raised error | **PASS** |
| 14 | Monotonicity | Coarticulation overlap ($\le 50$ms) | Nudged to $w_i.\text{end} \le w_{i+1}.\text{start}$ | Nudged and strictly monotonic | **PASS** |
| 15 | Monotonicity | Cascading minor overlaps across 5 words | All 5 words monotonic | All 5 words strictly monotonic | **PASS** |
| 16 | Corner Cases | Equal onset collision ($w_{i+1}.\text{start} == w_i.\text{start}$) with overlap $\le 50$ms | MonotonicityError or monotonic fix | Non-monotonic output produced | **FAIL / FINDING 1** |
| 17 | Corner Cases | Sub-0.1ms phoneme duration ($< 0.0001$s) | Handled safely | ValueError raised on 4-dec rounding | **FAIL / FINDING 2** |
| 18 | Corner Cases | Phoneme cue containment after word end nudging | Phonemes clamped to word end | Phoneme extends past word end | **FAIL / FINDING 3** |
| 19 | Boundaries | Empty inputs `([], [])` | Return `[]` | Returned `[]` | **PASS** |
| 20 | Boundaries | Chunks with empty word lists `([c0, c1], [[], []])` | Return `[]` | Returned `[]` | **PASS** |
| 21 | Boundaries | Mismatched chunk and word list counts | ChunkingError | ChunkingError raised | **PASS** |
| 22 | Boundaries | Single-word single-chunk | Return single WordToken | Single WordToken returned | **PASS** |
| 23 | Boundaries | Artificial zero-duration word (`end == start`) | Clamped to $+0.01$s | Clamped to $+0.01$s | **PASS** |
| 24 | Scalability | 20,000 words across 1,000 chunks (8.3h audio) | Execution $< 500$ms, $O(N)$ memory | Reconciled in 296.8ms | **PASS** |

---

## Unchallenged Areas

1. `partition_into_chunks` anchor selection hierarchy (assigned to peer `challenger_1`).
2. Silero-VAD and Faster-Whisper neural weight inference (Increment 2 scope, tested with isolated unit mocks).
3. Audio DTW warp path calculation (tested in Increment 1 suite).

---

## Final Verdict

**REQUEST_CHANGES**  
The implementation is exceptionally well-structured, performant, and passes 21 stress scenarios with zero regressions across the 404-test testbed. However, the equal-onset monotonicity breach (Challenge 1) is a direct functional defect that violates the core monotonicity guarantee. Changing line 293 in `src/subtitle_workbench/chunker.py` from `<` to `<=` will cleanly resolve Challenge 1.
