# Review Handoff Report: Milestone 2 Speech Pipeline and CLI Integration

Date: 2026-10-26T01:47:00Z
Reviewer: Reviewer 1 (Milestone 2)
Working Directory: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\reviewer_m2_1
Target Commit: 4a6b230 feat(pipeline): wire end-to-end speech alignment pipeline and CLI subcommands
Verdict: APPROVE

--------------------------------------------------------------------------------

## 1. Observation

### 1.1 Scope and Verification Commands Executed

Direct commands executed in repository `C:\Users\nurym\Desktop\local-subtitle-workbench`:

1. `uv run --locked pytest tests/test_pipeline_speech.py`:
   Output:
   ```text
   ============================= test session starts =============================
   platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0
   rootdir: C:\Users\nurym\Desktop\local-subtitle-workbench
   configfile: pyproject.toml
   collected 21 items

   tests\test_pipeline_speech.py .....................                      [100%]

   ============================= 21 passed in 2.66s ==============================
   ```

2. `uv run --locked pytest`:
   Output:
   ```text
   =========================== short test summary info ===========================
   SKIPPED [1] tests\test_asr.py:1129: faster-whisper is not installed
   ======================= 515 passed, 1 skipped in 8.81s ========================
   ```

3. `uv run --locked ruff check .`:
   Output:
   ```text
   All checks passed!
   ```

4. `uv run --locked ruff format --check .`:
   Output:
   ```text
   271 files already formatted
   ```

5. `uv run --locked python -m build --wheel --no-isolation`:
   Output:
   ```text
   * Getting build dependencies for wheel...
   * Building wheel...
   Successfully built local_subtitle_workbench-0.1.0-py3-none-any.whl
   ```

6. `uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out`:
   Output:
   ```text
   {
     "reference_duration_seconds": 6.5,
     "target_duration_seconds": 7.26,
     "reference_frames": 325,
     "target_frames": 363,
     "evaluated_cells": 15691,
     "path_length": 398,
     "mean_path_cost": 0.002988199899910483,
     "cue_count": 6,
     "alignment_elapsed_seconds": 0.11373359999925015,
     "alignment_rtf": 0.015665785123863657
   }
   {
     "installed_package": "C:\\Users\\nurym\\AppData\\Local\\Temp\\subtitle-wheel-skv4l80i\\venv\\Lib\\site-packages\\subtitle_workbench\\__init__.py",
     "network_guard": "passed",
     "max_absolute_error_ms": 18.400000000000194
   }
   ```

### 1.2 Code Inspection Observations

1. `src/subtitle_workbench/text_norm.py` (lines 364-366, 526):
   - Added `normalize_transcript(transcript: str) -> list[TokenSpan]` wrapping `normalize_text_spans(transcript)`.
   - Exported in `__all__`.

2. `src/subtitle_workbench/audio.py` (lines 142-145, 151):
   - Added `get_duration(path: Path | str) -> float` reading frame count and framerate via `wave.open(str(path), "rb")`.
   - Exported in `__all__`.

3. `src/subtitle_workbench/pipeline.py` (lines 157-383):
   - Implemented `run_speech_pipeline` orchestrating all 7 stages:
     - Stage 1 (Audio Validation): `validate_wav`, `get_duration`, pre-flight collision/overwrite detection on output files and inputs.
     - Stage 2 (VAD & ASR): Automatic transcription via `WhisperTranscriber` with `try ... finally` guaranteeing `transcriber_inst.unload()` is invoked. If explicit transcript provided, reads text or file and extracts VAD silences.
     - Stage 3 (Normalization): Spans generated via `normalize_transcript(text)` and initial `WordToken`s seeded across duration; or existing ASR segment tokens utilized.
     - Stage 4 (Macro-chunking): `partition_into_chunks` with `ChunkConfig(max_chunk_sec, min_silence_duration=vad_silence_min_sec, overlap_padding=chunk_padding_sec)`.
     - Stage 5 & 6 (Forced Alignment & Global Reconciliation): `ForcedAligner.align_chunks(...)` and `reconcile_chunk_alignments(chunks, aligned_result, padded_coordinates=True)`.
     - Stage 7 (Artifact Export): Generates `subtitles.vtt`, `timeline.jsonld`, `alignment_raw.json`, and `manifest.json` using exporters from `export.py`.

4. `src/subtitle_workbench/cli.py` (lines 12-146):
   - `CLIArgumentParser` overrides `error(message)` to print `error: <message>` to `sys.stderr` and exit with code 2 without dumping usage or tracebacks.
   - Subcommand `align-speech` configured with required `audio_wav`, `-o/--output`, and optional parameters.
   - Subcommand `align-dtw` configured with required `ref_wav`, `target_wav`, `cues_json`, `-o/--output`.
   - Root flags `--reference`, `--target`, `--cues`, `-o/--output` retained for backwards compatibility.
   - Missing arguments or invalid parameters print `error: ...` to `stderr` and exit with code 2. Success prints JSON metrics to `stdout` and exits with code 0.

5. `src/subtitle_workbench/__init__.py`:
   - Exported `run_speech_pipeline`, `normalize_transcript`, `get_duration`, and `align` in `__all__`.

6. `tests/test_pipeline_speech.py`:
   - 21 offline CPU tests verifying end-to-end execution, transcript file vs. string inputs, VRAM lifecycle on success and error paths, output overwrite protection, collision detection, corrupt audio handling, and CLI subprocess execution.

--------------------------------------------------------------------------------

## 2. Logic Chain

1. Integrity Audit:
   - Evaluated codebase for hardcoded outputs, dummy facade implementations, and test shortcuts.
   - `get_duration` computes duration from raw RIFF WAV frame headers.
   - `normalize_transcript` reuses existing tokenization and span projection.
   - `run_speech_pipeline` executes real audio validation, VAD/ASR branching, chunk partitioning, forced alignment, and file export.
   - No mock leakage into production code. No integrity violations found.

2. Correctness & Requirements Verification:
   - Requirement R2: 7 pipeline stages are explicitly executed in sequence. The VRAM lifecycle requirement is met via `try ... finally` wrapping `transcriber_inst.transcribe()` and invoking `transcriber_inst.unload()`. Output collision protection prevents destructive overwriting of source audio or transcript.
   - Requirement R3: CLI properly routes `align-speech`, `align-dtw`, and legacy root flags. Error exit code 2 and stdout JSON metrics contract confirmed via subprocess execution tests.
   - Requirement R4.2: Test suite runs in 2.66s on CPU without network calls or external weight downloads.

3. Adversarial Stress-Testing:
   - VRAM error path: Tested simulating `RuntimeError("VRAM allocation failure simulated")` during transcription. Confirmed `unload()` is still invoked and no corrupted output files remain.
   - CLI error contract: Executed subcommands with missing and invalid parameters via subprocess. Exit code 2 returned with clean `error: <message>` on stderr and no Python tracebacks.
   - Transcript path heuristic edge-case: Found that single-line inline transcript strings containing slashes (e.g. `"Hello and/or goodbye"`) without newlines trigger `transcript_file_path.is_file()` checks that fail with `FileNotFoundError`. Classified as a Minor finding.

--------------------------------------------------------------------------------

## 3. Caveats

- Inline transcripts containing `/` or `\` without newlines may be interpreted as missing file paths rather than literal text. Passing a multiline string or avoiding slashes in inline strings works around this.
- Optional dependencies `faster-whisper` and `torchaudio` are mocked in tests to comply with the < 5s offline CPU test requirement.

--------------------------------------------------------------------------------

## 4. Findings

### [Minor] Finding 1: Heuristic distinction between transcript file path and inline text

- What: `pipeline.py` (lines 207-217) classifies a transcript as a file path if `"\n" not in transcript` and (`"/" in transcript` or `"\\" in transcript`).
- Where: `src/subtitle_workbench/pipeline.py:213`
- Why: If an inline transcript contains a forward slash (e.g., `"Hello and/or goodbye"` or `"Ratio is 50/50"`), the pipeline attempts to treat it as a file path and raises `FileNotFoundError: Transcript file not found`.
- Suggestion: In future maintenance, refine the heuristic: check if `Path(transcript).is_file()` first, and for non-existent paths, only treat as a missing file if it does not contain whitespace or if it ends with a recognized transcript extension (`.txt`, `.vtt`, `.srt`, `.json`, `.transcript`).

--------------------------------------------------------------------------------

## 5. Conclusion

**Verdict: APPROVE**

The work product implemented by Worker 2 for Milestone 2 meets all functional, structural, and performance criteria:
- All 7 speech pipeline stages are implemented and integrated.
- Strict VRAM lifecycle management is enforced via `try ... finally`.
- Full CLI subcommand support (`align-speech`, `align-dtw`) and backward-compatible root flags implemented with the exit code 2 contract.
- 515 of 516 tests pass (1 skipped due to optional dependency), linters and formatters pass with zero errors, wheel builds cleanly, and smoke tests pass.
- Zero emojis found across all code, logs, and artifacts.

--------------------------------------------------------------------------------

## 6. Verification Method

To independently reproduce this verification:

```pwsh
# 1. Run speech pipeline tests
uv run --locked pytest tests/test_pipeline_speech.py -v

# 2. Run all tests
uv run --locked pytest

# 3. Verify ruff lint and format
uv run --locked ruff check .
uv run --locked ruff format --check .

# 4. Build wheel and run smoke test
uv run --locked python -m build --wheel --no-isolation
pwsh -Command "if (Test-Path dist/smoke_out) { Remove-Item -Recurse -Force dist/smoke_out }"
uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out
```
