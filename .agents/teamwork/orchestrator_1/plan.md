# Execution Plan — Increment 3: Macro-DTW Chunking & Alignment Reconciler

## Overview
Implement Bounded Chunker (<= 30.0s), Contextual Overlap Padding (0.5s), and Global Monotonic Alignment Reconciler for "Local Subtitle Alignment Workbench".

## Phases
1. **Phase 0: Survey & Exploration**
   - Dispatch 3 parallel Explorers (`explorer_1`, `explorer_2`, `explorer_3`) to survey:
     - `models.py`, existing speech models, validation patterns, invariants.
     - `asr.py`, `audio.py`, `text_norm.py`, and how VAD silences are extracted/represented.
     - Existing test suite (314 tests), `TEMPLATE_INCREMENT_REPORT.md`, and SDLC process.
   - Synthesize survey findings into `PROJECT.md` with Feature Inventory, Architecture, and Interface Contracts.

2. **Phase 1: Implementation Track — M1 (Data Models & Contracts)**
   - Add immutable `AudioChunk` and `ChunkConfig` with defensive validation (`finite_number`, range invariants `0.0 <= padded_start <= start < end <= padded_end`).
   - Export in `src/subtitle_workbench/__init__.py`.
   - Unit tests for data models and boundary validations.

3. **Phase 2: Implementation Track — M2 (Chunker & Reconciler Logic)**
   - Exceptions: `ChunkingError`, `MonotonicityError`.
   - `partition_into_chunks(segments, silences, total_duration, config)`:
     - Max chunk duration <= 30.0s.
     - Split priority: VAD silences (>= min_silence_duration) -> ASR segment boundaries -> fallback on word boundaries with lowest acoustic/pause interval.
     - Symmetric overlap padding clamped to `[0.0, total_duration]`.
   - `reconcile_chunk_alignments(chunks, chunk_aligned_words)`:
     - Coordinate transformation: `t_global = chunk.start + t_local`.
     - Deduplication of word tokens in overlap seams.
     - Strict global monotonicity guarantee (`word[i+1].start >= word[i].end` or onset order) or raise `MonotonicityError`.
     - Safeguard against zero-duration words and division-by-zero.
   - Export in `src/subtitle_workbench/__init__.py`.

4. **Phase 3: Testing & Quality Gate (M3)**
   - Tests in `tests/test_chunker.py`:
     - Duration bounds on long recordings (10-60 min).
     - Anchor selection preference (VAD silence vs ASR segment vs fallback).
     - Temporal clamping at 0.0 and total_duration.
     - Overlap seam deduplication.
     - Monotonicity checks and corruption error raising.
   - Run gates: `pytest`, `ruff check`, `ruff format --check`, wheel build.
   - Reviewer, Challenger, and Forensic Auditor verification loop.

5. **Phase 4: SDLC Documentation & Git Commit (M4)**
   - Write `docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md` from `docs/increments/TEMPLATE_INCREMENT_REPORT.md`.
   - Ensure clean wheel package build.
   - Commit with message: `feat(chunker): implement bounded chunk partitioner and monotonic alignment reconciler`.
   - Report completion back to Sentinel.
