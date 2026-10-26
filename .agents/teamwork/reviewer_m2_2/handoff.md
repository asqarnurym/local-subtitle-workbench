# Review & Adversarial Challenge Report: Milestone 2 Speech Pipeline and CLI Integration

Reviewer: Reviewer 2 (Milestone 2)
Working Directory: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\reviewer_m2_2
Target Commit: 4a6b230 feat(pipeline): wire end-to-end speech alignment pipeline and CLI subcommands
Branch: feature/increment-5-exporters-and-pipeline
Timestamp: 2026-10-26T01:50:00Z

--------------------------------------------------------------------------------

## Review Summary

**Verdict**: APPROVE

All requirements specified for Milestone 2 of Increment 5 (authoritative request section 2026-10-26T00:58:19Z) have been implemented correctly, defensively, and completely. Integrity checks confirm zero hardcoded test fixtures, zero dummy facades, zero task bypasses, and zero fabricated metrics. The implementation passes all 515 automated tests, strict ruff linting, ruff formatting, clean wheel build without isolation, and wheel smoke verification. Backward compatibility with the existing DTW workflow and legacy CLI root flags is completely preserved.

--------------------------------------------------------------------------------

## 1. Observation

1. Code Changes Inspected:
   - `src/subtitle_workbench/text_norm.py`:
     - Lines 364-366: Added `normalize_transcript(transcript: str) -> list[TokenSpan]` delegating directly to `normalize_text_spans(transcript)`.
     - Line 526: Exported `normalize_transcript` in `__all__`.
   - `src/subtitle_workbench/audio.py`:
     - Lines 141-145: Added `get_duration(path: Path | str) -> float` reading frame count and rate via `wave.open(str(path), "rb")`.
     - Line 150: Exported `get_duration` in `__all__`.
   - `src/subtitle_workbench/pipeline.py`:
     - Lines 157-383: Implemented `run_speech_pipeline(audio_path, output_dir, transcript=None, engine="auto", vad_silence_min_sec=0.4, max_chunk_sec=30.0, chunk_padding_sec=0.5, fallback_to_ctc=True, transcriber=None, aligner=None) -> dict`.
     - Validates inputs (`validate_wav`, positive durations, valid engine choice).
     - Protects outputs from overwriting pre-existing files or colliding with input audio/transcript paths.
     - Enforces VRAM lifecycle via `try ... finally` calling `transcriber_inst.unload()` regardless of transcription outcome.
     - Seeds `WordToken`s across duration and partitions into bounded chunks (`partition_into_chunks`).
     - Aligns and stitches via `ForcedAligner` and `reconcile_chunk_alignments`.
     - Generates all 4 artifacts: `subtitles.vtt`, `timeline.jsonld`, `alignment_raw.json`, and `manifest.json`.
     - Preserves `align`, `code_provenance`, `sha256` in `__all__`.
   - `src/subtitle_workbench/cli.py`:
     - Lines 12-17: Implemented `CLIArgumentParser(argparse.ArgumentParser)` overriding `error(message)` to emit `error: <message>` to `stderr` and exit with code 2.
     - Lines 40-75: Added `align-speech` subparser.
     - Lines 78-89: Added `align-dtw` subparser.
     - Lines 26-35, 120-139: Preserved legacy root flags `--reference`, `--target`, `--cues`, `-o/--output`.
     - Lines 91-94, 140-145: Caught exceptions and invalid argument combinations, returning exit code 2 without tracebacks. Returns exit code 0 and JSON metrics on success.
   - `src/subtitle_workbench/__init__.py`:
     - Re-exported `run_speech_pipeline`, `normalize_transcript`, `get_duration`, and `align` in sorted `__all__`.
   - `tests/test_pipeline_speech.py`:
     - Added 21 CPU-safe unit, lifecycle, overwrite protection, and CLI integration tests.

2. Quality Gate Execution Outputs:
   - `uv run --locked pytest tests/test_pipeline_speech.py`:
     `21 passed in 2.44s`
   - `uv run --locked pytest`:
     `515 passed, 1 skipped in 8.50s` (skip: `tests/test_asr.py:1129` faster-whisper not installed in base CPU venv).
   - `uv run --locked ruff check .`:
     `All checks passed!`
   - `uv run --locked ruff format --check .`:
     `271 files already formatted`
   - `uv run --locked python -m build --wheel --no-isolation`:
     `Successfully built local_subtitle_workbench-0.1.0-py3-none-any.whl`
   - `scripts/smoke_wheel.py`:
     `network_guard: passed, max_absolute_error_ms: 18.40`
   - Zero-emoji scan across all modified files: 0 matches found.

--------------------------------------------------------------------------------

## 2. Logic Chain

1. Requirements Conformance:
   - Authoritative requirement R2 calls for `run_speech_pipeline` orchestrating 7 stages: validation, VAD/ASR, normalization, chunking, forced alignment, reconciliation, artifact export. The implementation directly invokes each specialized module (`audio.validate_wav`, `asr.WhisperTranscriber`, `text_norm.normalize_transcript`, `chunker.partition_into_chunks`, `aligner.ForcedAligner`, `chunker.reconcile_chunk_alignments`, `export.*`).
   - R3 requires CLI subcommands (`align-speech`, `align-dtw`) while keeping backward compatibility with root flags and returning exit code 2 on validation/contract errors. Verified through direct subprocess tests and unit tests in `tests/test_pipeline_speech.py` that both subcommands and root flags execute cleanly and return 0 on success and 2 on error with `error: <message>` sent to `stderr`.

2. Defensive Programming & Safety:
   - Output collision checking verifies that neither `output_dir` nor any expected output artifact resolves to the same path as `audio_path` or `transcript_path`.
   - Output overwrite guard prevents clobbering existing runs if any of `subtitles.vtt`, `timeline.jsonld`, `alignment_raw.json`, or `manifest.json` already exists.
   - VRAM safety: `transcriber_inst.unload()` is placed in a `finally` block immediately around the `transcribe` call. Even on unexpected exceptions during transcription, GPU memory is reclaimed before subsequent operations.

3. Integrity Verification:
   - No mock bypasses are embedded in production code. Production modules (`pipeline.py`, `cli.py`, `audio.py`, `text_norm.py`) contain only genuine domain logic.
   - Test mocks in `test_pipeline_speech.py` follow standard testing practices for external heavy neural net backends (Faster-Whisper and PyTorch CTC), which is an explicit constraint in R4 to ensure offline execution in < 5 seconds.

--------------------------------------------------------------------------------

## 3. Findings

### [Minor] Finding 1: Heuristic File Path Detection in Inline Transcript String

- What: Heuristic in `src/subtitle_workbench/pipeline.py` (lines 207-218) detects whether `transcript` is a file path using:
  ```python
  Path(transcript).is_file()
  or (
      "\n" not in transcript
      and (
          transcript.endswith((".txt", ".vtt", ".srt", ".json", ".transcript"))
          or ("/" in transcript or "\\" in transcript)
      )
  )
  ```
- Where: `src/subtitle_workbench/pipeline.py:213`
- Why: If a caller provides an inline transcript string that does not contain newlines but contains a forward slash or backslash (for example, `transcript="either/or"` or `transcript="24/7 service"`), the condition `("/" in transcript or "\\" in transcript)` evaluates to `True`. Because no file named `"either/or"` exists on disk, `run_speech_pipeline` raises `FileNotFoundError: Transcript file not found: either\or`.
- Suggestion: Condition file path detection strictly on `Path(transcript).is_file()` or explicit extensions (`.endswith((".txt", ".vtt", ".srt", ".transcript"))`), rather than treating any slash as an indicator of a file path when the file does not exist.

--------------------------------------------------------------------------------

## 4. Adversarial Challenges & Stress Tests

### Challenge 1: Inline Transcript Slash Collision (Stress-Tested)
- Assumption challenged: Any single-line transcript containing a slash is a file path.
- Attack scenario: Pass `transcript="either/or"` to `run_speech_pipeline`.
- Predicted behavior: Should treat `"either/or"` as text to normalize.
- Actual behavior: Raised `FileNotFoundError: Transcript file not found: either\or`.
- Blast radius: Isolated to inline transcripts containing slashes or backslashes when passed as strings without newlines.
- Mitigation: Improve file path heuristic in a future polish commit.

### Challenge 2: Extreme Parameter Boundaries (Stress-Tested)
- Assumption challenged: Macro-chunking and VAD remain stable when `vad_silence_min_sec` exceeds audio duration (e.g. `100.0s` on `2.0s` audio), or when `audio_duration` is shorter than `chunk_padding_sec` (`0.2s` audio with `0.5s` padding).
- Attack scenario: Run `run_speech_pipeline` with `vad_silence_min_sec=100.0` and `chunk_padding_sec=0.5` on 0.2s synthetic audio.
- Result: PASS. Partitioning clamped padding properly within `[0.0, total_duration]` and created valid chunks without indexing errors or out-of-bounds frames.

### Challenge 3: CLI Subprocess & Exit Code Contract (Stress-Tested)
- Assumption challenged: Custom ArgumentParser prints to stderr and returns code 2 on missing or invalid parameters without stack trace.
- Attack scenarios:
  - `python -m subtitle_workbench --invalid` -> returncode 2, `error: unrecognized arguments: --invalid` on stderr.
  - `python -m subtitle_workbench align-speech audio.wav` (missing -o) -> returncode 2, `error: the following arguments are required: -o/--output` on stderr.
  - `python -m subtitle_workbench align-speech audio.wav -o out --engine invalid` -> returncode 2.
  - `python -m subtitle_workbench` (no args) -> returncode 2.
- Result: PASS. All CLI failure paths strictly return exit code 2 and emit clean error messages without Python tracebacks.

--------------------------------------------------------------------------------

## 5. Verified Claims

- Claim: 21 tests in `tests/test_pipeline_speech.py` pass -> Verified via `uv run --locked pytest tests/test_pipeline_speech.py` -> PASS (21 passed in 2.44s).
- Claim: Entire test suite passes without regressions -> Verified via `uv run --locked pytest` -> PASS (515 passed, 1 skipped in 8.50s).
- Claim: Ruff lint and format clean -> Verified via `uv run --locked ruff check .` and `uv run --locked ruff format --check .` -> PASS (0 errors, 0 diffs across 271 files).
- Claim: Wheel package builds without isolation -> Verified via `uv run --locked python -m build --wheel --no-isolation` -> PASS.
- Claim: Wheel smoke test passes offline -> Verified via `scripts/smoke_wheel.py` -> PASS (network guard passed).
- Claim: VRAM lifecycle unload invoked on error -> Verified in `test_vram_lifecycle_on_error` -> PASS.
- Claim: Backward compatibility for DTW aligner and root CLI flags -> Verified in `test_cli_align_dtw_subcommand` and `test_cli_legacy_root_flags_backward_compatibility` -> PASS.

--------------------------------------------------------------------------------

## 6. Coverage Gaps

- Real Faster-Whisper GPU execution with Large-v3 weights: Skipped in automated CPU test environment per design specs. Risk level: LOW (VRAM management contract verified via mock and unit tests in Increment 2).
- Real MFA system binary execution: Requires external Conda/MFA installation. Risk level: LOW (subprocess runner and TextGrid parser thoroughly tested in Increment 4).

--------------------------------------------------------------------------------

## 7. Caveats

No caveats that invalidate the conclusion. The test suite operates fully offline on CPU in accordance with project hardware boundaries.

--------------------------------------------------------------------------------

## 8. Conclusion

Milestone 2 of Increment 5 satisfies all architectural, functional, security, and quality requirements. The code exhibits strong modularity, rigorous defensive checks against file overwrites and input collisions, robust VRAM lifecycle management, and seamless backward compatibility.

**Verdict: APPROVE**

--------------------------------------------------------------------------------

## 9. Verification Method

To reproduce and verify these findings independently:

```pwsh
# 1. Run Milestone 2 test suite
uv run --locked pytest tests/test_pipeline_speech.py -v

# 2. Run full regression test suite
uv run --locked pytest

# 3. Verify linter and code formatting
uv run --locked ruff check .
uv run --locked ruff format --check .

# 4. Build wheel package without isolation
uv run --locked python -m build --wheel --no-isolation

# 5. Execute offline installed-wheel smoke test
pwsh -Command "if (Test-Path dist/smoke_out) { Remove-Item -Recurse -Force dist/smoke_out }"
uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out
```
