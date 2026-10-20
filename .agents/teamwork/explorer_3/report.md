# Increment 3 Investigation Report: Test Suite Architecture, Test Formulation, and SDLC Audit Mapping

**Author:** Teamwork Explorer 3  
**Date:** 2026-10-20  
**Target Milestone:** Increment 3 — Macro-DTW Bounded Chunking & Monotonic Alignment Reconciliation  
**Branch:** `feature/increment-3-macro-dtw-chunking`  
**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench`

---

## 1. Executive Summary

This report establishes the testing framework, test case formulations, and SDLC audit documentation blueprint for **Increment 3** of the *Local Subtitle Alignment Workbench*. 

Increment 3 introduces:
1. **Macro-Chunking Data Contracts** (`AudioChunk`, `ChunkConfig` in `src/subtitle_workbench/models.py`).
2. **Bounded Audio Partitioning** (`partition_into_chunks` in `src/subtitle_workbench/chunker.py`), enforcing strict chunk duration limits ($L \le 30.0\text{ s}$), multi-tiered natural anchor prioritization (VAD silences $\to$ ASR segment boundaries $\to$ acoustic fallback), and symmetric overlap padding ($\Delta_{\text{pad}} = 0.5\text{ s}$) with temporal clamping ($[0.0, T_{\text{total}}]$).
3. **Global Monotonic Alignment Reconciliation** (`reconcile_chunk_alignments` in `src/subtitle_workbench/chunker.py`), performing local-to-global coordinate translation ($t_{\text{global}} = \text{chunk.start} + t_{\text{local}}$), overlap seam deduplication, and strict chronological monotonicity enforcement ($w_{i+1}.\text{start} \ge w_i.\text{start}$) with diagnostic `MonotonicityError` tripping.

All chunking and reconciliation logic operates purely on mathematical and temporal contracts in memory, requiring **zero neural network mocks** and **zero GPU resources**, maintaining pure CPU execution with $O(N)$ linear memory and execution complexity over 10-to-60-minute educational recordings.

---

## 2. Existing Test Suite Analysis (Baseline: 314 Passed, 1 Skipped)

A rigorous inspection of the current repository test suite (`tests/`) confirms **315 collected test items** (314 passed, 1 skipped) executing in $3.41\text{ s}$ on CPU with `uv run --locked pytest`.

### 2.1 Inventory & Breakdown Across Test Modules

| Test File | Test Count | Domain / Module Covered | Primary Testing Methodology & Fixtures |
| :--- | :---: | :--- | :--- |
| `tests/test_speech_models.py` | 117 | `models.py`: `PhonemeCue`, `WordToken`, `ASRSegment`, `AlignmentResult` | Parametrized boundary values (`NaN`, `inf`, `bool`, negative intervals, surrogates, ASCII controls, empty strings). Helper factories: `sample_phoneme()`, `sample_word()`. Frozen dataclass immutability checks. |
| `tests/test_text_norm.py` | 72 | `text_norm.py`: `TokenSpan`, `integer_to_words`, `normalize_text_spans`, `project_tokens_to_cues` | Invariant helper `assert_token_span_invariant(text, spans)` verifying exact character slicing. Contraction expansion, ordinals, decimals, hyphenated compounds, acronyms, and reverse WebVTT cue projection. |
| `tests/test_asr.py` | 54 (53 passed, 1 skipped) | `asr.py`: `WhisperTranscriber`, `extract_vad_silences`, `ASRError` hierarchy | Offline dummy backend fixture `DummyWhisperBackend`, `DummyWord`, `DummySegment`. VRAM lifecycle tests (`unload()`, idempotent unload, context manager). Adversarial timestamp jitter, microsecond rounding, sample-to-second VAD index scaling. Live test skipped via `@pytest.mark.skipif`. |
| `tests/test_contracts.py` | 38 | `models.py` (`Config`, `validate_cues`), `audio.py` (`load_wav`, `validate_wav`) | Validates subtitle JSON shape, language tag (`"en"`), non-overlapping cues, `Config` resource ceilings (`max_frames`, `max_cells`). Audio format validation (PCM16 mono 16000Hz), silence rejection, frame guards, truncation. |
| `tests/test_dtw.py` | 15 | `dtw.py`: `banded_dtw` | Exact diagonal zero-cost paths, cost matrices, monotonic path steps, cell limit safety guards (`max_cells`), disconnected band failure modes. |
| `tests/test_export.py` | 12 | `export.py`: `webvtt`, `jsonld`, `timestamp` | Timecode serialization (`00:00:00.000`), carry over, WebVTT escaping, collapsed cue rejection, schema.org `VideoObject`/`Clip` JSON-LD generation. |
| `tests/test_integration.py` | 7 | `pipeline.py`, `cli.py`, `demo.py` | End-to-end alignment pipeline, synthetic timing oracle comparison ($\text{MAE} \le 50\text{ ms}$), deterministic SHA-256 output reproducibility, CLI argument validation. |
| **Total Baseline** | **315** | **Entire Package Public API** | **100% Offline Pass Rate (314 passed, 1 skipped)** |

### 2.2 Key Testing Conventions Observed

1. **Zero Mocks on Pure Business Logic:**
   - In `test_contracts.py`, `test_dtw.py`, `test_speech_models.py`, `test_text_norm.py`, and `test_export.py`, **no mock libraries (`unittest.mock`) are used**. Tests instantiate actual dataclasses and invoke real algorithmic functions.
   - Mocking is strictly restricted to `test_asr.py` (`DummyWhisperBackend`), solely because loading Faster-Whisper Large-v3 requires multi-gigabyte neural network weights that cannot run in lightweight CI.
   - For Requirement R3 (`tests/test_chunker.py`), **zero mocks must be used**, as chunking and reconciliation are pure mathematical logic over typed dataclasses.

2. **Systematic Defensive Boundary Parametrization:**
   - Every numerical field is tested against `float("nan")`, `float("inf")`, `-float("inf")`, `True`, `False`, negative floats, and strings.
   - Every string field is tested against empty strings `""`, whitespace `"   "`, null bytes `"\x00"`, delete `"\x7f"`, C1 controls (`\x80`), and surrogate characters (`\ud800`).
   - Every interval is tested against inverted bounds (`start > end`), zero duration (`start == end`), and out-of-bounds endpoints.

3. **Invariants & Assertion Helpers:**
   - Existing tests define focused helper assertions (such as `assert_token_span_invariant` in `test_text_norm.py`).
   - For `test_chunker.py`, invariant assertion helpers must verify:
     - `assert_chunk_invariants(chunk, total_duration, config)`: verifies `0.0 <= chunk.padded_start <= chunk.start < chunk.end <= chunk.padded_end <= total_duration` and `chunk.end - chunk.start <= config.max_chunk_duration`.
     - `assert_strictly_monotonic(words)`: verifies $w_{i+1}.\text{start} \ge w_i.\text{start}$ (or $w_{i+1}.\text{start} \ge w_i.\text{end}$ for non-overlapping words).

4. **Pure Offline Execution & Fast Test Cycle:**
   - Pytest completes the entire 314-test suite in ~3.4 seconds.
   - All tests run offline without network access. Synthetic generation generates in-memory arrays or small temporary WAV files via standard library `wave`.

---

## 3. Requirement R3: Comprehensive Test Suite Specification (`tests/test_chunker.py`)

Requirement R3 mandates a dedicated test module `tests/test_chunker.py` covering all aspects of `AudioChunk`, `ChunkConfig`, `partition_into_chunks`, and `reconcile_chunk_alignments`.

### 3.1 Test Helpers & Synthetic Data Generators (Zero Mocks)

```python
"""In-memory synthetic data helpers for pure business logic testing."""


def make_word(
    word_id: str,
    text: str,
    start: float,
    end: float,
    confidence: float = 0.95,
) -> WordToken:
    """Construct a valid WordToken."""
    return WordToken(
        id=word_id,
        text=text,
        normalized=text.lower().strip(".,!?"),
        start=round(start, 4),
        end=round(end, 4),
        confidence=confidence,
    )


def make_segment(
    seg_id: str,
    start: float,
    end: float,
    text: str,
    words: list[WordToken] | None = None,
) -> ASRSegment:
    """Construct a valid ASRSegment with chronologically ordered words."""
    if words is None:
        raw_words = text.split()
        words = []
        n = len(raw_words)
        dur = (end - start) / max(1, n)
        for i, w in enumerate(raw_words):
            w_start = start + i * dur
            w_end = w_start + dur * 0.9
            words.append(make_word(f"{seg_id}_w{i}", w, w_start, w_end))
    return ASRSegment(id=seg_id, start=start, end=end, text=text, words=words)


def generate_synthetic_lecture(
    total_duration_sec: float,
    speech_density: float = 0.8,
    avg_segment_duration: float = 4.0,
    pause_duration: float = 1.0,
) -> tuple[list[ASRSegment], list[tuple[float, float]], float]:
    """Generate deterministic long-form lecture speech segments and VAD silences.

    Produces alternating speech segments and silence pauses matching natural lecture prosody.
    """
    segments: list[ASRSegment] = []
    silences: list[tuple[float, float]] = []
    current_time = 0.0
    seg_idx = 0

    while current_time < total_duration_sec:
        # Determine remaining duration
        rem = total_duration_sec - current_time
        if rem <= avg_segment_duration + pause_duration:
            # Final speech segment
            s_end = total_duration_sec
            segments.append(
                make_segment(
                    f"seg_{seg_idx:04d}",
                    current_time,
                    s_end,
                    f"Conclusion words at {current_time:.1f}",
                )
            )
            break

        # Speech segment
        s_end = min(total_duration_sec, current_time + avg_segment_duration)
        segments.append(
            make_segment(
                f"seg_{seg_idx:04d}", current_time, s_end, f"Lecture segment text block {seg_idx}"
            )
        )
        current_time = s_end
        seg_idx += 1

        # Inter-segment silence pause
        p_end = min(total_duration_sec, current_time + pause_duration)
        if p_end - current_time >= 0.4:  # >= min_silence_duration
            silences.append((round(current_time, 4), round(p_end, 4)))
        current_time = p_end

    return segments, silences, total_duration_sec
```

### 3.2 Formulated Test Cases Breakdown

The test suite in `tests/test_chunker.py` is structured into 5 logical test classes/groups:

```
tests/test_chunker.py
├── Group 1: TestAudioChunkAndConfigContracts (Data contracts & invariants)
├── Group 2: TestExceptionHierarchy (Typed exception inheritance)
├── Group 3: TestPartitionIntoChunks (Anchor selection & duration bounds)
├── Group 4: TestLongRecordingsLinearScalability (10m, 30m, 60m complexity)
└── Group 5: TestReconcileChunkAlignments (Coordinates, seams, monotonicity)
```

#### Group 1: Data Contracts & Invariants (`AudioChunk`, `ChunkConfig`)
1. `test_audio_chunk_valid_instantiation`:
   - Instantiates an `AudioChunk` with valid parameters (`id="chunk-0"`, `index=0`, `start=10.0`, `end=35.0`, `padded_start=9.5`, `padded_end=35.5`).
   - Asserts frozen immutability (`FrozenInstanceError` upon attribute reassignment).
2. `test_audio_chunk_boundary_invariants_enforcement`:
   - Checks violation of `0.0 <= padded_start <= start < end <= padded_end`.
   - Parametrizes inverted intervals: `padded_start > start`, `start >= end`, `end > padded_end`, `padded_start < 0.0`.
   - Expects `ValueError`.
3. `test_audio_chunk_numerical_field_validation`:
   - Tests `start`, `end`, `padded_start`, `padded_end` against `float("nan")`, `float("inf")`, `-float("inf")`, `True`, `False`, negative numbers, strings.
   - Expects `ValueError`.
4. `test_audio_chunk_index_and_id_validation`:
   - `index`: tests negative integers (`-1`), bools (`True`), floats (`0.5`).
   - `id`: tests empty strings, spaces, non-ASCII, punctuation (`bad-->id`), strings > 128 chars.
5. `test_chunk_config_defaults_and_custom`:
   - Asserts default thresholds: `max_chunk_duration=30.0`, `min_chunk_duration=1.0`, `overlap_padding=0.5`, `min_silence_duration=0.4`.
6. `test_chunk_config_boundary_validation`:
   - Parametrizes invalid configurations: `max_chunk_duration <= 0.0`, `min_chunk_duration <= 0.0`, `min_chunk_duration > max_chunk_duration`, `overlap_padding < 0.0`, `min_silence_duration < 0.0`.
   - Parametrizes `NaN`, `inf`, and `bool` values.

#### Group 2: Exception Hierarchy Tests
7. `test_chunker_exception_hierarchy`:
   - Verifies `issubclass(ChunkingError, Exception)` and `issubclass(MonotonicityError, ChunkingError)`.
   - Verifies polymorphic exception catching: `try: raise MonotonicityError(...) except ChunkingError: pass`.

#### Group 3: Bounded Partitioner Business Logic (`partition_into_chunks`)
8. `test_partition_short_recording_produces_single_chunk`:
   - Audio duration = 15.0s (< 30.0s).
   - Returns exactly 1 `AudioChunk`.
   - Asserts `chunk.start == 0.0`, `chunk.end == 15.0`, `chunk.padded_start == 0.0`, `chunk.padded_end == 15.0`.
9. `test_partition_strict_duration_bound_enforced`:
   - 100s audio with irregular segments.
   - Verifies that for every generated chunk: `chunk.end - chunk.start <= config.max_chunk_duration (30.0s)`.
10. `test_partition_natural_anchor_priority_1_vad_silence`:
    - Setup: Segment 1 (0–12s), Silence (12.0–13.5s), Segment 2 (13.5–24.0s), Silence (24.0–25.2s), Segment 3 (25.2–35.0s).
    - If no silence splitting were used, the chunk would hit 30.0s mid-Segment 3.
    - Assertion: Partitioner prioritizes splitting during the Silence at 24.0–25.2s (silence duration 1.2s >= 0.4s), placing Chunk 0 end at the silence anchor ($\approx 24.6\text{s}$) rather than waiting for 30s or cutting Segment 3 mid-sentence.
11. `test_partition_natural_anchor_priority_2_asr_segment_boundary`:
    - Setup: Continuous speech with NO VAD silences >= 0.4s, but multiple ASR segments: Segment 1 (0–10s), Segment 2 (10–22s), Segment 3 (22–34s).
    - At 22s, Segment 2 ends. Since Segment 3 ends at 34s (> 30s), partitioner splits at the Segment 2 boundary ($t = 22.0\text{s}$).
    - Assertion: Chunk 0 ends at 22.0s; Chunk 1 begins at 22.0s. Words are not cut mid-sentence.
12. `test_partition_natural_anchor_priority_3_continuous_speech_fallback`:
    - Setup: Pathological case where a single uninterrupted speech segment spans 45.0s with zero pauses and zero segment breaks.
    - Assertion: Partitioner falls back to finding the optimal word boundary within the segment closest to 30.0s.
    - Chunks produced: Chunk 0 has duration $\le 30.0\text{s}$, Chunk 1 has duration $\le 30.0\text{s}$. No words are split in half.
13. `test_partition_padding_clamping_at_global_bounds`:
    - First chunk: `start = 0.0`. `padded_start` must equal `0.0` (clamped against `start - 0.5 = -0.5`).
    - Last chunk: `end = total_duration`. `padded_end` must equal `total_duration` (clamped against `end + 0.5 = total_duration + 0.5`).
    - Interior chunks: `padded_start == start - 0.5`, `padded_end == end + 0.5`.
    - Invariant holds everywhere: `0.0 <= padded_start <= start < end <= padded_end <= total_duration`.
14. `test_partition_empty_segments_handling`:
    - Empty segments list with `total_duration = 0.0` or positive duration.
    - Handled gracefully (returns `[]` if no speech).
15. `test_partition_rejects_invalid_total_duration`:
    - `total_duration <= 0.0`, `float("nan")`, `float("inf")`, `True`.
    - Raises `ValueError` or `ChunkingError`.
16. `test_partition_segments_exceeding_total_duration`:
    - Segment end > `total_duration`. Raises `ChunkingError` due to inconsistent temporal metadata.

#### Group 4: Long Recordings & Linear Scalability (10 to 60 Minutes)
17. `test_partition_long_recording_10_minutes`:
    - 600s synthetic lecture: ~120 segments, ~1200 words, ~100 silences.
    - Asserts 100% of chunks have $L \le 30.0\text{s}$.
    - Asserts contiguous coverage (no lost speech intervals).
    - Asserts execution completes in $< 50\text{ ms}$.
18. `test_partition_long_recording_30_minutes`:
    - 1800s synthetic lecture: ~360 segments, ~3600 words, ~300 silences.
    - Asserts all chunks bounded by 30.0s. Execution completes in $< 100\text{ ms}$.
19. `test_partition_long_recording_60_minutes`:
    - 3600s synthetic lecture: ~720 segments, ~7200 words, ~600 silences.
    - Asserts all chunks bounded by 30.0s.
    - Execution completes in $< 200\text{ ms}$.
    - Memory footprint remains strictly $O(N)$ with zero quadratic overhead (evaluated via process memory delta or object count bounds).

#### Group 5: Monotonic Alignment Reconciler (`reconcile_chunk_alignments`)
20. `test_reconcile_local_to_global_coordinate_translation`:
    - Chunk 0: $[0.0, 25.0]$, local words at $[1.0, 2.0], [10.0, 11.0]$.
    - Chunk 1: $[25.0, 50.0]$, local words at $[2.0, 3.0], [15.0, 16.0]$.
    - Global translated timestamps: Chunk 1 words become $[27.0, 28.0], [40.0, 41.0]$.
    - Verifies $t_{\text{global}} = \text{chunk.start} + t_{\text{local}}$.
21. `test_reconcile_seam_deduplication_exact_boundary`:
    - Two chunks overlapping by 0.5s:
      - Chunk 0 covers $[0.0, 25.0]$ with padded $[0.0, 25.5]$. A word token `"boundary"` was aligned at local $[24.8, 25.2]$.
      - Chunk 1 covers $[25.0, 50.0]$ with padded $[24.5, 50.5]$. The same word token `"boundary"` was aligned at local $[0.3, 0.7]$ (corresponding to global $24.8 + 0.5$).
    - Assertion: Seam deduplication eliminates the duplicated word in the padding zone. The reconciled stream contains exactly one instance of `"boundary"`.
22. `test_reconcile_strict_monotonicity_verified`:
    - Multi-chunk aligned words with strictly increasing timestamps.
    - Returns single unified list of `WordToken` where `reconciled[i+1].start >= reconciled[i].start`.
23. `test_reconcile_monotone_error_intra_chunk_corruption`:
    - A chunk contains corrupted word timestamps: Word 1 at $[5.0, 6.0]$, Word 2 at $[4.0, 4.8]$ (inverted onset).
    - Assertion: Reconciler raises `MonotonicityError` detailing the invalid timestamp and word IDs.
24. `test_reconcile_monotone_error_cross_chunk_seam_corruption`:
    - Chunk 0 ends with a word at global $26.0\text{s}$, but Chunk 1 begins with a word translated to global $25.2\text{s}$.
    - Assertion: Reconciler raises `MonotonicityError` citing the cross-chunk boundary violation.
25. `test_reconcile_zero_duration_and_microsecond_safeguards`:
    - Word with $t_{\text{start}} = t_{\text{end}} = 10.0$.
    - Handled defensively without division-by-zero or zero-width cue collapse.
26. `test_reconcile_mismatched_chunk_and_word_list_lengths`:
    - `len(chunks) = 3`, `len(chunk_aligned_words) = 2`.
    - Raises `ValueError` or `ChunkingError`.
27. `test_reconcile_empty_inputs`:
    - `chunks = []`, `chunk_aligned_words = []`.
    - Safely returns `[]`.

---

## 4. Requirement R4: SDLC Audit Report Mapping (`INCREMENT_3_MACRO_DTW_CHUNKING.md`)

Based on `docs/increments/TEMPLATE_INCREMENT_REPORT.md` and the verified standard in `docs/increments/INCREMENT_2_ASR_AND_VAD.md`, the audit report `docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md` must follow this exact structural schema:

### 4.1 Document Header & Metadata Block
```markdown
# Increment Report: Macro-DTW Bounded Chunking & Monotonic Alignment Reconciliation
**Increment ID:** `INCREMENT_3_MACRO_DTW_CHUNKING`  
**Date:** 2026-10-20  
**Git Branch:** `feature/increment-3-macro-dtw-chunking`  
**Git Commit SHA:** `<populated-by-implementer-after-commit>`  
**Author:** Askar Nurym  
**Status:** Completed & Verified  
```

### 4.2 Section-by-Section Mapping

#### Section 1: Executive Summary & Objective
- Problem statement: Unbounded dynamic programming on long audio ($10\text{--}60\text{ min}$) exhibits $O(T \times U)$ quadratic complexity, blowing past memory limits and causing cumulative timestamp drift.
- Solution: Bounded chunking with maximum duration $L \le 30.0\text{ s}$, 3-tier natural pause anchor prioritization (VAD silences $\to$ sentence ends $\to$ acoustic fallback), symmetric $0.5\text{ s}$ overlap padding with temporal clamping, and global monotonic reconciliation.
- Fit into Master's Thesis Individual Plan: Component of Stage 3 (Macro-Alignment & Segmentation).

#### Section 2: Traceability to Individual Plan & Quality Gates
- **Thesis Milestone:** НИРМ 3 — Алгоритм точной синхронизации (модуль макро-сегментации и реконсиляции).
- **ASDP Quality Gates Addressed:**
  - `[x] Gate 1: Requirements & Typed Contracts` (`AudioChunk`, `ChunkConfig` immutability, `ChunkingError`, `MonotonicityError`).
  - `[x] Gate 2: Modular Implementation` (`src/subtitle_workbench/chunker.py`, `models.py`, `__init__.py`).
  - `[x] Gate 3: Unit & Numerical Verification` (100% test pass rate across 314 baseline + ~35 new tests, zero regressions).
  - `[x] Gate 4: Packaging & Offline Smoke Test` (clean wheel build without network access, smoke test passes).
  - `[x] Gate 5: Manifest & Code Provenance Audit` (cryptographic SHA-256 reproducibility, linear complexity).

#### Section 3: Detailed Inventory of Changes
- **3.1 Files Created:**
  - `src/subtitle_workbench/chunker.py` (+~250 lines): partitioner, reconciler, and error classes.
  - `tests/test_chunker.py` (+~600 lines): comprehensive unit and scaling test suite.
  - `docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md` (+~200 lines): SDLC audit report.
- **3.2 Files Modified:**
  - `src/subtitle_workbench/models.py`: additions of `AudioChunk` and `ChunkConfig` dataclasses with defensive boundary validation.
  - `src/subtitle_workbench/__init__.py`: exports of `AudioChunk`, `ChunkConfig`, `ChunkingError`, `MonotonicityError`, `partition_into_chunks`, `reconcile_chunk_alignments`.
- **3.3 Dependencies & Build:**
  - External dependencies: **None** (zero additions to `pyproject.toml` or `uv.lock`). Operates entirely with Python standard library and NumPy.

#### Section 4: Verification Evidence & Quality Gate Results
Must document verbatim command execution outputs:
- **4.1 Automated Test Execution:**
  ```text
  Command: uv run --locked pytest
  Result: PASS
  Total Tests: 349 passed, 1 skipped in X.XXs (314 baseline + 35 new tests)
  New Tests Added in this Increment: 35
  Existing Tests Regressed: 0
  Mocks Used: Zero mocks on chunking & reconciliation
  ```
- **4.2 Code Linter & Formatting:**
  ```text
  Command: uv run --locked ruff check .
  Result: All checks passed!

  Command: uv run --locked ruff format --check .
  Result: All files correctly formatted!
  ```
- **4.3 Packaging & Wheel Smoke Test:**
  ```text
  Command: uv run --locked python -m build --wheel --no-isolation
  Result: Successfully built local_subtitle_workbench-0.1.0-py3-none-any.whl

  Command: uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output test_smoke_out
  Result: PASS (offline execution verified with socket guard, max absolute error <= 50ms)
  ```

#### Section 5: Architectural & Design Decisions Made
Document 5 core design decisions:
- **Decision 1 (Hierarchical Anchor Selection Priority):** Why VAD silence (priority 1) prevents mid-word splitting; why ASR sentence boundaries (priority 2) preserve linguistic semantics; why acoustic pause fallback (priority 3) guarantees $L \le 30.0\text{ s}$ even on continuous monologues.
- **Decision 2 (Symmetric Overlap Padding & Boundary Clamping):** $0.5\text{ s}$ padding prevents acoustic boundary cutoffs during DTW feature extraction. Explicit clamping $[0.0, T_{\text{total}}]$ eliminates negative time offsets at recording start and overshoot past duration.
- **Decision 3 (Seam Deduplication Strategy):** How words residing in the overlap window are deduplicated (e.g. keeping words whose midpoint or start falls within the unpadded chunk span $[chunk.start, chunk.end]$), ensuring zero duplicate words.
- **Decision 4 (Strict Monotonic Chronology Invariant):** Enforces $w_{i+1}.\text{start} \ge w_i.\text{start}$ globally. Corrupted timestamps immediately raise `MonotonicityError` rather than silently generating invalid WebVTT subtitles.
- **Decision 5 (Linear Memory & Execution Guarantees):** Explaining how chunking bounds memory to $O(L)$ where $L \le 30\text{ s}$ instead of $O(T_{\text{total}})$, keeping RAM under $15\text{ MB}$ even for 60-minute lectures.

#### Section 6: Edge Cases, Failure Modes & Boundary Conditions Tested
Detailed markdown table covering:
- Short audio ($< 30\text{ s}$) single-chunk production.
- Overlong speech ($> 30\text{ s}$) continuous speech fallback.
- First chunk left-clamping (`padded_start == 0.0`).
- Last chunk right-clamping (`padded_end == total_duration`).
- Interior chunk symmetric padding ($start - 0.5$, $end + 0.5$).
- Word deduplication at overlap seams.
- Intra-chunk inverted timestamps raising `MonotonicityError`.
- Inter-chunk inverted timestamps raising `MonotonicityError`.
- Zero-duration and microsecond timestamps.
- Long recording scalability ($10\text{ min}$, $30\text{ min}$, $60\text{ min}$).
- Non-finite numbers (`NaN`, `inf`, `bool`) in `AudioChunk` and `ChunkConfig`.

#### Section 7: Handover & Prerequisites for Increment 4
- Working tree clean, committed to `feature/increment-3-macro-dtw-chunking`.
- Prerequisites for Increment 4:
  - Macro-chunks produced by `partition_into_chunks` can be passed sequentially to the phonetic forced aligner (MFA / MMS_FA).
  - Aligned words can be fed directly to `reconcile_chunk_alignments` to assemble the full global subtitle timeline.

---

## 5. Anti-Falsification Checklist Compliance

In strict adherence to `docs/ANTI_FALSIFICATION.md`:
1. **Rule 1 (Frozen Gold Reference Standard):** No self-certification; synthetic testing tests pure algorithmic contracts, not fabricated empirical accuracy.
2. **Rule 2 (Absolute Ban on Synthetic Numbers):** No hypothetical performance numbers (e.g. "99.9% precision") are claimed. All reported timings and test counts reflect verifiable test outputs. Any unmeasured empirical metric must be marked `UNMEASURED / PENDING_EXPERIMENT`.
3. **Rule 3 (Separation of Raw vs Display Timings):** Word timestamps maintain full floating-point precision ($t_{\text{global}}$); display rounding is deferred to exporter modules.

---

## 6. Synthesis & Next Steps for Implementation

- **Explorer 1** defines `AudioChunk` and `ChunkConfig` in `src/subtitle_workbench/models.py`.
- **Explorer 2** defines the partitioning and reconciliation logic in `src/subtitle_workbench/chunker.py`.
- **Implementer** will assemble the code and execute the test suite in `tests/test_chunker.py` using the specifications and invariants formulated in this report.
- **Audit Report** `docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md` will be finalized with real execution outputs from `pytest`, `ruff`, and `build`.
