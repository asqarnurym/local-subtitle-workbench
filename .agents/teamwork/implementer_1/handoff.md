# Implementer Handoff Report: Increment 2 (ASR & VAD)

**Increment ID:** `INCREMENT_2_ASR_AND_VAD`  
**Git Branch:** `feature/increment-2-asr-and-vad`  
**Git Commit:** `27bf2529b7dcbd621fd79e82bf6e386b1b8e348d`  
**Commit Message:** `feat(asr): implement faster-whisper transcriber and vad silence extractor with vram lifecycle`  
**Report File:** `docs/increments/INCREMENT_2_ASR_AND_VAD.md`  

---

## 1. Executive Summary
Implemented Increment 2 for the Local Subtitle Alignment Workbench:
- **Faster-Whisper Large-v3 INT8 Transcriber (`WhisperTranscriber`):** Autoselection of compute device (`cuda` if available else `cpu`) and quantization (`int8_float16` for CUDA, `int8` for CPU) guaranteeing peak VRAM <= 1.85 GB on 4 GB laptop GPU.
- **Deterministic VRAM Lifecycle:** Explicit `unload()` method clears model reference, invokes Python garbage collector (`gc.collect()`), and flushes CUDA cache (`torch.cuda.empty_cache()`), preventing inter-stage memory leaks.
- **Silero-VAD Silence Extractor (`extract_vad_silences`):** Detects acoustic pause intervals (>= 400 ms) complementary to speech regions for drift-free macro-alignment in Increment 3.
- **Bijective Normalization Linkage:** Links ASR words directly to `WordToken` dataclasses with normalized tokens from `text_norm.normalize_text_spans`.
- **Exception Hierarchy:** `ASRError` base with typed subclasses `AudioFormatError`, `ASRInferenceError`, and `VRAMAllocationError` adhering to ECC Error Handling patterns.
- **Offline CPU Isolation:** All heavy dependencies (`faster-whisper`, `torch`) are configured as optional speech dependencies (`[project.optional-dependencies] speech`) and imported lazily. Base distribution and test suite run 100% offline on CPU.

---

## 2. File Inventory
1. `pyproject.toml` — Added `speech` optional dependencies group (`faster-whisper>=1.0.0`, `torch>=2.2.0`).
2. `uv.lock` — Updated lockfile with resolved speech packages.
3. `src/subtitle_workbench/asr.py` — New module containing `WhisperTranscriber`, `extract_vad_silences`, and `ASRError` hierarchy.
4. `src/subtitle_workbench/audio.py` — Added `validate_wav` to enforce PCM16 16 kHz format before model ingestion.
5. `src/subtitle_workbench/__init__.py` — Exported public ASR API components.
6. `tests/test_asr.py` — 30 comprehensive unit, contract, VRAM lifecycle, and failure-mode tests with dummy backend.
7. `docs/increments/INCREMENT_2_ASR_AND_VAD.md` — Formal SDLC increment audit report.

---

## 3. Quality Gate Results
- **Pytest:** `uv run --locked pytest`
  - 290 passed, 1 skipped in 3.69s (261 existing tests + 29 active new tests, 0 regressions, 0 failures).
- **Ruff Check:** `uv run --locked ruff check .`
  - All checks passed (0 errors, 0 warnings).
- **Ruff Format:** `uv run --locked ruff format --check .`
  - 71 files already formatted.
- **Wheel Build:** `uv run --locked python -m build --wheel --no-isolation`
  - Built `local_subtitle_workbench-0.1.0-py3-none-any.whl`.
- **Smoke Wheel Test:** `uv run python scripts/smoke_wheel.py`
  - PASS under offline socket guard (max error 18.4ms).
