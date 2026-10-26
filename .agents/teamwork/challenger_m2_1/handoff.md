# Adversarial Challenge Report: Speech Benchmark Runner CLI, Memory Profiling Fallbacks, and Exit Codes

**Agent:** challenger_m2_1  
**Role:** EMPIRICAL CHALLENGER (critic, specialist)  
**Parent Orchestrator:** d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\challenger_m2_1`  
**Target Branch:** `feature/increment-6-speech-benchmark`  
**Date:** 2026-10-26T04:41:00Z  
**Handoff Type:** Hard  
**Verdict:** REQUEST_CHANGES  
**Discipline:** Pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |). Zero Unicode emojis or graphical icons.

---

## Challenge Summary

**Overall risk assessment**: MEDIUM

Empirical stress testing of `scripts/speech_benchmark.py` revealed that while the core benchmark execution, offline synthetic generator, and statistical analysis functions are robust, there are two distinct failure modes regarding error handling and exit codes:

1. **Exit Code Contract Divergence on Runtime Exceptions:**
   In `scripts/speech_benchmark.py:964-969`, `except BenchmarkError` returns `1`, but `except Exception as err` returns `2`. Standard CLI conventions and task mandates dictate that argparse / syntax errors must exit with code `2`, whereas runtime execution errors must exit with code `1`. When an unexpected runtime exception occurs (e.g. invalid negative seed `--seed -1` triggering `ValueError: expected non-negative integer`, or filesystem collisions such as `--output-dir` targeting an existing file), the CLI exits with code `2` rather than `1`.
2. **Missing Seed Validation in CLI / Runner:**
   Negative seeds (e.g. `--seed -1`) are accepted by `argparse` as valid integers, and `run_benchmark()` does not validate `seed >= 0` before passing it to `np.random.default_rng(seed)`. This causes an unhandled raw `ValueError` to propagate and exit with code `2` instead of a domain `BenchmarkError` exiting with code `1`.
3. **Fragile Exception Catching in `psutil` Memory Profiling Tier:**
   In `scripts/speech_benchmark.py:164-169`, `get_peak_host_ram_mb()` wraps `import psutil` and `psutil.Process().memory_info()` in `try ... except ImportError: pass`. If `psutil` is installed but `Process().memory_info()` throws any runtime exception (e.g. `psutil.AccessDenied`, `psutil.NoSuchProcess`, `PermissionError`), the exception crashes the benchmark instead of cleanly falling back to Tier 2 (Windows native `ctypes` `GetProcessMemoryInfo`).

---

## 1. Observation

### 1.1 CLI Argument Stress Testing

1. **Invalid Corpus Names:**
   - Command:
     ```powershell
     uv run python scripts/speech_benchmark.py --corpus invalid_name
     ```
     Result: Exit code `2`. Argparse rejected with:
     ```
     usage: speech_benchmark.py [-h] [--corpus {timit,buckeye,synthetic}] ...
     speech_benchmark.py: error: argument --corpus: invalid choice: 'invalid_name' (choose from timit, buckeye, synthetic)
     ```
   - Programmatic invocation:
     ```python
     run_benchmark(corpus="invalid_name")
     ```
     Result: Raised `BenchmarkError("Unsupported corpus: invalid_name")`. In `main()`, caught by `except BenchmarkError:` and returned exit code `1`.

2. **Non-existent Directories:**
   - Command:
     ```powershell
     uv run python scripts/speech_benchmark.py --data-dir non_existent_corpus_dir
     ```
     Result: Exit code `1`. Output:
     ```
     [-] Benchmark Error: Corpus directory not found: non_existent_corpus_dir. Use --offline-synthetic for offline benchmarking without external datasets.
     ```
   - Command with `--offline-synthetic`:
     ```powershell
     uv run python scripts/speech_benchmark.py --offline-synthetic --data-dir non_existent_corpus_dir --output-dir dist/test_fallback
     ```
     Result: Exit code `0`. Gracefully detected missing `.wrd` files and staged temporary synthetic benchmark (`bench_synth_*`).
   - Command with `--output-dir` colliding with an existing regular file:
     ```powershell
     uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/existing_file.txt
     ```
     Result: Exit code `2`. Output:
     ```
     [-] Unexpected Error: [WinError 183] Cannot create a file when that file already exists: 'dist\\existing_file.txt'
     ```

3. **Invalid Modes:**
   - Command with unknown mode:
     ```powershell
     uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_bad_mode --modes invalid_mode
     ```
     Result: Exit code `1`. Output:
     ```
     [-] Benchmark Error: Unsupported ablation mode: invalid_mode
     ```
   - Command with mixed valid and invalid modes:
     ```powershell
     uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_mixed_mode --modes "mode1_whisper,invalid_mode"
     ```
     Result: Exit code `1`. `mode1_whisper` ran, then `invalid_mode` triggered `BenchmarkError`.
   - Command with empty string mode (`--modes ""`):
     ```powershell
     uv run python scripts/speech_benchmark.py --offline-synthetic --modes ""
     ```
     Result: Exit code `0`. Evaluated as falsy, defaulted to all 3 modes.

4. **Zero and Negative Bootstrap Resamples:**
   - Command with zero resamples:
     ```powershell
     uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_zero_resamples --bootstrap-resamples 0
     ```
     Result: Exit code `1`. Output:
     ```
     [-] Benchmark Error: num_resamples must be positive
     ```
   - Command with negative resamples:
     ```powershell
     uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_neg_resamples --bootstrap-resamples -5
     ```
     Result: Exit code `1`. Output:
     ```
     [-] Benchmark Error: num_resamples must be positive
     ```
   - Command with non-integer resamples:
     ```powershell
     uv run python scripts/speech_benchmark.py --bootstrap-resamples abc
     ```
     Result: Exit code `2`. Argparse rejected with `invalid int value: 'abc'`.

5. **Extreme Seeds:**
   - Command with seed `0`:
     ```powershell
     uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_seed_zero --seed 0
     ```
     Result: Exit code `0`. Output completed cleanly.
   - Command with maximum uint64 seed `9223372036854775807` ($2^{63}-1$):
     ```powershell
     uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_seed_large --seed 9223372036854775807
     ```
     Result: Exit code `0`. Output completed cleanly.
   - Command with negative seed `-1`:
     ```powershell
     uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_neg_seed --seed -1
     ```
     Result: Exit code `2`. Output:
     ```
     [-] Unexpected Error: expected non-negative integer
     ```
     Notice: This is a runtime error, yet it exited with code `2` instead of `1`.

### 1.2 Memory Profiling Fallback Stress Testing

1. **Baseline Environment (psutil uninstalled):**
   - Command:
     ```python
     import psutil
     ```
     Result: `ModuleNotFoundError: No module named 'psutil'`.
   - Command:
     ```python
     from scripts.speech_benchmark import get_peak_host_ram_mb, _get_peak_ram_windows

     print("win:", _get_peak_ram_windows())
     print("host:", get_peak_host_ram_mb())
     ```
     Result:
     `win: 31.29296875` MB, `host: 31.296875` MB.
     Windows ctypes `GetProcessMemoryInfo` (PeakWorkingSetSize) executed cleanly without crashing.

2. **psutil Mocked as None (`sys.modules['psutil'] = None`):**
   - Command:
     ```python
     import sys

     sys.modules["psutil"] = None
     from scripts.speech_benchmark import get_peak_host_ram_mb

     print(get_peak_host_ram_mb())
     ```
     Result: Returns `31.21` MB (> 0.0) via Tier 2 ctypes fallback.

3. **psutil Present with Runtime Error (Fragility Finding):**
   - Command:
     ```python
     import sys
     from unittest.mock import MagicMock

     mock = MagicMock()
     mock.Process.side_effect = RuntimeError("psutil failure")
     sys.modules["psutil"] = mock
     from scripts.speech_benchmark import get_peak_host_ram_mb

     get_peak_host_ram_mb()
     ```
     Result: Crashed with `RuntimeError: psutil failure`.
     Observation: In `scripts/speech_benchmark.py:164-169`:
     ```python
     try:
         import psutil

         return float(psutil.Process().memory_info().rss / (1024 * 1024))
     except ImportError:
         pass
     ```
     Because only `ImportError` is caught, any runtime exception during `Process().memory_info()` halts execution rather than proceeding to Tier 2 Windows ctypes.

4. **Multi-tier Fallback with Windows and POSIX Mocked to None:**
   - Command with active tracemalloc:
     ```python
     import sys, tracemalloc
     from unittest.mock import patch

     tracemalloc.start()
     with patch("scripts.speech_benchmark._get_peak_ram_windows", return_value=None):
         from scripts.speech_benchmark import get_peak_host_ram_mb

         print(get_peak_host_ram_mb())
     tracemalloc.stop()
     ```
     Result: Returns `14.18` MB.
   - Command with inactive tracemalloc:
     Result: Returns `0.0` MB without crashing.
   - Entire benchmark run with mocked fallbacks returning `0.0`:
     Result: Successfully completed 100% of benchmark execution and generated valid `benchmark_results.json` and `manifest.json`.

---

## 2. Logic Chain

1. **Exit Code Contract:**
   - Standard Unix / POSIX conventions and Task Requirement 3 require:
     * Exit code `2`: CLI argument syntax errors (handled by `argparse.ArgumentParser.error()`).
     * Exit code `1`: Runtime execution errors.
   - In `scripts/speech_benchmark.py`:
     ```python
     def main(argv: list[str] | None = None) -> int:
         args = parse_args(argv)
         ...
         try:
             run_benchmark(...)
             return 0
         except BenchmarkError as err:
             print(f"[-] Benchmark Error: {err}", file=sys.stderr)
             return 1
         except Exception as err:
             print(f"[-] Unexpected Error: {err}", file=sys.stderr)
             return 2
     ```
   - When an unhandled runtime exception occurs (such as `ValueError` from `--seed -1`, or `FileExistsError` on `--output-dir`), it is caught by `except Exception as err:` and returns `2`.
   - Consequently, calling scripts and CI pipelines cannot distinguish between CLI argument syntax errors (code 2) and runtime failures (code 2).

2. **Negative Seed Validation:**
   - Argument `--seed` has `type=int`. Argparse permits any integer, including `-1`.
   - `run_benchmark()` does not validate `seed >= 0`.
   - Passing `seed = -1` to `np.random.default_rng(seed)` raises `ValueError: expected non-negative integer`.
   - Because `ValueError` does not inherit from `BenchmarkError`, it triggers the `except Exception` branch and exits with code `2`.
   - Defensively validating `if seed < 0: raise BenchmarkError(f"Random seed must be non-negative, got {seed}")` would enforce clean domain error handling and return exit code `1`.
   - Furthermore, setting `except Exception as err: ... return 1` ensures that all runtime exceptions consistently exit with code `1`.

3. **psutil Robustness:**
   - In environments where `psutil` is installed but process inspection is restricted (e.g., container sandbox, access denied, or virtualized environments), `psutil.Process().memory_info()` can raise exceptions such as `psutil.AccessDenied`.
   - Catching only `ImportError` leaves Tier 1 vulnerable to runtime crashes.
   - Changing line 168 to `except (ImportError, Exception):` ensures the multi-tier fallback functions as designed under all execution environments.

---

## 3. Caveats

1. On Windows 11 with no `psutil` installed, Tier 2 (`_get_peak_ram_windows`) executes by default and functions flawlessly, returning accurate resident memory (~31 MB).
2. The seed vulnerability only manifests when negative integers are explicitly passed to `--seed`. Normal non-negative seeds (including `0` and very large values up to $2^{63}-1$) operate correctly.
3. No other caveats.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

`scripts/speech_benchmark.py` is structurally solid and functionally capable, but requires the following surgical fixes to ensure full compliance with the project's error handling and exit code contracts:

1. **Fix `main()` Exit Code Handling:**
   In `scripts/speech_benchmark.py:967-969`, update the generic `except Exception as err:` block to return exit code `1` (not `2`), ensuring that all runtime exceptions are distinguished from argparse syntax errors (which exit `2`):
   ```python
   except Exception as err:
       print(f"[-] Unexpected Error: {err}", file=sys.stderr)
       return 1
   ```
2. **Defensively Validate Random Seed:**
   In `run_benchmark()` (or in `parse_args`), add defensive validation for `seed`:
   ```python
   if seed < 0:
       raise BenchmarkError(f"Random seed must be non-negative, got {seed}")
   ```
3. **Broaden Exception Catching in psutil Memory Profiling:**
   In `scripts/speech_benchmark.py:168`, update `except ImportError:` to:
   ```python
   except (ImportError, Exception):
       pass
   ```
   so that runtime failures in `psutil` gracefully trigger Tier 2 Windows ctypes fallback.

---

## 5. Verification Method

To independently verify these findings:

1. **Verify Exit Code on Negative Seed:**
   ```powershell
   uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_neg_seed --seed -1; $LASTEXITCODE
   ```
   *Current behavior*: Exits with code `2`, printing `[-] Unexpected Error: expected non-negative integer`.  
   *Expected behavior*: Should exit with code `1` and clean domain message `[-] Benchmark Error: Random seed must be non-negative`.

2. **Verify Exit Code on Argparse Syntax Error:**
   ```powershell
   uv run python scripts/speech_benchmark.py --corpus invalid_choice; $LASTEXITCODE
   ```
   *Expected behavior*: Exits with code `2`, printing standard argparse usage and choice error.

3. **Verify psutil Runtime Fallback:**
   ```powershell
   uv run python -c "import sys; from unittest.mock import MagicMock; mock = MagicMock(); mock.Process.side_effect = RuntimeError('psutil failure'); sys.modules['psutil'] = mock; from scripts.speech_benchmark import get_peak_host_ram_mb; print(get_peak_host_ram_mb())"
   ```
   *Current behavior*: Crashes with uncaught `RuntimeError: psutil failure`.  
   *Expected behavior*: Should catch the error and return Windows ctypes RAM (> 0.0 MB).

4. **Verify Exit Code on BenchmarkError:**
   ```powershell
   uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_bad_mode --modes invalid_mode; $LASTEXITCODE
   ```
   *Expected behavior*: Exits with code `1`, printing `[-] Benchmark Error: Unsupported ablation mode: invalid_mode`.

### Invalidation Conditions
- If unexpected runtime exceptions are intentionally specified to exit with code 2 in this project's architecture.
- If `seed < 0` is considered an invalid argument that should be rejected by argparse directly.
