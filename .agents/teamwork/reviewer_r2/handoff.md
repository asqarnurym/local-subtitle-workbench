# Reviewer Round 2 Handoff Report: Increment 2 (ASR & VAD)

**Reviewer:** `teamwork_preview_reviewer` (Round 2)  
**Git Branch:** `feature/increment-2-asr-and-vad`  
**Git Commit SHA:** `c95bb8bd3ae6ec46e968a3560662d5f00e95ff91`  
**Repository:** `c:\Users\nurym\Desktop\local-subtitle-workbench`  
**Target:** Increment 2 (Faster-Whisper Large-v3 INT8 & Silero-VAD with GPU VRAM Lifecycle)  

---

## 1. What the Prior Attempt Got Wrong (Input → Expected → Actual → Root Cause)

### Issue 1: Timestamp Overshoot Triggers False Sample-Index Mode in `extract_vad_silences`
- **Input:** 5.0s audio clip with speech chunk in seconds slightly exceeding file duration due to frame hop/rounding (e.g. `(0.5, 5.01)`).
- **Expected:** Recognized as timestamps in seconds (clamped to `[0.5, 5.0]`); silence interval returned: `[(0.0, 0.5)]`.
- **Actual:** `5.01 > 5.0 + 1e-3` evaluated to True, switching `is_sample_indices` to True. Scaled by 16000, turning `(0.5, 5.01)` into `(0.00003, 0.0003)`. Returned silence `[(0.0003, 5.0)]`, marking 99.99% of the file as silence.
- **Root Cause:** Overly fragile threshold `any(max(s, e) > duration + 1e-3)` with only 1 ms tolerance. A single audio frame at 16 kHz is 10–32 ms. Furthermore, Faster-Whisper Silero-VAD native output is always in sample indices, yet it used the heuristic.

### Issue 2: Corrupted WAV Chunk Structure Leaks Raw `RuntimeError`
- **Input:** WAV file with corrupted internal chunk headers/sizes (e.g. subchunk size exceeding parent chunk size).
- **Expected:** `validate_wav` raises `ValueError`, and `WhisperTranscriber.transcribe` / `extract_vad_silences` raises `AudioFormatError`.
- **Actual:** Python's `wave.open` / `chunk.skip()` raised raw `RuntimeError`, which bypassed the `(wave.Error, EOFError)` catch in `validate_wav` and `asr.py`, leaking uncaught `RuntimeError` to caller.
- **Root Cause:** `validate_wav` in `audio.py` only caught `(wave.Error, EOFError)`, missing `RuntimeError` and `struct.error`. Furthermore, `asr.py` did not include `RuntimeError` in its audio format validation catch block.

### Issue 3: Unhandled Exceptions in `extract_vad_silences` Leak Raw `RuntimeError`, `ValueError`, `TypeError`
- **Input:** Custom `vad_backend` raises `RuntimeError("VAD failed")`, or returns malformed chunk data with non-numeric fields.
- **Expected:** Wrapped in `ASRInferenceError` per ECC Error Handling hierarchy.
- **Actual:** Raw `RuntimeError`, `ValueError`, or `TypeError` leaked directly out of `extract_vad_silences`.
- **Root Cause:** Invocation of `vad_backend` and parsing of `speech_chunks` was not wrapped in exception handling to enforce the `ASRError` hierarchy. Also, reading frames was not wrapped.

### Issue 4: Hyphenated Compound Words Truncated in `WhisperTranscriber.transcribe`
- **Input:** Whisper emits compound/hyphenated word like `"twenty-five"` or `"state-of-the-art"`.
- **Expected:** `WordToken(text="twenty-five", normalized="twenty five", ...)`.
- **Actual:** `token_text = spans[0].token` set `token_text` to `"twenty"`, discarding the rest of the word.
- **Root Cause:** Line 194 unconditionally took `spans[0].token` instead of stripping boundary punctuation from the full token.

### Issue 5: Unsorted Words and Fragile Segment Timing Bounds
- **Input:** Whisper backend emits words with jitter or out of order.
- **Expected:** Emitted `ASRSegment.words` is ordered chronologically, and segment `start`/`end` encompasses all words (`r_seg_start <= all w.start` and `all w.end <= r_seg_end`).
- **Actual:** Segment bounds assumed `words_list[0].start` was the minimum and `words_list[-1].end` was the maximum without verifying word sorting or computing `min`/`max` over all words.
- **Root Cause:** Lack of sorting on `words_list` and using indexed access `words_list[0]` and `words_list[-1]`.

### Issue 6: Invalid / Malformed Parameter Rejection
- **Input:** `transcribe(p, language="")`, `transcribe(p, language="   ")`, or `min_silence_duration_ms <= 0`.
- **Expected:** Early rejection raising `ASRInferenceError`.
- **Actual:** Empty/whitespace language passed downstream to backend causing model crash; non-positive silence durations accepted silently.
- **Root Cause:** Missing parameter validation for `language` and `min_silence_duration_ms`.

---

## 2. What I Changed
1. `src/subtitle_workbench/audio.py`:
   - Updated `validate_wav` to catch `(wave.Error, EOFError, RuntimeError, struct.error)` and map them to `ValueError(f"Corrupt or invalid WAV file: {err}")`.
2. `src/subtitle_workbench/asr.py`:
   - Validated `min_silence_duration_ms` in `WhisperTranscriber.__init__` and `extract_vad_silences`.
   - Validated `language` in `transcribe` ensuring non-empty string and normalized with `.strip().lower()`.
   - Hardened `validate_wav` and `wave.open` frame reading to catch `RuntimeError` and map to `AudioFormatError`.
   - Preserved full hyphenated compound words via boundary punctuation stripping (`clean_text.strip(...) or spans[0].token`).
   - Ensured monotonic start times in fallback word synthesis (`if words_list and r_ws < words_list[-1].end: r_ws = words_list[-1].end`).
   - Sorted `words_list` by `(w.start, w.end)` and computed segment bounds across all words (`min(w.start)` and `max(w.end)`).
   - Fixed VAD scale heuristic: native faster-whisper is unconditionally treated as sample indices; custom backends use `max(duration + 2.0, duration * 1.2)` tolerance to avoid corrupting slight frame overshoots.
   - Wrapped all `vad_backend` invocations and speech chunk parsing in `try...except ASRError: raise except Exception as exc: raise ASRInferenceError(...)`.
3. `tests/test_asr.py`:
   - Added 8 new adversarial tests covering all 6 defect scenarios (all written first and observed failing before implementing fixes).
4. `docs/increments/INCREMENT_2_ASR_AND_VAD.md`:
   - Updated test counts (306 passed, 1 skipped), verification commands, documented Decision 6, and added new edge cases to Table 6.

---

## 3. Verification Record
- **Deep Verification (ran actual tests):**
  - `uv run --locked pytest`: 306 passed, 1 skipped in 4.14s (261 existing tests + 45 active new ASR tests, 0 regressions).
  - `uv run --locked ruff check .`: Clean, 0 errors.
  - `uv run --locked ruff format --check .`: Clean, 79 files formatted.
  - `uv run --locked python -m build --wheel --no-isolation`: Cleanly built `local_subtitle_workbench-0.1.0-py3-none-any.whl`.
  - `uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output test_smoke_out`: PASS with offline socket guard (max absolute error: 18.4ms).
- **Shallow Verification (manual only):**
  - Verified docstrings and report markdown.
- **Unverified aspects:**
  - Physical execution on NVIDIA GeForce RTX 3050 Laptop GPU with live 3GB Large-v3 weights downloaded (skipped via `pytest.mark.skipif` because speech dependencies are optional and not installed in base environment).

---

## 4. Known Issues
- `Shallow Verification`: Live Faster-Whisper download on physical GPU remains unverified in this offline CPU environment.
- `Minor Robustness Risk`: Very long audio clips (> 2 hours) will read all WAV bytes in `validate_wav` to verify EOF integrity, requiring memory proportional to uncompressed audio size (~230 MB / 2h).

---

## 5. Remaining Risk & Next Step
- The ASR and Silero-VAD contracts are now completely robust against numeric anomalies, timestamp collapse, corrupted chunk structures, compound word truncation, and VAD scale distortions.
- Ready for Increment 3: Macro-DTW alignment and audio chunking consuming `ASRSegment` and `extract_vad_silences` intervals.
