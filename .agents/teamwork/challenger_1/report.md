# Empirical Challenge Report: Increment 3 (Macro-Chunking)

## Verdict: REQUEST_CHANGES

## Challenge Summary

**Overall risk assessment**: **CRITICAL**

Empirical stress testing of `partition_into_chunks` revealed two major defects:
1. **Critical Duration Bound Violation**: When audio contains silence or pauses > 30.0s (e.g., sparse speech, lecture pauses, or leading silence before the first word), `partition_into_chunks` creates chunks whose duration significantly exceeds `max_chunk_duration` (e.g. 48.0s, 70.0s, 112.0s). This invalidates the core architectural premise of Macro-DTW, which relies on chunks strictly bounded by $L \le 30.0$s to prevent quadratic memory explosion and audio frame loader overflow (`Config.max_frames = 3000`, 60s).
2. **High Clamping Invariant Violation**: Floating-point rounding with `round(..., 4)` after `min(total_dur, ...)` causes `chunk.padded_end` and `chunk.end` to strictly exceed `total_duration` whenever `total_duration` has sub-millisecond precision (e.g. `total_dur = 10.00006` produces `padded_end = 10.0001 > total_dur`).

---

## Challenges

### [Critical] Challenge 1: Unbounded Chunk Duration on Pauses / Gaps > 30.0s

- **Assumption challenged**: The implementation in `src/subtitle_workbench/chunker.py` assumes that speech occurs at least once every 30.0 seconds, and that in the safety fallback (lines 152–170), checking that a single word does not exceed 30.0s (`w_len = word.end - word.start <= max_chunk_duration`) guarantees that the enclosing chunk `[curr_start, word.end]` does not exceed 30.0s.
- **Attack scenario**:
  - A lecture where a professor pauses for 110s between discussion sections.
  - A recording where speech begins after 45s of leading silence.
  - Sparse speech segments separated by gaps $> 30.0$s.
  - In each case:
    1. Priority 1 (VAD silence), Priority 2 (segment breaks), and Priority 3 (word gaps) find no candidate splits in `[curr_start, curr_start + 30.0]` because `has_before` requires a word ending $\le 30.0$s.
    2. The loop enters the safety fallback at line 161.
    3. The code sets `chosen_split = round(all_words[word_ptr].end, 4)`.
    4. The chunk is constructed with `start = curr_start` and `end = chosen_split`.
    5. The resulting chunk duration is `chunk.end - chunk.start = all_words[word_ptr].end - curr_start`, which equals the entire gap duration (e.g., 48.0s, 70.0s, 112.0s).
- **Blast radius**:
  - Violates Requirement R2: *"Partition continuous audio stream into sequential chunks strictly bounded by end - start <= max_chunk_duration (30.0s)"*.
  - Violates invariant `assert (c.end - c.start) <= config.max_chunk_duration + 1e-4` in `tests/test_chunker.py`.
  - For long pauses (e.g., 10 minutes), chunks of 600+ seconds are created, crashing DTW alignment due to audio loader buffer limits (`Config.max_frames = 3000`, 60s) and causing quadratic memory explosion ($O(T \times U)$).
- **Mitigation**:
  1. The partitioner must not assume speech begins at `curr_start`. When `all_words[word_ptr].start > curr_start + max_chunk_duration`, `curr_start` must advance or empty silence intervals must be handled so that either:
     - Chunks skip non-speech silence intervals, starting chunk $k$ at or near `all_words[word_ptr].start - padding`, OR
     - If contiguous tiling of the timeline is required, silence chunks must be valid, or intermediate anchor points across long silences must be established at multiples of `max_chunk_duration` without requiring words inside.
  2. The safety fallback MUST assert or guarantee that `chosen_split - curr_start <= max_chunk_duration`.

---

### [High] Challenge 2: Clamping Invariant Violation (`padded_end > total_duration`)

- **Assumption challenged**: The implementation assumes that `padded_end = round(min(total_dur, chunk_end + cfg.overlap_padding), 4)` guarantees `padded_end <= total_dur`.
- **Attack scenario**:
  - `total_dur` has sub-millisecond precision, e.g. `total_dur = 10.00006` or `486.8074629816908`.
  - At the final chunk, `min(total_dur, ...)` evaluates to `total_dur` (`10.00006`).
  - Next, `round(10.00006, 4)` is evaluated, which rounds UP to `10.0001`.
  - `10.0001 > 10.00006`, so `chunk.padded_end > total_duration` and `chunk.end > total_duration`.
  - In addition, `AudioChunk` allows this because `AudioChunk` only checks `padded_end >= end` and does not take `total_duration` as a parameter. But external invariant checks (`assert chunk.padded_end <= total_duration`) fail.
- **Blast radius**:
  - Violates Requirement R2: *"clamped strictly within [0.0, total_duration]"*.
  - Audio slice extraction for DTW (`audio[int(padded_start * sr) : int(padded_end * sr)]`) reads past EOF or requests audio frames beyond total audio duration.
- **Mitigation**:
  - Enforce `padded_end = min(total_dur, round(chunk_end + cfg.overlap_padding, 4))` and `chunk_end = min(total_dur, round(split_point, 4))` so that rounding cannot push values above `total_dur`. Alternatively, quantize `total_dur` to 4 decimal places at function entry: `total_dur = round(finite_number(total_duration, "total_duration"), 4)`.

---

## Stress Test Results

Executed via automated test harness `tests/stress_test_chunker.py`:

| Test Suite | Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|---|
| `60m_dense_silences` | 60-min lecture with pause every 2s | 120-180 chunks, all $\le 30.0$s | 121 chunks in 0.022s, all bounds satisfied | **PASS** |
| `60m_zero_silences` | 60-min lecture with continuous uninterrupted speech | 120-180 chunks, all $\le 30.0$s | 180 chunks in 0.013s, all bounds satisfied | **PASS** |
| `60m_sparse_silences_long_pauses` | 60-min lecture with 110s pauses between speech | All chunks $\le 30.0$s | 29 chunks have duration `112.0s` ($> 30.0$s) | **FAIL** |
| `leading_silence_gt_30s` | 2-min recording, speech begins at 45.0s | All chunks $\le 30.0$s | Chunk 0 has duration `48.0s` ($> 30.0$s) | **FAIL** |
| `micro_segments` | 1000 micro-segments (60ms) | Chunks $\le 30.0$s, fast execution | 5 chunks in 0.0094s, all bounds satisfied | **PASS** |
| `exact_30s_boundaries` | Segments ending exactly at 30.0s intervals | Chunks partitioned at 30.0s | 10 chunks in 0.0002s, all bounds satisfied | **PASS** |
| `pathological_silences` | Overlapping, adjacent, zero-length, negative, out-of-bounds silences | Handled gracefully without crash | 3 chunks in 0.0001s, all bounds satisfied | **PASS** |
| `randomized_fuzzing_50_trials` | 50 randomized trials with random gaps (0.1s to 50s) | All invariants hold for all chunks | 27/50 trials failed due to duration bound and clamping violations | **FAIL** |

**Summary**: 5/8 suites passed, 3 suites failed with reproducible empirical violations.

---

## Unchallenged Areas

- **GPU VRAM lifecycle**: Handled in Increment 2 (`asr.py`), out of scope for pure CPU chunking logic.
- **DTW alignment cost calculation**: Increment 4 scope; Increment 3 tests models, chunking, and reconciliation.
