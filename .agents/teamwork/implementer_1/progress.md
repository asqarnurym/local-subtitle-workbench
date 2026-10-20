# Progress: Increment 2 (ASR & VAD)

## Status: COMPLETED

### Checklist
- [x] Initialized BRIEFING.md and progress.md
- [x] R1: Add optional dependency group `speech` to `pyproject.toml`
- [x] R3: Write comprehensive unit/contract tests in `tests/test_asr.py` following TDD (RED phase confirmed)
- [x] R2: Implement `src/subtitle_workbench/asr.py` with `WhisperTranscriber`, `extract_vad_silences`, exceptions
- [x] R2: Export public API in `src/subtitle_workbench/__init__.py`
- [x] Verify tests: `uv run --locked pytest` (290 passed, 1 skipped)
- [x] Verify linter: `uv run --locked ruff check .` (0 errors)
- [x] Verify formatting: `uv run --locked ruff format --check .` (71 files clean)
- [x] Verify build: `uv run --locked python -m build --wheel --no-isolation` (wheel built)
- [x] Verify smoke test: `uv run python scripts/smoke_wheel.py` (PASS, max error 18.4ms)
- [x] Document report: `docs/increments/INCREMENT_2_ASR_AND_VAD.md`
- [x] Commit: `git commit -m "feat(asr): implement faster-whisper transcriber and vad silence extractor with vram lifecycle"`
- [x] Handoff: `handoff.md` and `send_message`
