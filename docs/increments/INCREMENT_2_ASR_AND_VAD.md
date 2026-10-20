# Increment Report: ASR & Silero-VAD with GPU VRAM Lifecycle Management
**Increment ID:** `INCREMENT_2_ASR_AND_VAD`  
**Date:** 2026-10-20  
**Git Branch:** `feature/increment-2-asr-and-vad`  
**Git Commit SHA:** `e8f8f10753d95d901734277dbb28b942d2f5f605`  
**Author:** Askar Nurym  
**Status:** Completed & Verified  

---

## 1. Executive Summary & Objective
Increment 2 implements the automated speech recognition (ASR) and voice activity detection (VAD) layer of the Local Subtitle Alignment Workbench. The core requirement is integrating Faster-Whisper Large-v3 INT8 (via CTranslate2) and Silero-VAD pause detection while enforcing deterministic GPU memory lifecycle management under strict hardware constraints (NVIDIA GeForce RTX 3050 Laptop GPU, 4 GB VRAM ceiling, target allocation <= 1.85 GB VRAM).

The module maintains strict offline isolation: heavy neural dependencies (`torch`, `faster-whisper`) are specified as optional dependencies under `[project.optional-dependencies] speech`, with imports isolated and lazily resolved inside runtime methods. This guarantees that the base distribution and test suite execute completely offline on CPU without requiring GPU hardware or multi-gigabyte weight downloads.

---

## 2. Traceability to Individual Plan & Quality Gates
- **Thesis Milestone:** НИРМ 3 — Алгоритм точной синхронизации (модуль ASR и VAD сегментации).
- **ASDP Quality Gates Addressed:**
  - [x] Gate 1: Requirements & Typed Contracts (`ASRSegment`, `WordToken` typed mapping, `ASRError` hierarchy).
  - [x] Gate 2: Modular Implementation (`src/subtitle_workbench/asr.py`, `audio.py`, `src/subtitle_workbench/__init__.py`).
  - [x] Gate 3: Unit & Numerical Verification (314 passed, 1 skipped offline, 54 tests in `test_asr.py`, 0 regressions).
  - [x] Gate 4: Packaging & Offline Smoke Test (wheel builds without isolation, smoke test executes offline with network guard).
  - [x] Gate 5: Manifest & Code Provenance Audit (deterministic memory flush, clean separation of concerns).

---

## 3. Detailed Inventory of Changes

### 3.1 Files Created
| File Path | Lines of Code | Responsibility / Architectural Role |
| :--- | :---: | :--- |
| `src/subtitle_workbench/asr.py` | +490 | `WhisperTranscriber`, `extract_vad_silences`, exception hierarchy (`ASRError`, `AudioFormatError`, `ASRInferenceError`, `VRAMAllocationError`), device/quantization auto-selection, deterministic GPU memory management, sanitization, word chronological ordering, compound preservation, timing repair, and fallback word synthesis. |
| `tests/test_asr.py` | +1120 | 54 tests: contract verification, VRAM unload & cache flushes, audio format errors, Silero-VAD pause extraction, dummy offline backend, adversarial robustness, timing repairs, and skip-protected live integration. |
| `docs/increments/INCREMENT_2_ASR_AND_VAD.md` | +210 | SDLC increment documentation and verification evidence trail. |

### 3.2 Files Modified
| File Path | Diff Summary | Rationale for Modification |
| :--- | :--- | :--- |
| `pyproject.toml` | +6 lines | Added `[project.optional-dependencies] speech = ["faster-whisper>=1.0.0", "torch>=2.2.0"]`. |
| `uv.lock` | Updated lockfile | Resolved dependencies for `speech` optional group. |
| `src/subtitle_workbench/audio.py` | +32 lines | Added `validate_wav` helper ensuring uncompressed mono PCM16 16000 Hz input before memory allocation, hardened with chunked streaming verification, `struct.error` and `RuntimeError` trapping. |
| `src/subtitle_workbench/__init__.py` | +12 lines | Exported `WhisperTranscriber`, `extract_vad_silences`, and error classes in public API. |

### 3.3 Dependencies & Build
- Added optional dependency group: `speech` (`faster-whisper>=1.0.0`, `torch>=2.2.0`).
- Base runtime package remains lightweight (NumPy only), perfectly preserving offline CPU compatibility.

---

## 4. Verification Evidence & Quality Gate Results

### 4.1 Automated Test Execution
```
Command: uv run --locked pytest
Result: PASS
Total Tests: 314 passed, 1 skipped in 4.10s (261 existing + 53 active new tests)
New Tests Added in this Increment: 54 (53 active, 1 skipped)
Existing Tests Regressed: 0
Mocks Used: Isolated fixture DummyWhisperBackend
Skipped: 1 (optional live integration test when faster-whisper is not installed)
```

### 4.2 Code Linter & Formatting
```
Command: uv run --locked ruff check .
Result: All checks passed!

Command: uv run --locked ruff format --check .
Result: 83 files already formatted!
```

### 4.3 Packaging & Wheel Smoke Test
```
Command: uv run --locked python -m build --wheel --no-isolation
Result: Successfully built local_subtitle_workbench-0.1.0-py3-none-any.whl

Command: uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output test_smoke_out
Result: PASS (offline execution verified with socket guard, max absolute error: 18.4ms)
```

---

## 5. Architectural & Design Decisions Made
- **Decision 1 (Deterministic VRAM Unload Lifecycle):** Faster-Whisper Large-v3 INT8 requires ~1.85 GB VRAM on GPU. To strictly prevent memory fragmentation and OOM on the 4 GB RTX 3050 Laptop GPU, `WhisperTranscriber.unload()` explicitly deletes model references, executes `gc.collect()`, and calls `torch.cuda.empty_cache()` when CUDA is active. Context manager support (`__enter__` / `__exit__`) is implemented for safe deterministic scoping.
- **Decision 2 (Lazy / Optional Speech Imports):** Neither `torch` nor `faster-whisper` are imported at module level in `asr.py`. Heavy imports occur strictly inside runtime methods (`_resolve_device_and_compute_type`, `_get_or_load_model`, `extract_vad_silences`), ensuring that CPU-only environments and CI can import `subtitle_workbench` without installing multi-gigabyte ML runtimes.
- **Decision 3 (Silero-VAD Pause Extraction for Macro-DTW):** `extract_vad_silences` extracts silence intervals (pauses >= 400 ms) complementary to detected speech intervals. It handles leading pauses (`[0, start]`), inter-segment pauses, and trailing pauses (`[end, duration]`), providing silence anchors for Macro-DTW in Increment 3.
- **Decision 4 (Bijective Normalization Linkage):** Whisper's emitted words are mapped directly to `WordToken` dataclasses, linking display text to normalized phonetic tokens via `normalize_text_spans` from `text_norm.py`. Contractions like `"don't"` are automatically expanded to normalized `"do not"` while preserving timing and original tokens.
- **Decision 5 (Adversarial Robustness & Timestamp Stability):**
  - Post-rounding monotonicity enforcement: guarantees `round(end, 4) > round(start, 4)` even when Whisper yields microsecond intervals, preventing `ValueError` contract collapse.
  - Sub-threshold duration suppression: files shorter than `min_silence_duration_ms` with no speech return empty silence lists rather than invalid short silence windows.
  - Sanitization of external model outputs: strips ASCII controls, C1 controls, and surrogates before tokenization to ensure typed validation contracts never fail unexpectedly.
  - Missing word timestamp fallback: when Whisper transcribes segment text but omits word-level timestamps, WordTokens are synthesized evenly across the segment span.
  - Resilient CUDA exception handling: catches driver mismatches during device resolution and GPU cache cleanup.
- **Decision 6 (VAD Scale Normalization, Compound Preservation & Robust Format Wrapping - Round 2):**
  - Native Faster-Whisper Silero-VAD always outputs sample indices, unconditionally converted to seconds (`s / sample_rate`).
  - For external VAD backends, seconds are robustly distinguished from sample indices using `max(s, e) > max(duration + 2.0, duration * 1.2)`, preventing minor frame boundary overshoots (e.g. 5.01s on 5.0s audio) from false division by 16000.
  - Corrupted WAV chunks raising `RuntimeError` or `struct.error` in `wave.py` are mapped to `ValueError` in `validate_wav` and `AudioFormatError` in public APIs.
  - Hyphenated compound words (e.g. `"twenty-five"`) retain their full token text via boundary stripping instead of single span truncation.
  - `WordToken` items within `ASRSegment` are sorted chronologically, and segment bounds strictly encompass all constituent word bounds.
  - Input parameters (`language`, `min_silence_duration_ms`) are strictly validated against non-empty strings and positive integers.
- **Decision 7 (Inverted Timing Repair, Kwargs Forwarding, Streaming Wave Validation & Strict Path Typing - Round 3):**
  - Buggy third-party VAD backends returning inverted intervals (`end < start`) are normalized via `min(s, e), max(s, e)` rather than dropped, preserving genuine speech intervals.
  - VAD timestamp inputs are validated for finiteness (`not (isnan or isinf)`), raising `ASRInferenceError` on non-finite values.
  - `WhisperTranscriber.transcribe` accepts `**kwargs: Any` and forwards optional inference parameters (e.g., `temperature`, `beam_size`, `initial_prompt`) to backend transcribe while strictly maintaining `word_timestamps=True`.
  - Inverted segment bounds (`seg_start > seg_end`) and inverted word timings are repaired to strictly guarantee `0.0 <= seg.start <= word.start < word.end <= seg.end` even when synthesized from raw text spans.
  - Non-string, non-Path inputs to `transcribe` and `extract_vad_silences` are trapped early and raise `AudioFormatError` rather than leaking raw `TypeError`.
  - `validate_wav` reads frames in 64 KB streaming chunks, preventing multi-hundred megabyte allocations for multi-hour audio files while maintaining strict EOF and format validation (addressing Open Issue #2).

---

## 6. Edge Cases, Failure Modes & Boundary Conditions Tested
| Scenario / Edge Case | Input Description | Expected Behavior | Actual Behavior & Test ID |
| :--- | :--- | :--- | :--- |
| Non-existent audio file | Non-existent path | Raise `AudioFormatError` | PASS (`test_transcribe_nonexistent_file`) |
| Corrupt WAV header | Arbitrary non-WAV bytes | Raise `AudioFormatError` | PASS (`test_transcribe_invalid_wav_content`) |
| Corrupt chunk structure | Chunk seek pos out of bounds | Raise `AudioFormatError` | PASS (`test_corrupted_wav_chunk_structure_raises_audio_format_error`) |
| Unsupported sample rate | 8000 Hz, 44100 Hz WAV | Raise `AudioFormatError` | PASS (`test_transcribe_unsupported_audio_format`) |
| Multi-channel audio | Stereo WAV (2 channels) | Raise `AudioFormatError` | PASS (`test_transcribe_unsupported_audio_format`) |
| Truncated WAV payload | Incomplete sample buffer | Raise `AudioFormatError` | PASS (`test_transcribe_truncated_wav`) |
| CUDA Out-of-Memory | OOM during transcription | Raise `VRAMAllocationError` | PASS (`test_transcribe_vram_allocation_error`) |
| Allocation failure string | "Failed to allocate bytes" | Raise `VRAMAllocationError` | PASS (`test_transcribe_vram_allocation_error_on_alloc_failure`) |
| Runtime model failure | Backend crash / exception | Raise `ASRInferenceError` | PASS (`test_transcribe_general_inference_error`) |
| VAD backend crash | Exception in `vad_backend` | Raise `ASRInferenceError` | PASS (`test_extract_vad_silences_backend_runtime_error_wrapped`) |
| Malformed VAD chunk | Non-numeric start/end in chunk | Raise `ASRInferenceError` | PASS (`test_extract_vad_silences_malformed_chunk_payload_wrapped`) |
| Degenerate word timing | `start == end` timestamp | Fixed to strictly `start < end` | PASS (`test_transcribe_word_timestamp_monotonicity`) |
| Microsecond timestamp rounding | `start=1.00001, end=1.00004` | Post-round `start < end` maintained | PASS (`test_transcribe_microsecond_timestamps_rounding_collapse`) |
| Contraction expansion | Word `"don't"` | Normalized to `"do not"` | PASS (`test_transcribe_contract_and_normalization`) |
| Compound word preservation | Hyphenated `"twenty-five"` | Text preserved without truncation | PASS (`test_transcribe_hyphenated_compound_words_preserved`) |
| Word jitter / out of order | Word 2 starts before Word 1 | Words sorted, bounds encompass | PASS (`test_transcribe_words_sorted_and_segment_bounds_encompassing`) |
| Sub-threshold pause | Pause duration < 400 ms | Filtered out from silence list | PASS (`test_extract_vad_silences_short_pause_filtering`) |
| Sub-threshold file duration | 200 ms silent file | Returns empty list `[]` | PASS (`test_extract_vad_silences_sub_threshold_duration`) |
| Complete silence audio | Zero speech detected (4s) | Returns `[(0.0, duration)]` | PASS (`test_extract_vad_silences_all_silent`) |
| Timestamp overshoot in VAD | Speech end 5.01s on 5.0s audio | Treated as seconds, not samples | PASS (`test_extract_vad_silences_timestamp_overshoot_not_treated_as_samples`) |
| Long clip (> 100s) | Timestamps in seconds > 100 | Correctly kept as seconds | PASS (`test_extract_vad_silences_seconds_over_100_seconds`) |
| Sub-100 sample index | Sample index = 50 (< 100) | Correctly scaled to seconds | PASS (`test_extract_vad_silences_sample_index_under_100`) |
| Empty / whitespace language | `language=""` or `"   "` | Raise `ASRInferenceError` | PASS (`test_transcribe_rejects_empty_or_whitespace_language`) |
| Invalid silence duration | `min_silence_duration_ms <= 0` | Raise `ASRInferenceError` | PASS (`test_rejects_non_positive_silence_duration`) |
| Inverted VAD chunks | Backend returns `(2.0, 1.0)` | Normalized to `[1.0, 2.0]` | PASS (`test_extract_vad_silences_handles_inverted_chunks`) |
| Zero / negative VAD chunks | Length 0 and negative chunks | Discarded or clamped to `0.0` | PASS (`test_extract_vad_silences_handles_zero_length_and_negative_chunks`) |
| Non-finite VAD timestamps | NaN or Inf in chunk timestamps | Raise `ASRInferenceError` | PASS (`test_extract_vad_silences_rejects_nan_and_inf_timestamps`) |
| Kwargs forwarding in ASR | `temperature=0.2, beam_size=3` | Forwarded to backend transcribe | PASS (`test_transcribe_forwards_optional_kwargs`) |
| Inverted segment & word timings | `seg_start > seg_end`, `w_s > w_e` | Monotonic ordering repaired | PASS (`test_transcribe_handles_inverted_segment_and_word_timings`) |
| Inverted segment without words | Inverted `seg_start > seg_end` | Synthesized words across span | PASS (`test_transcribe_handles_inverted_segment_with_synthesized_words`) |
| Non-Path/str audio path types | `None`, integer, list | Raise `AudioFormatError` | PASS (`test_transcribe_and_silences_reject_invalid_audio_path_types`) |
| Streaming WAV validation | Large file chunked read & typing | 64 KB streaming & TypeError | PASS (`test_validate_wav_streaming_memory_and_invalid_types`) |
| Control characters in ASR | Raw text with `\x00` | Sanitized, no `ValueError` | PASS (`test_transcribe_sanitizes_control_characters`) |
| Missing word timestamps | `words=[]` from Whisper | Synthesized from segment text | PASS (`test_transcribe_synthesizes_words_when_raw_words_omitted`) |
| CUDA driver mismatch | `torch.cuda` raises exception | Falls back to CPU | PASS (`test_device_resolution_handles_cuda_driver_exception`) |
| String vs Path input | Path passed as `str` | Accepted and converted | PASS (`test_transcribe_and_silences_accept_str_path`) |
| Idempotent unload | Repeated `unload()` calls | Safe, no error | PASS (`test_vram_lifecycle_idempotent_unload`) |

---

## 7. Handover & Prerequisites for Increment 3
- **Status of Working Tree:** Clean, verified, committed to `feature/increment-2-asr-and-vad`.
- **Prerequisites for Increment 3:**
  - Macro-DTW segmenter (`dtw.py`) can consume `ASRSegment` outputs from `WhisperTranscriber`.
  - Pause boundaries from `extract_vad_silences` can be used as drift-free anchor points for lecture audio partitioning.
