# Handoff Report: Milestone 2 Speech Pipeline and CLI Integration

Date: 2026-10-26T01:41:00Z
Worker: Worker 2 (Milestone 2)
Working Directory: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m2_1
Branch: feature/increment-5-exporters-and-pipeline
Commit: 4a6b230 feat(pipeline): wire end-to-end speech alignment pipeline and CLI subcommands

--------------------------------------------------------------------------------

## 1. Observation

1. Codebase Baseline & Requirements:
   - Target files under write ownership:
     - `src/subtitle_workbench/text_norm.py`
     - `src/subtitle_workbench/audio.py`
     - `src/subtitle_workbench/pipeline.py`
     - `src/subtitle_workbench/cli.py`
     - `src/subtitle_workbench/__init__.py`
     - `tests/test_pipeline_speech.py`
   - Initial test baseline: 494 passed, 1 skipped in 6.09s (`tests/test_asr.py:1129` skipped as `faster-whisper` is an optional dependency in the CPU test environment).

2. Implementation Artifacts Created & Modified:
   - `src/subtitle_workbench/text_norm.py`:
     - Added `normalize_transcript(transcript: str) -> list[TokenSpan]` wrapping `normalize_text_spans(transcript)`.
     - Exported `normalize_transcript` in `__all__`.
   - `src/subtitle_workbench/audio.py`:
     - Added `get_duration(path: Path | str) -> float` reading frame count and framerate via `wave.open(str(path), "rb")`.
     - Exported `get_duration` in `__all__`.
   - `src/subtitle_workbench/pipeline.py`:
     - Implemented `run_speech_pipeline(audio_path, output_dir, transcript=None, engine="auto", vad_silence_min_sec=0.4, max_chunk_sec=30.0, chunk_padding_sec=0.5, fallback_to_ctc=True, transcriber=None, aligner=None) -> dict`.
     - Executed all 7 stages:
       - Stage 1 (Audio Validation): `validate_wav`, `get_duration`, output overwrite protection checking `subtitles.vtt`, `timeline.jsonld`, `alignment_raw.json`, and `manifest.json`, and collision checking against audio and transcript paths (`ValueError("output may not overwrite an input")`).
       - Stage 2 (VAD & ASR): ASR branching with guaranteed `transcriber.unload()` inside `try ... finally` block. When transcript is supplied, reads text string or file, validates non-empty text, and extracts silences with fallback to `[]`.
       - Stage 3 (Normalization): Seeds uniform `WordToken`s across audio duration from `normalize_transcript` spans. If ASR run, uses segment tokens directly.
       - Stage 4 (Macro-chunking): `partition_into_chunks` with `ChunkConfig(max_chunk_sec, min_silence_duration=vad_silence_min_sec, overlap_padding=chunk_padding_sec)`.
       - Stage 5 & 6 (Forced Alignment & Global Reconciliation): `ForcedAligner.align_chunks(...)` returning seam-deduplicated, monotonic `WordToken`s.
       - Stage 7 (Artifact Export): Writes `subtitles.vtt` (`export_karaoke_vtt`), `timeline.jsonld` (`export_jsonld`), `alignment_raw.json` (`export_raw_alignment`), and `manifest.json` (`generate_manifest`). Returns execution manifest dictionary.
     - Retained `align`, `code_provenance`, `sha256` in `__all__` alongside `run_speech_pipeline`.
   - `src/subtitle_workbench/cli.py`:
     - Implemented `CLIArgumentParser(argparse.ArgumentParser)` overriding `error(message)` to print `error: <message>` to `stderr` and exit with code 2.
     - Added `align-speech` subparser: `audio_wav`, `-o/--output`, `--engine`, `--transcript`, `--vad-silence-min-sec`, `--max-chunk-sec`, `--chunk-padding-sec`.
     - Added `align-dtw` subparser: `ref_wav`, `target_wav`, `cues_json`, `-o/--output`, `--band-seconds`, `--spectral-weight`, `--max-frames`, `--max-cells`.
     - Preserved full backward compatibility with root flags: `--reference`, `--target`, `--cues`, `-o/--output` when no subcommand is specified.
     - Exit code contract: 0 on success (JSON summary metrics to `stdout`), 2 on validation/contract/parsing errors (`error: <message>` to `stderr` with no traceback).
   - `src/subtitle_workbench/__init__.py`:
     - Exported `run_speech_pipeline`, `normalize_transcript`, `get_duration`, and `align` in `__all__`.
   - `tests/test_pipeline_speech.py`:
     - Added 21 offline CPU tests covering end-to-end pipeline execution with mocks, transcript file and string handling, VRAM lifecycle on success and error paths, output overwrite protection, collision detection, audio corruption, and CLI subprocess execution.

3. Automated Quality Gate Results:
   - `uv run --locked pytest tests/test_pipeline_speech.py`: 21 passed in 2.43s.
   - `uv run --locked pytest`: 515 passed, 1 skipped in 8.06s.
   - `uv run --locked ruff check .`: "All checks passed!" (0 errors).
   - `uv run --locked ruff format --check .`: "251 files already formatted" (0 diffs).
   - `uv run --locked python -m build --wheel --no-isolation`: Built `local_subtitle_workbench-0.1.0-py3-none-any.whl` with exit code 0.
   - `uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out`: Clean run, network guard passed, max absolute error 18.4ms.

--------------------------------------------------------------------------------

## 2. Logic Chain

1. Step 1 (Audio duration and transcript normalization helpers):
   - `audio.py` lacked an O(1) header-only duration reader. Implementing `get_duration` with `wave.open` provides duration calculation without array loading.
   - `text_norm.py` had `normalize_text_spans` but lacked `normalize_transcript`. Wrapping `normalize_text_spans` in `normalize_transcript` satisfied the requested public API while reusing tokenization logic.

2. Step 2 (End-to-end speech pipeline orchestration):
   - Hardware constraints dictate strict VRAM management: `WhisperTranscriber.unload()` must run immediately after transcription and before alignment. Placing transcription in `try ... finally` guarantees `transcriber.unload()` is invoked in both success and error paths.
   - Slicing and alignment reconciliation: `ForcedAligner.align_chunks` handles audio chunk slicing and calls `reconcile_chunk_alignments`. Defensively checking if the result is 2D and flattening via `reconcile_chunk_alignments(chunks, result, padded_coordinates=True)` ensures compatibility with mock objects.
   - Collision protection: verifying that no expected output path equals `audio_path.resolve()` or `transcript_path.resolve()` prevents destructive overwrites.

3. Step 3 (CLI architecture and exit code contract):
   - Providing optional subparsers alongside top-level flags in `CLIArgumentParser` allows `subtitle-workbench` to dispatch to `align-speech`, `align-dtw`, or legacy root flags.
   - Catching all domain and I/O exceptions in `main()` ensures `error: <message>` is printed to `stderr` and status code 2 is returned without Python tracebacks, fulfilling requirement R3.

4. Step 4 (Offline CPU test suite):
   - Using synthetic WAV fixtures and spec-compliant mocks for transcriber and aligner ensures the 21 new tests run in < 2.5 seconds on pure CPU without PyTorch or external model weights.

--------------------------------------------------------------------------------

## 3. Caveats

- In environments where optional dependencies (`faster-whisper`, `torchaudio`) are not installed, `run_speech_pipeline(transcript=None)` requires either a mock transcriber or an explicit transcript string/file. This is the intended architecture to keep the base package lightweight.
- `scripts/smoke_wheel.py` requires that `dist/smoke_out` does not already exist prior to execution because `demo.generate()` enforces an empty output directory.

--------------------------------------------------------------------------------

## 4. Conclusion

Milestone 2 implementation is complete and verified:
- `normalize_transcript` and `get_duration` helpers added and exported.
- `run_speech_pipeline` fully wires the 7-stage speech pipeline with strict VRAM lifecycle and artifact exports.
- `cli.py` supports `align-speech` and `align-dtw` subcommands while retaining full backward compatibility with root flags and adhering to the exit code 2 contract.
- 21 comprehensive offline CPU tests added in `tests/test_pipeline_speech.py`.
- All 515 tests pass, linters pass with 0 warnings, wheel build succeeds, and smoke test passes.
- Changes committed as `4a6b230 feat(pipeline): wire end-to-end speech alignment pipeline and CLI subcommands`.

--------------------------------------------------------------------------------

## 5. Verification Method

To independently verify these deliverables:

1. Run unit and integration tests for Milestone 2:
   ```pwsh
   uv run --locked pytest tests/test_pipeline_speech.py -v
   ```
   Expected: 21 passed in < 3 seconds.

2. Run full test suite:
   ```pwsh
   uv run --locked pytest
   ```
   Expected: 515 passed, 1 skipped in ~8 seconds.

3. Verify linter and formatter:
   ```pwsh
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   Expected: All checks passed, 251 files formatted.

4. Verify wheel packaging and smoke test:
   ```pwsh
   uv run --locked python -m build --wheel --no-isolation
   pwsh -Command "if (Test-Path dist/smoke_out) { Remove-Item -Recurse -Force dist/smoke_out }"
   uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out
   ```
   Expected: Exit code 0, network guard passed.

5. Verify git commit on branch `feature/increment-5-exporters-and-pipeline`:
   ```pwsh
   git log -n 1 --oneline
   ```
   Expected: `4a6b230 feat(pipeline): wire end-to-end speech alignment pipeline and CLI subcommands`.
