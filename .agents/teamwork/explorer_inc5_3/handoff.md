# Increment 5 Handoff Report: CLI Architecture, Test Baseline, Wheel Smoke Testing, and Documentation Specifications

## 1. Observation

### 1.1 CLI Module Inspection (`src/subtitle_workbench/cli.py`)
- **Current Entry Point**:
  - File: `src/subtitle_workbench/cli.py` (lines 13-46):
    ```python
    def main(argv: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            description="Transfer checked English subtitle timings between local audio tracks."
        )
        parser.add_argument(
            "--reference", required=True, type=Path, help="Reference PCM16 mono 16 kHz WAV"
        )
        parser.add_argument("--target", required=True, type=Path, help="Target PCM16 mono 16 kHz WAV")
        parser.add_argument("--cues", required=True, type=Path, help="Checked reference cue JSON")
        parser.add_argument("--output", required=True, type=Path, help="New output directory")
        parser.add_argument("--band-seconds", type=float, default=0.5)
        parser.add_argument("--spectral-weight", type=float, default=0.15)
        parser.add_argument("--max-frames", type=int, default=3000)
        parser.add_argument("--max-cells", type=int, default=2_000_000)
        args = parser.parse_args(argv)
        try:
            manifest = align(
                args.reference,
                args.target,
                args.cues,
                args.output,
                Config(
                    band_seconds=args.band_seconds,
                    spectral_weight=args.spectral_weight,
                    max_frames=args.max_frames,
                    max_cells=args.max_cells,
                ),
            )
        except (OSError, ValueError, wave.Error, EOFError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(json.dumps(manifest["metrics"], indent=2))
        return 0
    ```
- **Invocation Wiring**:
  - `src/subtitle_workbench/__main__.py` (lines 1-4):
    ```python
    from .cli import main

    raise SystemExit(main())
    ```
  - `pyproject.toml` (lines 21-22):
    ```toml
    [project.scripts]
    subtitle-workbench = "subtitle_workbench.cli:main"
    ```
- **CLI Tests in Existing Suite**:
  - `tests/test_integration.py` (lines 45-69, 71-93, 108-130):
    - Tests invoke `python -m subtitle_workbench --reference ... --target ... --cues ... --output ...`.
    - `test_cli_full_run_and_rejected_overwrite`: verifies return code 0 on initial execution, prints metrics JSON to stdout, and return code 2 with `"already exist" in rejected.stderr` on rejected overwrite.
    - `test_malformed_json_produces_cli_error_without_output`: verifies return code 2 and `"error:" in completed.stderr`.
    - `test_excessively_nested_json_is_a_clear_cli_error`: verifies return code 2, `"nesting exceeds" in completed.stderr`, and `assert "Traceback" not in completed.stderr`.

### 1.2 Smoke Wheel Script Analysis (`scripts/smoke_wheel.py`)
- **Direct Invocation of CLI `main()`**:
  - Lines 58-62:
    ```python
    generate(root / "input")
    exit_code = main(
        [
            "--reference",
            str(root / "input/reference.wav"),
            "--target",
            str(root / "input/target.wav"),
            "--cues",
            str(root / "input/cues.json"),
            "--output",
            str(root / "output"),
        ]
    )
    assert exit_code == 0
    ```
  - `scripts/smoke_wheel.py` directly passes `argv` with root flags (`--reference`, `--target`, `--cues`, `--output`) into `subtitle_workbench.cli.main()`.
- **Offline Network Guard**:
  - Lines 48-51 monkeypatch `socket.socket` and `socket.create_connection` to raise `RuntimeError('Network access is forbidden during installed-wheel smoke')`.
- **Prerequisite Boundary Condition**:
  - `src/subtitle_workbench/demo.py` (lines 28-30):
    ```python
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("demo directory must be empty")
    ```
  - Verbatim execution test: When `scripts/smoke_wheel.py` was executed pointing `--output` to an existing non-empty directory (`dist/smoke_out`), it raised `ValueError: demo directory must be empty`. When executed with a clean non-existent path (`dist/smoke_out_fresh`), it completed with exit code 0:
    ```
    {
      "reference_duration_seconds": 6.5,
      "target_duration_seconds": 7.26,
      "reference_frames": 325,
      "target_frames": 363,
      "evaluated_cells": 15691,
      "path_length": 398,
      "mean_path_cost": 0.002988199899910483,
      "cue_count": 6,
      "alignment_elapsed_seconds": 0.11711710000236053,
      "alignment_rtf": 0.016131831956248007
    }
    {
      "installed_package": "C:\\Users\\...\\site-packages\\subtitle_workbench\\__init__.py",
      "network_guard": "passed",
      "max_absolute_error_ms": 18.400000000000194
    }
    {
      "wheel": "local_subtitle_workbench-0.1.0-py3-none-any.whl",
      "python": "3.12.10"
    }
    ```

### 1.3 Quality Gate Baseline Verification
- **Test Suite**:
  - Command: `uv run --locked pytest`
  - Result: 446 passed, 1 skipped in 4.33s.
  - Skipped test: `tests/test_asr.py:1129` (skipped because `faster-whisper` is an optional dependency not installed in offline CPU base environment).
- **Linter**:
  - Command: `uv run --locked ruff check .`
  - Result: `All checks passed!` (0 errors).
- **Formatter**:
  - Command: `uv run --locked ruff format --check .`
  - Result: `210 files already formatted` (0 diffs).
- **Wheel Package Build**:
  - Command: `uv run --locked python -m build --wheel --no-isolation`
  - Result: Exit code 0, generated `dist/local_subtitle_workbench-0.1.0-py3-none-any.whl`.

### 1.4 Documentation Requirements & Templates
- `docs/increments/TEMPLATE_INCREMENT_REPORT.md` (lines 1-91):
  - Requires:
    1. Executive Summary & Objective
    2. Traceability to Individual Plan & Quality Gates (Gates 1-5)
    3. Detailed Inventory of Changes (Created files, Modified files, Dependencies & Build)
    4. Verification Evidence & Quality Gate Results (pytest, ruff check, ruff format, wheel build & smoke_wheel)
    5. Architectural & Design Decisions Made
    6. Edge Cases, Failure Modes & Boundary Conditions Tested
    7. Handover & Prerequisites
- Prior Increment 4 Report: `docs/increments/INCREMENT_4_FORCED_ALIGNMENT.md` (166 lines) serves as reference implementation for level of detail, decision documentation, and edge case catalog.
- `ORIGINAL_REQUEST.md` (section `## 2026-10-26T00:58:19Z`, lines 250-254):
  - Mandatory git branch: `feature/increment-5-exporters-and-pipeline`.
  - Required 3 atomic commits:
    1. `feat(export): implement WebVTT karaoke, schema.org JSON-LD, raw alignment, and manifest exporters`
    2. `feat(pipeline): wire end-to-end speech alignment pipeline and CLI subcommands`
    3. `docs(sdlc): formalize Increment 5 verification report and audit logs`
  - Target documentation path: `docs/increments/INCREMENT_5_EXPORTERS_AND_PIPELINE.md`.

---

## 2. Logic Chain

### 2.1 CLI Architecture & Backward Compatibility Resolution
1. **Observation 1.1** demonstrates that `scripts/smoke_wheel.py` and `tests/test_integration.py` invoke `main(['--reference', ...])` with root flags.
2. In standard Python `argparse`, if root-level options have `required=True`, invoking a subcommand (`align-speech` or `align-dtw`) will fail because the parser expects the root required options.
3. Conversely, if `add_subparsers()` is marked `required=True`, passing root flags without a subcommand will fail with an unrecognized argument or missing subcommand error.
4. **Tested Solution**: Configure root parser with optional flags (`--reference`, `--target`, `--cues`, `-o / --output`, `--band-seconds`, `--spectral-weight`, `--max-frames`, `--max-cells`) and optional subparsers (`subparsers = parser.add_subparsers(dest="subcommand")`).
   - If `args.subcommand == "align-speech"`: dispatch to `run_speech_pipeline(audio_path=args.audio_wav, output_dir=args.output, transcript=args.transcript, engine=args.engine)`.
   - If `args.subcommand == "align-dtw"`: dispatch to `align(reference_path=args.ref_wav, target_path=args.target_wav, cues_path=args.cues_json, output_dir=args.output, config=Config(...))`.
   - If `args.subcommand is None`: check that all 4 root flags (`--reference`, `--target`, `--cues`, `--output`) were supplied. If any are missing, print descriptive message to `sys.stderr` and return exit code 2. If all 4 are present, dispatch to `align(...)`.
5. **Exit Code & Traceback Contract**:
   - `argparse.ArgumentParser.error()` prints to `sys.stderr` and exits with code 2.
   - Wrapping argument parsing and pipeline execution inside `try / except` blocks catching `(OSError, ValueError, wave.Error, EOFError, ASRError, ChunkingError, MonotonicityError, MFAError, CTCAlignerError)` ensures all contract and validation failures print `error: <message>` to `sys.stderr` and return code 2 without printing Python stack traces, satisfying `test_excessively_nested_json_is_a_clear_cli_error` and R3.
   - Catching `SystemExit` around `parser.parse_args(argv)` guarantees that calling `main(argv)` as a function from Python (as done in `scripts/smoke_wheel.py`) returns an integer status code (0 or 2) instead of propagating an unhandled `SystemExit` exception.

### 2.2 Subcommand Option Specifications
- Subcommand `align-speech`:
  - `audio_wav`: `Path`, positional required.
  - `-o`, `--output`: `Path`, option required.
  - `--engine`: `str`, choices: `["auto", "mfa", "ctc"]`, default: `"auto"`.
  - `--transcript`: `str | None`, default: `None` (accepts inline text or text file path).
  - Optional tuning knobs (with defaults matching `run_speech_pipeline`):
    - `--vad-silence-min-sec`: `float`, default: `0.4`.
    - `--max-chunk-sec`: `float`, default: `30.0`.
    - `--chunk-padding-sec`: `float`, default: `0.5`.
- Subcommand `align-dtw`:
  - `ref_wav`: `Path`, positional required.
  - `target_wav`: `Path`, positional required.
  - `cues_json`: `Path`, positional required.
  - `-o`, `--output`: `Path`, option required.
  - `--band-seconds`: `float`, default: `0.5`.
  - `--spectral-weight`: `float`, default: `0.15`.
  - `--max-frames`: `int`, default: `3000`.
  - `--max-cells`: `int`, default: `2_000_000`.
- Root flags (Legacy DTW mode):
  - `--reference`: `Path`, optional on parser, validated required when `subcommand is None`.
  - `--target`: `Path`, optional on parser, validated required when `subcommand is None`.
  - `--cues`: `Path`, optional on parser, validated required when `subcommand is None`.
  - `-o`, `--output`: `Path`, optional on parser, validated required when `subcommand is None`.
  - `--band-seconds`: `float`, default: `0.5`.
  - `--spectral-weight`: `float`, default: `0.15`.
  - `--max-frames`: `int`, default: `3000`.
  - `--max-cells`: `int`, default: `2_000_000`.

### 2.3 Smoke Script Invariant & CI Cleanliness
1. `scripts/smoke_wheel.py` invokes `demo.generate(root / 'input')`.
2. `demo.generate()` enforces that the output directory does not exist or is completely empty (`if output.exists() and any(output.iterdir()): raise ValueError("demo directory must be empty")`).
3. If an automated script or developer runs `python scripts/smoke_wheel.py --wheel ... --output dist/smoke_out` repeatedly without deleting `dist/smoke_out` first, the run will fail with `ValueError`.
4. Therefore, verification scripts must either target a unique temporary directory or ensure `dist/smoke_out` is cleaned before invoking `scripts/smoke_wheel.py`.

---

## 3. Caveats

1. **Host Environment Dependencies**: `faster-whisper` and `torchaudio` are optional dependencies not installed in the CPU test environment; all unit and integration tests for speech alignment pipelines must use mock/stub transcribers and mock aligners to ensure offline execution in under 5 seconds.
2. **Transcript Parameter Handling**: The `--transcript` option can be an inline string (e.g. `"hello world"`) or a path to a file (e.g. `"transcripts/lecture.txt"`). The pipeline should detect if `Path(transcript).is_file()`, read the text from disk if so, or use the string directly. If a path is explicitly provided but the file is missing, it must raise a descriptive `FileNotFoundError` (exit code 2).
3. **Smoke Test Directory State**: `dist/smoke_out` was left from prior runs. When verifying the wheel smoke test during Increment 5 quality gates, the implementer must ensure the output folder is deleted prior to running `smoke_wheel.py`.

---

## 4. Conclusion

1. **CLI Implementation Strategy**: `src/subtitle_workbench/cli.py` can cleanly support both modern subcommands (`align-speech`, `align-dtw`) and root-level legacy flags (`--reference`, `--target`, `--cues`, `--output`) using an `ArgumentParser` with `dest="subcommand"` subparsers alongside top-level options. When `subcommand is None`, top-level flags are validated; if missing, exit code 2 is returned with a descriptive error message to `stderr`.
2. **Exit Code and Output Consistency**:
   - Exit code 0: prints JSON summary metrics to `stdout`.
   - Exit code 2: catches all domain and I/O exceptions, prints `error: <message>` to `stderr`, and produces no tracebacks.
3. **Full Quality Gate Readiness**: Baseline environment is verified: 446 tests passing (1 skipped), 0 ruff errors, 0 format diffs, clean wheel build.
4. **Three Atomic Commits Defined**:
   - Commit 1: `feat(export): implement WebVTT karaoke, schema.org JSON-LD, raw alignment, and manifest exporters`
   - Commit 2: `feat(pipeline): wire end-to-end speech alignment pipeline and CLI subcommands`
   - Commit 3: `docs(sdlc): formalize Increment 5 verification report and audit logs`
5. **Documentation Path**: `docs/increments/INCREMENT_5_EXPORTERS_AND_PIPELINE.md` follows `TEMPLATE_INCREMENT_REPORT.md` and `INCREMENT_4_FORCED_ALIGNMENT.md`.

---

## 5. Verification Method

### 5.1 CLI Functional Verification Commands
1. **Legacy DTW Mode via Root Flags**:
   ```powershell
   uv run python -m subtitle_workbench --reference tests/fixtures/ref.wav --target tests/fixtures/tgt.wav --cues tests/fixtures/cues.json --output dist/test_cli_legacy
   ```
   *Expected*: Exit code 0, metrics JSON printed to stdout.
2. **DTW Subcommand Mode**:
   ```powershell
   uv run python -m subtitle_workbench align-dtw tests/fixtures/ref.wav tests/fixtures/tgt.wav tests/fixtures/cues.json -o dist/test_cli_dtw
   ```
   *Expected*: Exit code 0, metrics JSON printed to stdout.
3. **Speech Subcommand Mode**:
   ```powershell
   uv run python -m subtitle_workbench align-speech tests/fixtures/speech.wav -o dist/test_cli_speech --engine ctc --transcript "sample text"
   ```
   *Expected*: Exit code 0 on valid run; exit code 2 on invalid audio or file collision.
4. **Error Handling & Negative Testing**:
   ```powershell
   uv run python -m subtitle_workbench
   ```
   *Expected*: Exit code 2, error message on stderr, no traceback.
   ```powershell
   uv run python -m subtitle_workbench align-speech missing.wav -o dist/test_out
   ```
   *Expected*: Exit code 2, error message on stderr indicating missing file.

### 5.2 Quality Gate Commands
```powershell
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m build --wheel --no-isolation
pwsh -Command "if (Test-Path dist/smoke_out) { Remove-Item -Recurse -Force dist/smoke_out }"
uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out
```

### 5.3 Invalidation Conditions
- If `scripts/smoke_wheel.py` fails due to `subtitle_workbench.cli.main` rejecting root flags `--reference`, `--target`, `--cues`, `--output`.
- If `pytest` has any failures or regression below 446 passing tests.
- If running invalid CLI commands outputs a Python Traceback to stderr instead of `error: <message>` with exit code 2.
