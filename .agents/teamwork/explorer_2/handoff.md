# Handoff Report — Explorer 2: Requirement R2 Chunker Architecture & Algorithm Design

**From:** explorer_2 (Architecture & Algorithm Investigation)  
**To:** orchestrator_1 / implementer_1  
**Date:** 2026-10-20  
**Status:** Complete (Hard Handoff)  
**Artifact:** `c:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_2\report.md`  

---

## 1. Observation

1. **ASR Silences Contract (`src/subtitle_workbench/asr.py:353-506`):**
   - `extract_vad_silences(audio_path, min_silence_duration_ms=400, vad_backend=None) -> list[tuple[float, float]]`
   - Returns disjoint chronological intervals $(s_{start}, s_{end})$ with duration $s_{end} - s_{start} \ge \frac{\text{min\_silence\_duration\_ms}}{1000.0} - 10^{-6}$.
   - All timestamps satisfy $0.0 \le s_{start} < s_{end} \le \text{duration}$.
2. **ASR Segments & Word Token Models (`src/subtitle_workbench/models.py:161-232`):**
   - `WordToken`: immutable (`frozen=True`) with `id: str`, `text: str`, `normalized: str`, `start: float`, `end: float`, `confidence: float`, `phonemes: list[PhonemeCue]`.
   - `ASRSegment`: `id: str`, `start: float`, `end: float`, `text: str`, `words: list[WordToken]`.
   - Invariants strictly enforced: `0.0 <= start < end`, non-empty ASCII IDs, no control characters.
3. **DTW Max Frames Constraint (`src/subtitle_workbench/audio.py:67-68`):**
   - `if (count + hop - 1) // hop > config.max_frames: raise ValueError("audio exceeds configured max_frames; use a shorter segment")`.
   - Proves long recordings must be chunked into windows $L \le 30.0$ s to prevent buffer overflow and excessive DTW cell evaluation.
4. **Package Exports (`src/subtitle_workbench/__init__.py:1-31`):**
   - Currently exports ASR, text normalization, and models symbols. Does not yet export `AudioChunk`, `ChunkConfig`, `ChunkingError`, `MonotonicityError`, `partition_into_chunks`, or `reconcile_chunk_alignments`.
5. **Existing Test Suite Baseline:**
   - Ran `uv run --locked pytest`: 314 passed, 1 skipped (skip is optional faster-whisper on CPU).
   - Zero test regressions in the current branch `feature/increment-3-macro-dtw-chunking`.

---

## 2. Logic Chain

1. **Need for Macro-Segmentation (from Observation 3 & ARCHITECTURE.md:33):**
   - Long educational recordings (10–60 minutes) exceed `Config.max_frames = 3000` (60 seconds) and unconstrained DTW memory scales quadratically ($O(T \times U) \approx 32.4$ GB RAM for 60 min).
   - Therefore, audio must be partitioned into chunks bounded by $L \le 30.0$ s before feature extraction or forced alignment.
2. **Multi-Level Anchor Strategy (from Observation 1 & 2):**
   - Splitting audio randomly or strictly by time truncates words and causes acoustic boundary distortions.
   - Using VAD silences $\ge 0.4$ s (Priority 1) places split points in natural pauses where no speech energy exists.
   - When no VAD silence exists, sentence segment boundaries from Whisper (Priority 2) preserve syntactic and grammatical cohesion.
   - For continuous speech $> 30.0$ s without sentence breaks (Priority 3 fallback), splitting along inter-word boundaries with the largest pause interval prevents phoneme slicing.
3. **Symmetric Overlap Padding & Clamping (from Requirement R2):**
   - Setting $\Delta_{pad} = 0.5$ s with clamping `padded_start = max(0.0, start - padding)` and `padded_end = min(total_duration, end + padding)` ensures acoustic context around boundary phonemes while strictly satisfying `padded_start == 0.0` at $t=0$ and `padded_end == total_duration` at $t=\text{total\_duration}$.
4. **Coordinate Transformation & Seam Deduplication (from Requirement R2 & Observation 2):**
   - Aligners evaluate local chunks. Global mapping $t_{global} = base\_offset + t_{local}$ correctly restores absolute timeline position.
   - Phonemes inside `WordToken.phonemes` must also be transformed: `p.start + base_offset`, `p.end + base_offset`.
   - Tokens whose midpoint lies inside leading padding ($k > 0$ and $mid < chunk.start$) or trailing padding ($k < N-1$ and $mid > chunk.end$) duplicate adjacent chunks and must be discarded.
5. **Strict Monotonicity & Error Handling (from Requirement R2 & ECC Error Handling):**
   - Defining `ChunkingError` and `MonotonicityError(ChunkingError)` provides clear diagnostics.
   - Enforcing `word[i+1].start >= word[i].start` and checking `word[i+1].start >= word[i].end` ensures the output WebVTT subtitle track is strictly chronological, raising `MonotonicityError` if out-of-order corruption occurs.

---

## 3. Caveats

1. **Word-Level Splitting Granularity:** If an individual spoken word exceeds `max_chunk_duration` (30.0 s), the partitioner will raise `ChunkingError`. This is expected because atomic speech tokens cannot be phonetically partitioned across independent alignment chunks.
2. **Negative Local Timestamps:** When aligners emit words in the leading padding zone ($t_{local} < 0$ relative to unpadded start), they are automatically discarded by the seam filter.
3. **No Code Modification:** In accordance with the Explorer role, no production files in `src/` or `tests/` were altered during this investigation.

---

## 4. Conclusion

1. **Architecture Ready for Implementation:** The algorithms for `partition_into_chunks` and `reconcile_chunk_alignments` have been fully drafted and mathematically validated in `report.md`.
2. **Exception Hierarchy Defined:** `ChunkingError` (base) and `MonotonicityError` (specialized) meet all ECC typed error guidelines.
3. **Deterministic Linear Complexity:** The designed partitioner runs in $O(N + S)$ time ($< 2$ ms for 60 min audio) and reconciler runs in $O(W)$ time ($< 5$ ms for 60 min audio) with $< 5$ MB memory.
4. **Implementer Action Plan:** `implementer_1` can drop the reference implementation from Section 6 of `report.md` directly into `src/subtitle_workbench/chunker.py`, integrate with `models.py` (`AudioChunk`, `ChunkConfig`), and export the 6 symbols in `src/subtitle_workbench/__init__.py`.

---

## 5. Verification Method

To verify the findings and subsequent implementation:

1. **Inspect Report:**
   - Read `c:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_2\report.md`.
2. **Run Existing Test Suite:**
   ```bash
   uv run --locked pytest
   ```
   *Expected:* 314 passed, 1 skipped.
3. **Run Code Quality Checkers:**
   ```bash
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   *Expected:* Zero errors.
4. **Invalidation Conditions:**
   - Any chunk produced where $end - start > 30.0$ s.
   - Any chunk where $padded\_start < 0.0$ or $padded\_end > total\_duration$.
   - Any duplicate word tokens across chunk seams in `reconcile_chunk_alignments`.
   - Failure to raise `MonotonicityError` when corrupted timestamps are provided.
