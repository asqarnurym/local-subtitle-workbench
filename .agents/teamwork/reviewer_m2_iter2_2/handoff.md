# Quality & Adversarial Review Report: Milestone 2 Iteration 2 (Commit a87fe08)

**Agent:** reviewer_m2_iter2_2  
**Roles:** reviewer, critic  
**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\reviewer_m2_iter2_2`  
**Parent Orchestrator:** d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Target Commit:** `a87fe08` (`feat(benchmark): implement clustered bootstrap, paired Wilcoxon tests, and benchmark runner`)  
**Verdict:** APPROVE  
**Date:** 2026-10-26T04:57:30Z  
**Discipline:** Pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |). Zero Unicode emojis or graphical icons.

---

## 1. Observation

1. **PSUtil Exception Fallback in Memory Profiler (`scripts/speech_benchmark.py:156-180`):**
   - In `get_peak_host_ram_mb()`, lines 164-169:
     ```python
     try:
         import psutil

         return float(psutil.Process().memory_info().rss / (1024 * 1024))
     except Exception:
         pass
     ```
   - The handler was updated from `except ImportError:` to `except Exception:`, ensuring that any runtime error (e.g. `AccessDenied`, `NoSuchProcess`, `RuntimeError`) during `psutil.Process().memory_info()` is cleanly bypassed.
   - Execution falls back through Tier 2 Windows ctypes (`_get_peak_ram_windows()`), Tier 3 POSIX (`_get_peak_ram_posix()`), and Tier 4 tracemalloc (`_get_peak_ram_tracemalloc()`), guaranteeing a valid non-negative float return value.

2. **Argument Validation in `run_benchmark()` (`scripts/speech_benchmark.py:543-547`):**
   - Lines 543-546:
     ```python
     if seed < 0:
         raise BenchmarkError(f"Random seed must be non-negative, got {seed}")
     if bootstrap_resamples < 1:
         raise BenchmarkError(f"bootstrap_resamples must be >= 1, got {bootstrap_resamples}")
     ```
   - Defensive validation enforces `seed >= 0` and `bootstrap_resamples >= 1`, rejecting negative seeds and invalid resample counts with domain-specific `BenchmarkError`.

3. **CLI Exit Code Discipline in `main()` (`scripts/speech_benchmark.py:987-1010`):**
   - `args = parse_args(argv)` is executed before the runtime `try...except` block. Argparse syntax errors (unknown flags, missing values, invalid choice) raise `SystemExit` with exit code 2.
   - Runtime execution in `main()` is wrapped in `try...except`:
     ```python
     try:
         run_benchmark(...)
         return 0
     except BenchmarkError as err:
         sys.stderr.write(f"[-] Benchmark Error: {err}\n")
         return 1
     except (ValueError, Exception) as err:
         sys.stderr.write(f"error: {err}\n")
         return 1
     ```
   - Exit code 1 is strictly returned for domain/runtime exceptions, while exit code 2 remains strictly reserved for CLI argument parsing errors.
   - Independent verification command execution confirmed:
     * `uv run python scripts/speech_benchmark.py --offline-synthetic --seed -1` -> returned `ExitCode: 1`
     * `uv run python scripts/speech_benchmark.py --corpus invalid_choice` -> returned `ExitCode: 2`

4. **Automated Unit & Integration Tests in `tests/test_benchmark.py`:**
   - Lines 1046-1064: `test_speech_benchmark_cli_seed_negative_exits_one` verifies CLI invocation with `--seed -1` exits with returncode 1, emits `[-] Benchmark Error`, and matches `non-negative`.
   - Lines 1066-1076: `test_speech_benchmark_negative_seed_validation` tests `run_benchmark(..., seed=-1)` raises `BenchmarkError`.
   - Lines 1078-1088: `test_speech_benchmark_invalid_resamples_validation` tests `run_benchmark(..., bootstrap_resamples=0)` raises `BenchmarkError`.
   - Lines 1090-1105: `test_get_peak_host_ram_mb_psutil_exception_fallback` mocks `psutil.Process.side_effect = RuntimeError("AccessDenied simulated failure")` and asserts `get_peak_host_ram_mb()` returns a non-negative float.

5. **Automated Test Suite and Code Quality Runs:**
   - `uv run --locked pytest tests/test_benchmark.py -v`:
     `30 passed in 5.41s` (100% pass rate).
   - `uv run --locked pytest`:
     `677 passed, 1 skipped in 20.10s` (100% pass rate, 0 regressions).
   - `uv run --locked ruff check .`:
     `All checks passed!` (0 errors/warnings).
   - `uv run --locked ruff format --check .`:
     `396 files already formatted` (0 diffs).
   - `uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/benchmark_demo`:
     `[OK] Benchmark execution and artifact generation completed successfully.` (Exit code 0).

6. **Integrity and Anti-Cheating Inspection:**
   - No hardcoded test outputs or mock bypasses in production logic.
   - Real deserialization of `alignment_raw.json` into typed `WordToken` and `PhonemeCue` objects in `_deserialize_raw_alignment()`.
   - No emojis or forbidden Unicode characters present in source code or commit log.

---

## 2. Logic Chain

1. In Observation 1, broadening the exception handler in `get_peak_host_ram_mb()` to `except Exception:` prevents unexpected psutil failures (such as process permission or OS access denial) from halting benchmark execution.
2. In Observation 2, explicit boundary checks on `seed` and `bootstrap_resamples` eliminate invalid states prior to allocating RNG state or executing expensive resampling loops.
3. In Observation 3, placing `parse_args()` outside the runtime try block and catching all runtime exceptions in `main()` to return 1 guarantees POSIX/CLI convention alignment (exit code 2 for CLI syntax errors, exit code 1 for runtime failures).
4. In Observations 4 and 5, unit tests and regression test suites independently verify all happy paths, boundary violations, fallback behaviors, and CLI exit codes with a 100% pass rate.
5. In Observation 6, audit checks confirmed no facade implementations, dummy results, or integrity violations exist.
6. Therefore, the implementation in commit `a87fe08` is verified, robust, and approved.

---

## 3. Caveats

1. The test environment operates on Windows 11 with CPU/synthetic offline mock fixtures (executing in < 6 seconds per R5). Real CUDA model inference on GPU requires the optional `speech` extra (`faster-whisper`, `torch`), which is skipped gracefully in environments without GPU weights.
2. No caveats.

---

## 4. Conclusion

- **Verdict:** APPROVE
- All five required verification targets for Milestone 2 Iteration 2 are fully satisfied:
  1. `get_peak_host_ram_mb()` catches `except Exception:` on psutil and falls back cleanly.
  2. Argument validation for `seed >= 0` and `bootstrap_resamples >= 1` in `run_benchmark()` is enforced.
  3. `main()` catches runtime exceptions returning exit code 1 while reserving exit code 2 for argparse errors.
  4. Unit and CLI integration tests cover negative seeds, invalid resamples, and psutil exception fallback.
  5. All verification commands (`pytest tests/test_benchmark.py`, full `pytest`, `ruff check`, `ruff format`) pass with zero errors.

---

## 5. Verification Method

To independently reproduce and verify this review:

1. **Run benchmark test suite with verbose reporting:**
   ```powershell
   uv run --locked pytest tests/test_benchmark.py -v
   ```
   *Expected outcome*: 30 passed in < 6 seconds.

2. **Run full project regression test suite:**
   ```powershell
   uv run --locked pytest
   ```
   *Expected outcome*: 677 passed, 1 skipped in ~20 seconds.

3. **Verify CLI exit codes for runtime validation vs argparse syntax:**
   ```powershell
   uv run python scripts/speech_benchmark.py --offline-synthetic --seed -1
   Write-Host "ExitCode:" $LASTEXITCODE
   # Expected: ExitCode: 1

   uv run python scripts/speech_benchmark.py --corpus invalid_choice
   Write-Host "ExitCode:" $LASTEXITCODE
   # Expected: ExitCode: 2
   ```

4. **Verify code quality:**
   ```powershell
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   *Expected outcome*: Zero errors, zero formatting diffs.

5. **Verify git commit `a87fe08`:**
   ```powershell
   git show a87fe08 --stat
   ```

### Invalidation Conditions
- Any test failure in `tests/test_benchmark.py`.
- Any unhandled exception or non-1 exit code on invalid runtime parameters.
- Any regression in the repository test suite.
