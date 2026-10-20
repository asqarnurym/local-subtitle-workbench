# Reviewer Round 1 Handoff Report: Increment 2 (ASR & VAD)

**Reviewer:** `teamwork_preview_reviewer` (Round 1)  
**Git Branch:** `feature/increment-2-asr-and-vad`  
**Repository:** `c:\Users\nurym\Desktop\local-subtitle-workbench`  
**Target:** Increment 2 (Faster-Whisper Large-v3 INT8 & Silero-VAD with GPU VRAM Lifecycle)  

---

## 1. What the Prior Attempt Got Wrong (Input → Expected → Actual → Root Cause)

### Issue 1: Sub-threshold Silence Window in `extract_vad_silences`
- **Input:** 200 ms audio clip with no detected speech and `min_silence_duration_ms=400`.
- **Expected:** `[]` (silence interval < 400 ms must not be reported per contract).
- **Actual:** `[(0.0, 0.2)]` returned.
- **Root Cause:** In `extract_vad_silences`, `if not speech_chunks:` unconditionally returned `[(0.0, round(duration, 4))]` without verifying `duration >= min_silence_sec - 1e-6`.

### Issue 2: Timestamp Rounding Collapse (`start == end`) Leaking Raw `ValueError`
- **Input:** Word timestamps differing by microsecond values, e.g. `start = 1.00001`, `end = 1.00004`.
- **Expected:** `WordToken` contract `0.0 <= start < end` strictly preserved after rounding; no exception thrown.
- **Actual:** `round(1.00001, 4)` and `round(1.00004, 4)` both rounded to `1.0`. `WordToken.__post_init__` threw unhandled `ValueError: start must be strictly less than end`, leaking out of `transcribe()`.
- **Root Cause:** Enforced `w_end > w_start` before rounding, but did not re-verify `r_end > r_start` after rounding to 4 decimal places. Furthermore, the segment construction loop was not wrapped in an error handler to map unexpected normalization errors to `ASRInferenceError`.

### Issue 3: Fragile `and c[0] > 100` Heuristic Corrupting VAD Pause Detection
- **Input A:** 120-second audio clip with speech chunk `(105, 110)` in integer seconds.
- **Expected A:** Silences `[(0.0, 105.0), (110.0, 120.0)]`.
- **Actual A:** `[(0.0069, 120.0)]` returned because `105 > 100` triggered division by 16000, treating 105 seconds as sample index 105.
- **Input B:** 1-second audio clip with speech chunk `(50, 16000)` in sample frames.
- **Expected B:** 50 samples scaled by 16000 to ~0.0031s.
- **Actual B:** `50 > 100` evaluated to False, treating 50 samples as 50.0 seconds in a 1.0-second clip.
- **Root Cause:** Arbitrary magic number `100` used to distinguish sample indices from seconds.

### Issue 4: Control Characters and Surrogates Leaking `ValueError`
- **Input:** External ASR backend yielding raw token text containing `\x00` or control characters.
- **Expected:** Sanitized clean tokens meeting `WordToken` dataclass constraints without uncaught exceptions.
- **Actual:** `normalize_text_spans` raised `ValueError: text must not contain control characters`, leaking raw `ValueError` to caller.
- **Root Cause:** Lack of string sanitization on raw text from external model before passing to `normalize_text_spans` and `WordToken`.

### Issue 5: Omitted Word Timestamps Dropping Entire Spoken Segments
- **Input:** Whisper transcribes segment text (`text="Synthesized segment text"`), but alignment fails and `raw_seg.words` is `[]` or `None`.
- **Expected:** Spoken segment preserved; WordTokens synthesized from segment text across `[seg_start, seg_end]`.
- **Actual:** Segment silently discarded (`if not words_list: continue`).
- **Root Cause:** Missing fallback word synthesis from segment text when `raw_words` is omitted by the ASR backend.

### Issue 6: Fragile CUDA OOM Error Matching
- **Input:** CTranslate2 or CUDA backend raises `RuntimeError("Failed to allocate 2097152 bytes on device: CUDA error")`.
- **Expected:** Wrapped in `VRAMAllocationError`.
- **Actual:** Fell through to `ASRInferenceError`.
- **Root Cause:** Narrow substring matching only looking for `"out of memory"`.

### Issue 7: Unhandled Exception in Device Resolution
- **Input:** `torch.cuda.is_available()` raises `RuntimeError("Driver mismatch")`.
- **Expected:** Graceful fallback to CPU device.
- **Actual:** Uncaught exception in `WhisperTranscriber.__init__`.
- **Root Cause:** Only `ImportError` caught during device auto-selection.

---

## 2. What I Changed
1. `src/subtitle_workbench/asr.py`:
   - Added `_sanitize_text` to strip control characters and surrogates before validation.
   - Added `_is_vram_allocation_error` supporting broad CUDA allocation failure patterns.
   - Made `_resolve_device_and_compute_type` and `unload` catch `(ImportError, Exception)` for driver resilience.
   - Implemented post-rounding strict inequality (`r_end > r_start`) for word tokens and segments.
   - Added fallback word synthesis from `seg_text` when `raw_words` is empty.
   - Wrapped segment building in `try...except ASRError: raise except Exception as exc: raise ASRInferenceError(...)`.
   - Replaced magic `c[0] > 100` heuristic in `extract_vad_silences` with scale-independent check `any(max(s, e) > duration + 1e-3)`.
   - Handled sub-threshold audio files (`duration < min_silence_sec`) returning empty silence lists.
   - Clamped VAD speech timestamps to `[0.0, duration]`.
2. `tests/test_asr.py`:
   - Added 8 adversarial tests under Section 9 covering all 8 defect scenarios (TDD: tests written first, observed failing, then greened).
3. `docs/increments/INCREMENT_2_ASR_AND_VAD.md`:
   - Updated test counts, verification commands, and documented architectural decision 5.

---

## 3. Verification Record
- **Deep Verification (ran actual tests):**
  - `uv run --locked pytest`: 298 passed, 1 skipped in 4.01s (261 existing tests + 37 active new ASR tests, 0 regressions).
  - `uv run --locked ruff check .`: Clean, 0 errors.
  - `uv run --locked ruff format --check .`: Clean, 75 files formatted.
  - `uv run --locked python -m build --wheel --no-isolation`: Cleanly built `local_subtitle_workbench-0.1.0-py3-none-any.whl`.
  - `uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output test_smoke_out`: PASS with offline socket guard (max error 18.4ms).
- **Shallow Verification (manual only):**
  - Verified docstrings and report markdown.
- **Unverified aspects:**
  - Physical execution on NVIDIA GeForce RTX 3050 Laptop GPU with live 3GB Large-v3 weights downloaded (skipped via `pytest.mark.skipif` because speech dependencies are optional and not installed in base environment).

---

## 4. Known Issues
- `Shallow Verification`: Live Faster-Whisper download on physical GPU remains unverified in this offline CPU container.
- `Minor Robustness Risk`: Very long audio clips (> 2 hours) will read all WAV bytes in `validate_wav` to verify EOF integrity, requiring memory proportional to uncompressed audio size (~230 MB / 2h).

---

## 5. Remaining Risk & Next Step
- The ASR and Silero-VAD contracts are now fully hardened against numeric anomalies, timestamp collapse, VAD scale distortion, and driver faults.
- Ready for Increment 3: Macro-DTW alignment and audio chunking consuming `ASRSegment` and `extract_vad_silences` intervals.
