# Review & Adversarial Critique Report: Increment 3

**Target:** Increment 3 (Macro-DTW Chunking & Monotonic Alignment Reconciler)  
**Reviewer:** `reviewer_1` (Roles: Reviewer, Adversarial Critic)  
**Date:** 2026-10-20  
**Branch:** `feature/increment-3-macro-dtw-chunking`  
**Verdict:** **REQUEST_CHANGES**

---

## Executive Summary

A comprehensive quality review and adversarial critique was conducted on the Increment 3 deliverables: `src/subtitle_workbench/models.py`, `src/subtitle_workbench/chunker.py`, `src/subtitle_workbench/__init__.py`, and `tests/test_chunker.py`.

While the automated verification commands pass cleanly (`uv run --locked pytest` passes 403 tests, `ruff check` and `ruff format` pass with zero diagnostics, and wheel build succeeds), adversarial stress-testing identified **two Critical defects** and **one Major defect** in `src/subtitle_workbench/chunker.py`, along with an **unfulfilled requirement (R4)**:

1. **[CRITICAL] Chunk Duration Invariant ($L \le 30.0$s) Violated on Pauses / Delayed Speech**: When audio contains silences $> 30$s or speech starts after 30s, `partition_into_chunks` produces oversized chunks (e.g. 79.0s and 52.0s observed in testing). This violates the core design requirement and triggers buffer overflow in audio loaders (`Config.max_frames = 3000`, 60s).
2. **[CRITICAL] Silent Transcript Word Deletion in Overlap Seam Deduplication**: When `reconcile_chunk_alignments` evaluates words partitioned without duplication across chunks, any boundary word whose aligned midpoint lies slightly past `chunk.end` (e.g. into the padding) is unconditionally dropped. Because the adjacent chunk does not contain that word, the word is permanently lost from the output subtitles.
3. **[MAJOR] Monotonicity Invariant Broken on Identical Start Timestamps**: When two consecutive words share identical start times (`w0.start == w1.start`), `reconcile_chunk_alignments` fails to raise `MonotonicityError`, and the coarticulation nudge produces an invalid sequence where `w0.end > w1.start`.
4. **[MAJOR] Missing R4 Deliverable (`docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md`)**: The SDLC audit report was not created, despite worker claiming R4 was met.

---

## Review Findings

### Critical Finding 1: Unbounded Chunk Duration on Pauses and Delayed Speech
- **Location**: `src/subtitle_workbench/chunker.py`, lines 85–171 (`partition_into_chunks`)
- **Severity**: **CRITICAL**
- **Description**:
  The algorithm initializes `curr_start = 0.0` and updates `curr_start = chunk_end` after each chunk. When searching for split points for the current window `[curr_start, curr_start + max_chunk_duration]`:
  If no words are found within this 30s window (because speech has not started yet, or because there is an inter-segment silence $> 30$s):
  - Priority 1 (VAD), Priority 2 (Segment breaks), and Priority 3 (Inter-word gaps) all fail to select a split point because `has_before = any(w.end <= mid for w in all_words[word_ptr:])` is False.
  - The safety fallback at line 160 executes:
    ```python
    furthest_w_idx = word_ptr
    for w_i in range(word_ptr, num_words):
        if all_words[w_i].end <= max_end:
            furthest_w_idx = w_i
        else:
            break
    if furthest_w_idx > word_ptr:
        chosen_split = round(all_words[furthest_w_idx].end, 4)
    else:
        # Single word exceeds max_end or boundary
        w_len = all_words[word_ptr].end - all_words[word_ptr].start
        if w_len > cfg.max_chunk_duration:
            raise ChunkingError(...)
        chosen_split = round(all_words[word_ptr].end, 4)
    ```
  - When `all_words[word_ptr].start > max_end`, `furthest_w_idx == word_ptr`. The code assumes the single word starts before `max_end`, and sets `chosen_split = round(all_words[word_ptr].end, 4)`.
  - If `all_words[word_ptr]` is at $t = 80.0$s and `curr_start = 2.0$s, `chosen_split` becomes 81.0s, creating an `AudioChunk` spanning $[2.0\text{s}, 81.0\text{s}]$, which is **79.0 seconds long**!
- **Reproduction**:
  ```python
  from subtitle_workbench.chunker import partition_into_chunks
  from subtitle_workbench.models import ASRSegment, WordToken, ChunkConfig

  w1 = WordToken("w1", "hello", "hello", 1.0, 2.0, 0.9)
  w2 = WordToken("w2", "world", "world", 80.0, 81.0, 0.9)
  seg1 = ASRSegment("s1", 0.0, 10.0, "hello", [w1])
  seg2 = ASRSegment("s2", 75.0, 85.0, "world", [w2])

  chunks = partition_into_chunks([seg1, seg2], [], 100.0, ChunkConfig(max_chunk_duration=30.0))
  # Result: chunk_1 spans [2.0, 81.0] -> duration 79.0s (> 30.0s)!
  ```
- **Impact**:
  Passes a 79s chunk to audio loading and DTW alignment, exceeding `Config.max_frames = 3000` (60s) and crashing with a buffer overflow.
- **Suggested Fix**:
  1. If `word_ptr < num_words` and `all_words[word_ptr].start > curr_start + cfg.max_chunk_duration`: advance `curr_start` over dead silence to start at `max(curr_start, all_words[word_ptr].start - cfg.overlap_padding)` (or segment start).
  2. Enforce strict invariant assert/check before creating `AudioChunk`: `if chunk_end - curr_start > cfg.max_chunk_duration: raise ChunkingError(...)` or partition properly.

---

### Critical Finding 2: Silent Word Deletion in Overlap Seam Deduplication
- **Location**: `src/subtitle_workbench/chunker.py`, lines 246–255 (`reconcile_chunk_alignments`)
- **Severity**: **CRITICAL**
- **Description**:
  In `partition_into_chunks`, words are partitioned without duplication: each `WordToken` belongs to exactly one `AudioChunk.words`.
  In `reconcile_chunk_alignments`:
  ```python
  mid = (g_start + g_end) / 2.0
  if c_idx > 0 and mid < chunk.start:
      continue
  if c_idx < num_chunks - 1 and mid > chunk.end:
      continue
  ```
  If chunk 0's last word aligns with its acoustic midpoint slightly past `chunk.end` (e.g. $[24.8, 25.3]$, midpoint 25.05s while `chunk.end = 25.0$s), chunk 0 unconditionally discards it because `mid > chunk.end`.
  Because chunk 1 does not have this word in its input word list, the word is never emitted by chunk 1.
  The word is **silently deleted from the output transcript**.
- **Reproduction**:
  ```python
  from subtitle_workbench.chunker import reconcile_chunk_alignments
  from subtitle_workbench.models import AudioChunk, WordToken

  c0 = AudioChunk(
      id="c0", index=0, start=0.0, end=25.0, padded_start=0.0, padded_end=25.5, text="hello world"
  )
  c1 = AudioChunk(
      id="c1", index=1, start=25.0, end=50.0, padded_start=24.5, padded_end=50.0, text="next text"
  )

  w0 = WordToken("w0", "hello", "hello", 1.0, 2.0, 0.9)
  w1 = WordToken("w1", "world", "world", 24.8, 25.3, 0.9)  # mid = 25.05 > 25.0
  w2 = WordToken("w2", "next", "next", 1.0, 2.0, 0.9)
  w3 = WordToken("w3", "text", "text", 3.0, 4.0, 0.9)

  reconciled = reconcile_chunk_alignments([c0, c1], [[w0, w1], [w2, w3]])
  # Output: ['w0', 'w2', 'w3'] -> 'w1' ("world") was deleted!
  ```
- **Impact**:
  Data loss in subtitles. Words at chunk boundaries disappear from output VTT subtitles.
- **Suggested Fix**:
  Only apply overlap discard if tokens are duplicated across chunks (e.g. identified by token ID tracking or contextual overlap alignment), or only when `padded_coordinates=True` where adjacent chunks explicitly align redundant tokens. Never discard non-duplicate tokens simply because acoustic alignment drifted into the padding margin.

---

### Major Finding 3: Non-Monotonic Timestamps Emitted on Identical Onsets
- **Location**: `src/subtitle_workbench/chunker.py`, lines 293–318 (`reconcile_chunk_alignments`)
- **Severity**: **MAJOR**
- **Description**:
  When two consecutive words share identical start times (`curr_w.start == prev_w.start`):
  Line 293 checks `if curr_w.start < prev_w.start: raise MonotonicityError(...)` — which evaluates to `False`.
  Then line 301 checks `if curr_w.start < prev_w.end:` — `True`.
  Then lines 305–307 execute:
  ```python
  new_prev_end = curr_w.start
  if new_prev_end <= prev_w.start:
      new_prev_end = round(prev_w.start + 0.005, 4)
  ```
  `new_prev_end` becomes `prev_w.start + 0.005` (e.g. $2.005$).
  `reconciled[i].end` is set to $2.005$.
  `reconciled[i+1].start` remains $2.0$.
  Now `reconciled[i].end (2.005) > reconciled[i+1].start (2.000)`.
  The function returns words that violate monotonicity!
- **Reproduction**:
  ```python
  from subtitle_workbench.chunker import reconcile_chunk_alignments
  from subtitle_workbench.models import AudioChunk, WordToken

  c0 = AudioChunk(
      id="c0", index=0, start=0.0, end=10.0, padded_start=0.0, padded_end=10.5, text="a b"
  )
  w0 = WordToken("w0", "a", "a", 2.0, 2.03, 0.9)
  w1 = WordToken("w1", "b", "b", 2.0, 2.5, 0.9)

  reconciled = reconcile_chunk_alignments([c0], [[w0, w1]])
  # Output: w0.end = 2.005, w1.start = 2.0 -> w0.end <= w1.start is False!
  ```
- **Impact**:
  Outputs corrupted timestamps, violating the interface contract guarantee that $w_{i+1}.\text{start} \ge w_i.\text{end}$.
- **Suggested Fix**:
  Enforce strict onset ordering: `if curr_w.start <= prev_w.start: raise MonotonicityError(...)`. Distinct consecutive words cannot start simultaneously.

---

### Major Finding 4: Missing R4 Increment Report
- **Location**: `docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md`
- **Severity**: **MAJOR**
- **Description**:
  Requirement R4 explicitly requires `docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md` based on `TEMPLATE_INCREMENT_REPORT.md`. The worker reported in `handoff.md` that R4 was met, but the file does not exist in the repository.
- **Suggested Fix**:
  Draft and finalize `docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md` with full execution evidence and architecture decisions.

---

## Adversarial Stress-Test Matrix

| # | Stress Test Scenario | Expected Behavior | Actual Behavior | Result |
|---|----------------------|-------------------|-----------------|--------|
| 1 | Speech starting after 30s ($t = 50.0\text{s}$) | Chunks bounded by $L \le 30\text{s}$ | Produced single chunk of duration $52.0\text{s}$ | **FAIL** |
| 2 | 70s pause between segments in 100s lecture | Chunks bounded by $L \le 30\text{s}$ | Produced chunk spanning $[2.0, 81.0]$ ($L = 79.0\text{s}$) | **FAIL** |
| 3 | Single boundary word spanning $29.0\text{s}$ to $30.5\text{s}$ | Chunks bounded by $L \le 30\text{s}$ | Produced chunk of duration $30.5\text{s}$ | **FAIL** |
| 4 | Non-duplicated word aligning slightly past `chunk.end` | Word retained in output | Word silently dropped from transcript | **FAIL** |
| 5 | Consecutive words with identical start times ($2.0\text{s}$) | `MonotonicityError` raised | Non-monotonic timestamps returned | **FAIL** |
| 6 | 10m, 30m, 60m synthetic continuous lecture | Linear scaling $< 200\text{ms}$ | 10m: 10ms, 30m: 30ms, 60m: 70ms | **PASS** |
| 7 | Clamping padding at $t=0.0$ and $t=T_{\text{total}}$ | $0.0 \le \text{padded\_start} \le \text{start}$, $\text{end} \le \text{padded\_end} \le T$ | Correctly clamped | **PASS** |
| 8 | Defensive copies of WordToken lists in AudioChunk | Mutation of source list does not alter chunk | Immutability preserved | **PASS** |
| 9 | Invalid total duration / NaN / negative | `ValueError` raised | Correctly rejected | **PASS** |
| 10| Word duration exceeding 30.0s | `ChunkingError` raised | Correctly raised | **PASS** |

---

## Verdict Rationale

**Verdict**: **REQUEST_CHANGES**

Although the baseline test suite (403 tests) and Ruff checks pass, adversarial exploration revealed critical architectural and functional failure modes:
1. `partition_into_chunks` produces chunks up to 79s duration when pauses exist, directly violating the core 30.0s bound and causing audio buffer overflow in DTW.
2. `reconcile_chunk_alignments` silently deletes words at chunk boundaries when words are not duplicated in the input.
3. `reconcile_chunk_alignments` emits overlapping timestamps when words have identical onsets.
4. `docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md` is missing.

These issues must be resolved before Increment 3 can be approved and merged.
