# Empirical Challenge Report: Milestone 2 Speech Pipeline and CLI Integration

Date: 2026-10-26T01:48:45Z
Challenger: Challenger 1 (Milestone 2)
Working Directory: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\challenger_m2_1
Target Commit: 4a6b230 feat(pipeline): wire end-to-end speech alignment pipeline and CLI subcommands
Verdict: APPROVE

--------------------------------------------------------------------------------

## 1. Observation

1. Implementation Inspection:
   - `src/subtitle_workbench/pipeline.py` (lines 182-227):
     - Output existence pre-flight checks:
       `outputs = [output_dir / name for name in ("subtitles.vtt", "timeline.jsonld", "alignment_raw.json", "manifest.json")]`
       `if any(p.exists() for p in outputs): raise ValueError("output files already exist; choose a new output directory")`
     - Audio and transcript collision guards:
       `if output_dir.resolve() == resolved_audio or any(p.resolve() == resolved_audio for p in outputs): raise ValueError("output may not overwrite an input")`
       `if output_dir.resolve() == resolved_transcript or any(p.resolve() == resolved_transcript for p in outputs): raise ValueError("output may not overwrite an input")`
   - `src/subtitle_workbench/pipeline.py` (lines 232-247):
     - VRAM lifecycle management:
       ```python
       try:
           try:
               silences = extract_vad_silences(audio_path, min_silence_duration_ms=silence_min_ms)
           except Exception:
               silences = []
           segments = transcriber_inst.transcribe(audio_path)
       finally:
           if hasattr(transcriber_inst, "unload") and callable(transcriber_inst.unload):
               transcriber_inst.unload()
       ```
   - `src/subtitle_workbench/pipeline.py` (lines 248-267):
     - Transcript validation:
       `text = raw_text.strip()`
       `if not text: raise ValueError("transcript cannot be empty")`
       `spans = normalize_transcript(text)`
       `if not spans: raise ValueError("transcript contains no valid words after normalization")`
   - `src/subtitle_workbench/cli.py` (lines 12-18, 96-146):
     - `CLIArgumentParser` overrides `error(message)` to print `error: <message>` to `stderr` and invoke `sys.exit(2)`.
     - `main()` catches all exceptions, printing `error: {error}` to `stderr` and returning exit code 2 without stack traces.

2. Adversarial Test Harness Created (`tests/test_challenger_m2_1.py`):
   - Created 50 discrete stress tests testing 7 dimensions:
     - 5 tests for VRAM lifecycle under error (CUDA OOM, generic exceptions, empty segments, VAD failure, duck-typing without unload).
     - 11 tests for collision detection (exact path, relative path, output artifact name matches for audio and transcript).
     - 6 tests for existing output directory rejection (each artifact individually, all together, permitting unrelated files).
     - 9 tests for audio error handling (missing, directory, 0 bytes, 0 frames, truncated data, corrupt header, stereo, 44.1 kHz, 8-bit).
     - 7 tests for transcript error handling (empty string, whitespace string, empty file, whitespace file, missing Path, missing string path, punctuation-only).
     - 7 tests for pipeline properties and parameter guards (engine, thresholds, monotonicity, SHA-256 hash matching).
     - 5 tests for CLI subcommand exit code 2 contract without tracebacks.

3. Empirical Test Execution Output:
   - Command: `uv run --locked pytest tests/test_challenger_m2_1.py -v`
     - Result: 50 passed in 1.66s.
   - Command: `uv run --locked pytest`
     - Result: 565 passed, 1 skipped in 10.18s (566 total items across test suite).
   - Command: `uv run --locked ruff check .`
     - Result: "All checks passed!" (0 errors).
   - Command: `uv run --locked ruff format --check .`
     - Result: "274 files already formatted" (0 diffs).
   - Command: `uv run --locked python -m build --wheel --no-isolation`
     - Result: Successfully built `local_subtitle_workbench-0.1.0-py3-none-any.whl` (exit code 0).
   - Command: `uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out`
     - Result: Exit code 0, network guard passed, max absolute error 18.4ms.

--------------------------------------------------------------------------------

## 2. Logic Chain

1. Step 1 (VRAM Cleanup Verification):
   - Observation: `pipeline.py` wraps transcription within `try ... finally` calling `transcriber.unload()`.
   - Stress test: Simulated `RuntimeError("CUDA out of memory")`, `ValueError("tensor shape")`, empty segments `[]`, and VAD failures.
   - Finding: In every failure case, `transcriber.unload()` was strictly called exactly once, preventing VRAM leaks even when catastrophic errors abort execution.

2. Step 2 (Output Collision and Rejection Verification):
   - Observation: `pipeline.py` compares `output_dir.resolve()` and all candidate artifact target paths against input files.
   - Stress test: Supplied paths where `output_dir == audio_path`, `output_dir == transcript_path`, audio named `subtitles.vtt`, and transcript named `manifest.json`.
   - Finding: `ValueError("output may not overwrite an input")` is raised deterministically across all collision vectors.

3. Step 3 (Existing Output Directory Pre-flight):
   - Observation: `pipeline.py` verifies `any(p.exists() for p in outputs)`.
   - Stress test: Placed `subtitles.vtt`, `timeline.jsonld`, `alignment_raw.json`, and `manifest.json` individually and collectively into target output directories.
   - Finding: In all conflict scenarios, `ValueError("output files already exist; choose a new output directory")` is raised. Conversely, directories containing unrelated files (e.g. `notes.txt`) are correctly permitted without false positives.

4. Step 4 (Input Audio and Transcript Boundary Robustness):
   - Observation: Audio inputs route through `validate_wav` and `get_duration`; transcripts route through file resolution and `normalize_transcript`.
   - Stress test: Injected 0-byte files, truncated WAVs, 0-frame headers, stereo WAVs, non-16kHz WAVs, whitespace transcripts, 0-byte transcript files, missing paths, and punctuation-only text.
   - Finding: All invalid inputs are rejected with targeted `ValueError` or `FileNotFoundError` prior to heavy pipeline execution.

5. Step 5 (CLI Contract & Quality Gates):
   - Observation: `cli.py` maps all internal exceptions and CLI parsing failures to exit code 2 and writes clean single-line messages to stderr.
   - Stress test: Tested missing files, collisions, existing directories, and empty transcripts through `main()`.
   - Finding: All adversarial CLI runs exited with code 2 and zero tracebacks on stderr. Full project test suite (565 passed, 1 skipped), linters, formatting, and offline wheel build all passed without issues.

--------------------------------------------------------------------------------

## 3. Caveats

- As faster-whisper and torch are optional dependencies in the CPU-only test environment, VRAM lifecycle tests utilize spec-compliant mock transcribers with tracked calls. Actual CUDA memory deallocation (`torch.cuda.empty_cache()`) was previously validated in Increment 2.
- No other caveats.

--------------------------------------------------------------------------------

## 4. Conclusion

**Verdict: APPROVE**

Milestone 2 implementation is robust, defensive, and adheres strictly to all architectural specifications:
- VRAM lifecycle is guaranteed across all normal and exceptional paths via `try ... finally`.
- Input collision protection prevents accidental data corruption or overwrite.
- Existing output directory rejection reliably protects prior run artifacts.
- Audio and transcript validations defend against malformed, truncated, or empty inputs.
- CLI subcommands satisfy the exit code 2 contract with clean error reporting.
- All 50 empirical adversarial challenge tests and all 516 baseline tests pass cleanly.

--------------------------------------------------------------------------------

## 5. Verification Method

To independently verify this empirical challenge report:

1. Run the adversarial stress test suite:
   ```pwsh
   uv run --locked pytest tests/test_challenger_m2_1.py -v
   ```
   Expected: 50 passed in < 2 seconds.

2. Run the complete project test suite:
   ```pwsh
   uv run --locked pytest
   ```
   Expected: 565 passed, 1 skipped in ~10 seconds.

3. Verify zero lint errors and zero formatting differences:
   ```pwsh
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   Expected: All checks passed, 274 files formatted.

4. Verify offline wheel build and smoke test:
   ```pwsh
   uv run --locked python -m build --wheel --no-isolation
   pwsh -Command "if (Test-Path dist/smoke_out) { Remove-Item -Recurse -Force dist/smoke_out }"
   uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out
   ```
   Expected: Built wheel cleanly, network guard passed.

--------------------------------------------------------------------------------

## Adversarial Review Summary

**Overall risk assessment**: LOW

### Stress Test Results

| Attack Vector | Expected Result | Actual Result | Status |
|---|---|---|---|
| Transcribe raises CUDA OOM | transcriber.unload() called | unload() called once, no artifacts | [PASS] |
| Transcribe raises Generic Exception | transcriber.unload() called | unload() called once, no artifacts | [PASS] |
| Transcribe returns empty segments | unload() called, ValueError | unload() called, ValueError raised | [PASS] |
| VAD extractor crashes | silences fallback to [], unload() called | silences=[], unload() called | [PASS] |
| Transcriber lacks unload method | Safe duck-typing handling | Handled cleanly without AttributeError | [PASS] |
| Output dir equals input WAV | ValueError (collision) | ValueError raised | [PASS] |
| Output dir equals input transcript | ValueError (collision) | ValueError raised | [PASS] |
| Input WAV named subtitles.vtt | ValueError (collision / exists) | ValueError raised | [PASS] |
| Input transcript named manifest.json | ValueError (collision / exists) | ValueError raised | [PASS] |
| Output dir contains subtitles.vtt | ValueError (already exists) | ValueError raised | [PASS] |
| Output dir contains timeline.jsonld | ValueError (already exists) | ValueError raised | [PASS] |
| Output dir contains alignment_raw.json | ValueError (already exists) | ValueError raised | [PASS] |
| Output dir contains manifest.json | ValueError (already exists) | ValueError raised | [PASS] |
| Output dir contains unrelated files | Pipeline completes normally | Completed normally | [PASS] |
| Missing audio WAV | FileNotFoundError | FileNotFoundError raised | [PASS] |
| Directory passed as audio WAV | FileNotFoundError | FileNotFoundError raised | [PASS] |
| 0-byte audio file | ValueError | ValueError raised | [PASS] |
| 0-frame WAV with valid header | ValueError | ValueError raised | [PASS] |
| Truncated WAV payload | ValueError | ValueError raised | [PASS] |
| Corrupted RIFF header | ValueError | ValueError raised | [PASS] |
| Stereo (2-channel) WAV | ValueError | ValueError raised | [PASS] |
| Non-16kHz WAV (44.1 kHz) | ValueError | ValueError raised | [PASS] |
| Non-16-bit WAV (8-bit) | ValueError | ValueError raised | [PASS] |
| Empty transcript string | ValueError | ValueError raised | [PASS] |
| Whitespace transcript string | ValueError | ValueError raised | [PASS] |
| 0-byte transcript file | ValueError | ValueError raised | [PASS] |
| Whitespace transcript file | ValueError | ValueError raised | [PASS] |
| Missing transcript Path | FileNotFoundError | FileNotFoundError raised | [PASS] |
| Missing transcript str (.txt) | FileNotFoundError | FileNotFoundError raised | [PASS] |
| Punctuation-only transcript | ValueError | ValueError raised | [PASS] |
| Invalid engine string | ValueError | ValueError raised | [PASS] |
| Negative/zero thresholds | ValueError | ValueError raised | [PASS] |
| Monotonicity and hash verification | Strict monotonicity + SHA256 match | Validated across 5 sequential tokens | [PASS] |
| CLI align-speech missing audio | Exit code 2, clean stderr | Exit 2, error: File not found | [PASS] |
| CLI align-speech empty transcript | Exit code 2, clean stderr | Exit 2, error: transcript cannot be empty | [PASS] |
| CLI align-speech missing transcript | Exit code 2, clean stderr | Exit 2, error: Transcript file not found | [PASS] |
| CLI align-speech collision | Exit code 2, clean stderr | Exit 2, error: output may not overwrite an input | [PASS] |
| CLI align-speech existing artifact | Exit code 2, clean stderr | Exit 2, error: output files already exist | [PASS] |
