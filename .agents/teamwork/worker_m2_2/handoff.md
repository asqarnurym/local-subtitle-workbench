# Handoff Report: Milestone 2 Iteration 2 Implementation

**Agent:** worker_m2_2  
**Role:** implementer, qa, specialist  
**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m2_2`  
**Parent Orchestrator:** d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Target Branch:** `feature/increment-6-speech-benchmark`  
**Date:** 2026-10-26T04:53:00Z  
**Handoff Type:** Hard  
**Discipline:** Pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |). Zero Unicode emojis or graphical icons.

---

## 1. Observation

1. **Reviewer and Challenger Findings:**
   - `reviewer_m2_1/handoff.md:25-59`: Identified Critical Finding 1 in `scripts/speech_benchmark.py`: `run_speech_pipeline()` returns execution manifest dictionary (without `"words"` key), while actual alignments are exported to `alignment_raw.json`. `pred_words = res_pipe.get("words", [])` silently returned `[]` in production mode.
   - `reviewer_m2_1/handoff.md:61-74`: Identified Major Finding 2: production execution branch lacked unit/integration test coverage.
   - `reviewer_m2_1/handoff.md:68-74`: Identified Minor Finding 3: `device="auto"` should resolve to `device=None` for `WhisperTranscriber` to trigger auto device selection.
   - `challenger_m2_1/handoff.md:21-27`: Identified exit code divergence on runtime exceptions (returning 2 instead of 1), missing negative seed validation, and fragile exception catching on `psutil.Process().memory_info()`.

2. **Code Changes Implemented:**
   - In `scripts/speech_benchmark.py`:
     * Added helper function `_deserialize_raw_alignment(raw_file: Path) -> list[WordToken]` deserializing `WordToken` and nested `PhonemeCue` instances from `alignment_raw.json`.
     * Updated Mode 2 (`mode2_ctc`) and Mode 3 (`mode3_hybrid`) to call `_deserialize_raw_alignment(Path(p_tmp) / "alignment_raw.json")` and extract `pred_words` and `pred_phones`.
     * Updated Mode 1 (`mode1_whisper`) to instantiate `WhisperTranscriber(device=None if device == "auto" else device, compute_type="int8")`.
     * In `get_peak_host_ram_mb()`, changed `except ImportError:` to `except Exception:` on the `psutil` block to ensure any runtime failure falls back cleanly to Tier 2 Windows ctypes.
     * In `run_benchmark()`, added input validation:
       `if seed < 0: raise BenchmarkError(f"Random seed must be non-negative, got {seed}")`
       `if bootstrap_resamples < 1: raise BenchmarkError(f"bootstrap_resamples must be >= 1, got {bootstrap_resamples}")`
     * In `run_benchmark()`, set `is_offline = bool(offline_synthetic)` so that passing `corpus="synthetic", offline_synthetic=False` properly triggers the real production execution path on synthetic utterances.
     * In `main()`, caught `BenchmarkError` (writing `[-] Benchmark Error: {err}\n` to stderr and returning 1) and generic `(ValueError, Exception)` (writing `error: {err}\n` to stderr and returning 1), strictly reserving exit code 2 for argparse syntax errors.

   - In `tests/test_benchmark.py`:
     * Added `test_speech_benchmark_real_production_execution` testing `run_benchmark(corpus="synthetic", offline_synthetic=False, ...)` with monkeypatched `WhisperTranscriber` and `run_speech_pipeline`, verifying word and phoneme extraction from `alignment_raw.json` and error aggregation across all 3 ablation modes.
     * Added `test_speech_benchmark_cli_seed_negative_exits_one` verifying `--seed -1` exits with code 1.
     * Added `test_speech_benchmark_negative_seed_validation` verifying `BenchmarkError` on negative seed.
     * Added `test_speech_benchmark_invalid_resamples_validation` verifying `BenchmarkError` on `bootstrap_resamples < 1`.
     * Added `test_get_peak_host_ram_mb_psutil_exception_fallback` verifying clean fallback when `psutil` raises a runtime exception.

3. **Verification Command Results:**
   - `uv run --locked pytest tests/test_benchmark.py`:
     `30 passed in 5.04s` (100% pass rate).
   - `uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/benchmark_demo`:
     Executed with exit code 0; generated valid `benchmark_results.json` (3,423 bytes) and cryptographic `manifest.json` (1,940 bytes).
   - `uv run --locked pytest`:
     `677 passed, 1 skipped in 19.57s` (100% pass rate across entire repository test suite).
   - `uv run --locked ruff check .`:
     `All checks passed!` (0 warnings/errors).
   - `uv run --locked ruff format --check .`:
     `375 files already formatted` (0 formatting diffs).
   - Commit amended:
     Commit hash `a87fe08`: `feat(benchmark): implement clustered bootstrap, paired Wilcoxon tests, and benchmark runner`.

---

## 2. Logic Chain

1. Observations 1 and 2 establish that the critical contract mismatch between `run_speech_pipeline` and `speech_benchmark.py` has been resolved by loading and parsing `alignment_raw.json` directly into typed `WordToken` and `PhonemeCue` objects.
2. In Observation 2, `is_offline = bool(offline_synthetic)` allows `run_benchmark(corpus="synthetic", offline_synthetic=False)` to exercise the genuine production branch on staged synthetic WAV/WRD/PHN files without requiring external datasets.
3. In Observation 2, `_get_peak_host_ram_mb()` now catches all exceptions on `psutil`, ensuring resilient multi-tier fallback.
4. In Observation 2, argument validation guarantees that negative seeds and non-positive bootstrap resample counts raise domain `BenchmarkError` and exit with code 1, while exit code 2 is strictly reserved for argparse CLI syntax errors.
5. In Observation 3, automated test suite verification confirmed 30/30 passing benchmark tests, full regression pass (677 passed, 1 skipped), zero linter errors, zero format diffs, and successful demo artifact generation.
6. Commit 2 on `feature/increment-6-speech-benchmark` was cleanly amended (`a87fe08`) incorporating all fixes and test additions.

---

## 3. Caveats

1. Real-mode GPU execution on CUDA requires optional `faster-whisper` and `torch` dependencies (`[project.optional-dependencies] speech`). In offline/CPU test environments, mock fixtures and synthetic corpora are used as specified in R5, executing in < 5 seconds.
2. No caveats.

---

## 4. Conclusion

All requirements for Milestone 2 Iteration 2 have been satisfied:
- Production mode `run_speech_pipeline` output deserialization from `alignment_raw.json` implemented and verified.
- Memory profiling fallback catches any runtime failure on `psutil` and falls back cleanly to Windows ctypes.
- CLI argument validation for `--seed >= 0` and `--bootstrap-resamples >= 1` enforced; runtime errors exit with code 1.
- Unit and integration tests added in `tests/test_benchmark.py` exercising the real production pipeline path, CLI exit codes, and memory fallback.
- Test suites (30 benchmark tests, 677 total tests), linters, and formatters pass cleanly.
- Git commit 2 amended on `feature/increment-6-speech-benchmark`.

---

## 5. Verification Method

To independently verify the implementation and acceptance gates:

1. **Run benchmark unit and integration test suite:**
   ```powershell
   uv run --locked pytest tests/test_benchmark.py
   ```
   *Expected result*: 30 passed in < 6 seconds.

2. **Run offline synthetic benchmark demo:**
   ```powershell
   uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/benchmark_demo
   ```
   *Expected result*: Exits with code 0, prints clean ASCII output, and generates `dist/benchmark_demo/benchmark_results.json` and `dist/benchmark_demo/manifest.json`.

3. **Verify CLI exit codes on negative seed and syntax error:**
   ```powershell
   uv run python scripts/speech_benchmark.py --offline-synthetic --seed -1; Write-Host "ExitCode:" $LASTEXITCODE
   uv run python scripts/speech_benchmark.py --corpus invalid_choice; Write-Host "ExitCode:" $LASTEXITCODE
   ```
   *Expected result*: First command exits with code 1 (domain runtime validation). Second command exits with code 2 (argparse syntax error).

4. **Run code quality and formatting checks:**
   ```powershell
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   *Expected result*: 0 warnings, all files formatted.

5. **Run full regression test suite:**
   ```powershell
   uv run --locked pytest
   ```
   *Expected result*: 677 passed, 1 skipped.

6. **Inspect amended git commit:**
   ```powershell
   git log -n 2 --oneline
   ```
   *Expected result*: Shows commit `a87fe08 feat(benchmark): implement clustered bootstrap, paired Wilcoxon tests, and benchmark runner`.

### Invalidation Conditions
- Any test failure in `tests/test_benchmark.py`.
- Any non-zero exit code on `uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/benchmark_demo`.
- Any ruff lint or formatting violation.
