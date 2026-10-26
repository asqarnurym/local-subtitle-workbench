# Forensic Audit Report: Milestone 2 Iteration 2

**Agent:** auditor_m2_iter2_1  
**Role:** critic, specialist, auditor  
**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\auditor_m2_iter2_1`  
**Parent Orchestrator:** d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Target Commit:** `a87fe08` (`feat(benchmark): implement clustered bootstrap, paired Wilcoxon tests, and benchmark runner`)  
**Target Branch:** `feature/increment-6-speech-benchmark`  
**Date:** 2026-10-26T04:58:00Z  
**Verdict:** CLEAN  
**Discipline:** Pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |). Zero Unicode emojis or graphical icons.

---

## Forensic Audit Summary

**Work Product**: Commit `a87fe08` on branch `feature/increment-6-speech-benchmark` (`scripts/speech_benchmark.py`, `tests/test_benchmark.py`)  
**Profile**: General Project (Integrity Mode: development)  
**Verdict**: CLEAN  

### Phase Results
- [Check 1 - Commit Inspection]: PASS -- Commit a87fe08 contains genuine implementations in scripts/speech_benchmark.py (1013 insertions) and tests/test_benchmark.py (505 insertions, 1 deletion).
- [Check 2 - Pure ASCII Scan]: PASS -- 0 non-ASCII bytes found in scripts/speech_benchmark.py (37,886 bytes) and tests/test_benchmark.py (40,624 bytes).
- [Check 3 - Anti-Falsification & Facade Analysis]: PASS -- No hardcoded metrics, no fake return values, no dummy facades, no pre-populated artifacts. Metrics are computed dynamically via evaluate_alignment_boundaries, clustered_bootstrap_ci, and paired_wilcoxon_test.
- [Check 4 - Deserialization Contract Fix]: PASS -- _deserialize_raw_alignment() cleanly reconstructs WordToken and PhonemeCue objects with start, end, confidence from alignment_raw.json.
- [Check 5 - Exception Handling & CLI Exit Codes]: PASS -- Negative seed and non-positive resamples raise BenchmarkError and exit with code 1; argparse syntax errors exit with code 2; get_peak_host_ram_mb() catches any psutil exception and cleanly falls back.
- [Check 6 - Unit & Integration Test Suite]: PASS -- uv run --locked pytest tests/test_benchmark.py passed 30/30 tests in 5.69s.
- [Check 7 - Benchmark Demo Execution]: PASS -- uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_auditor_m2_iter2 exited with code 0 and generated valid benchmark_results.json and manifest.json.
- [Check 8 - Cryptographic Provenance]: PASS -- SHA-256 hash of benchmark_results.json matches manifest.json bit-for-bit (ee52c1a9bbc25656450a2b30ea3f1ef6590744a575e3e0af696457a63bb77ac0).
- [Check 9 - Code Quality & Linters]: PASS -- uv run --locked ruff check . passed with 0 errors; uv run --locked ruff format --check . passed with 396 files formatted.
- [Check 10 - Full Repository Regression]: PASS -- uv run --locked pytest passed 677 tests, 1 skipped in 22.47s.

---

## 1. Observation

1. **Commit Inspection (`git show --stat a87fe08`):**
   - Commit: `a87fe087323b3043d841df2b00d07f77ca1af067`
   - Author: Asqar Nurym <nurym.asqar@gmail.com>
   - Message: `feat(benchmark): implement clustered bootstrap, paired Wilcoxon tests, and benchmark runner`
   - Files changed:
     * `scripts/speech_benchmark.py`: 1013 insertions
     * `tests/test_benchmark.py`: 505 insertions, 1 deletion

2. **Byte-Level Pure ASCII Scan:**
   - Byte-by-byte scan verified zero non-ASCII bytes across all modified and related Increment 6 files:
     * `scripts/speech_benchmark.py`: 37,886 bytes, 0 non-ASCII bytes.
     * `tests/test_benchmark.py`: 40,624 bytes, 0 non-ASCII bytes.
     * `scripts/download_reference_corpora.py`: 3,312 bytes, 0 non-ASCII bytes.
     * `src/subtitle_workbench/corpora.py`: 19,868 bytes, 0 non-ASCII bytes.
     * `src/subtitle_workbench/metrics.py`: 16,672 bytes, 0 non-ASCII bytes.
     * `tests/test_metrics_stress.py`: 9,434 bytes, 0 non-ASCII bytes.
   - All logging, console output, and docstrings use ASCII symbols exclusively (`[*]`, `[+]`, `[OK]`, `[-]`, `->`, `|`).

3. **Code Structure and Authenticity:**
   - In `scripts/speech_benchmark.py`:
     * `_deserialize_raw_alignment(raw_file: Path)` reads `alignment_raw.json` and parses word and phoneme dictionaries into strictly typed `WordToken` and `PhonemeCue` models.
     * Mode 2 (`mode2_ctc`) and Mode 3 (`mode3_hybrid`) invoke `run_speech_pipeline` with a temporary directory and call `_deserialize_raw_alignment(Path(p_tmp) / "alignment_raw.json")`.
     * Mode 1 (`mode1_whisper`) constructs `WhisperTranscriber(device=None if device == "auto" else device, compute_type="int8")` and triggers `t_mode.unload()` upon completion.
     * `get_peak_host_ram_mb()` wraps `psutil.Process().memory_info()` in `except Exception:` and falls back gracefully to `_get_peak_ram_windows()` (via `psapi.GetProcessMemoryInfo`), `_get_peak_ram_posix()`, and `_get_peak_ram_tracemalloc()`.
     * Boundary errors are evaluated with `evaluate_alignment_boundaries(pred_words, utt.ref_words)` and `evaluate_alignment_boundaries(pred_phones, utt.ref_phones)`.
     * Aggregation calculates MAE, MedAE, RMSE, Acc@20ms, Acc@50ms, Acc@100ms, clustered bootstrap 95% CIs via `clustered_bootstrap_ci`, and paired hypothesis testing via `paired_wilcoxon_test`. No hardcoded metrics exist.

4. **Test Suite Verification:**
   - Executing `uv run --locked pytest tests/test_benchmark.py`:
     `30 passed in 5.69s` (100% pass rate).
     Includes tests for:
     * `test_speech_benchmark_real_production_execution` (verifies Mode 1, Mode 2, and Mode 3 production pipelines using monkeypatched models and `alignment_raw.json` deserialization).
     * `test_speech_benchmark_cli_seed_negative_exits_one` (verifies CLI returns exit code 1 on negative seed).
     * `test_speech_benchmark_negative_seed_validation` (verifies `BenchmarkError` on negative seed).
     * `test_speech_benchmark_invalid_resamples_validation` (verifies `BenchmarkError` on non-positive bootstrap resamples).
     * `test_get_peak_host_ram_mb_psutil_exception_fallback` (verifies fallback when `psutil` raises an exception).

5. **CLI Execution & Artifact Verification:**
   - Executing `uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_auditor_m2_iter2`:
     * Exit code: 0.
     * Generated `dist/test_auditor_m2_iter2/benchmark_results.json` (3,423 bytes).
     * Generated `dist/test_auditor_m2_iter2/manifest.json` (1,940 bytes).
     * Cryptographic SHA-256 match confirmed: `ee52c1a9bbc25656450a2b30ea3f1ef6590744a575e3e0af696457a63bb77ac0`.

6. **CLI Error Exit Code Verification:**
   - `uv run python scripts/speech_benchmark.py --offline-synthetic --seed -1` exited with code 1 (`[-] Benchmark Error: Random seed must be non-negative, got -1`).
   - `uv run python scripts/speech_benchmark.py --corpus invalid_choice` exited with code 2 (`error: argument --corpus: invalid choice: 'invalid_choice'`).

7. **Linters and Regression:**
   - `uv run --locked ruff check .` exited with code 0 (`All checks passed!`).
   - `uv run --locked ruff format --check .` exited with code 0 (`396 files already formatted`).
   - `uv run --locked pytest` exited with code 0 (`677 passed, 1 skipped in 22.47s`).

---

## 2. Logic Chain

1. Commit `a87fe08` was inspected directly from git history and confirmed to replace prior flawed integration with a robust deserialization mechanism (`_deserialize_raw_alignment`).
2. Source code inspection of `scripts/speech_benchmark.py` and `tests/test_benchmark.py` confirmed that all calculations for boundary errors, metrics, confidence intervals, and hypothesis tests are genuinely executed on input data. No facade returns, pre-calculated constants, or hardcoded strings were found.
3. Byte-level analysis confirmed strict compliance with the Zero-Emoji discipline: 0 non-ASCII bytes across all touched files.
4. Independent execution of `uv run --locked pytest tests/test_benchmark.py` verified that all 30 benchmark tests pass offline in 5.69s without external network access or model downloads.
5. Independent execution of `speech_benchmark.py` on the synthetic benchmark proved that the runner creates compliant, mathematically valid, and cryptographically verified JSON and manifest artifacts.
6. Verification of negative inputs confirmed proper separation of domain validation failures (exit code 1) from CLI syntax errors (exit code 2).
7. Full regression test suite execution (677 passed, 1 skipped) confirmed zero regressions across the codebase.
8. Therefore, the implementation in commit `a87fe08` is genuine, robust, and clean of integrity violations.

---

## 3. Caveats

1. Real-world CUDA inference on TIMIT/Buckeye corpora requires optional speech dependencies (`torch` and `faster-whisper`), which are properly isolated per R1/R5. In the offline test environment, synthetic datasets and isolated mocks are used, verifying complete logic deterministically.
2. No caveats.

---

## 4. Conclusion

The work product committed in `a87fe08` on branch `feature/increment-6-speech-benchmark` satisfies all integrity criteria and quality gates:
- Genuine and complete implementation of benchmark execution, metrics calculation, and reporting.
- Flawless deserialization of `alignment_raw.json` into `WordToken` and `PhonemeCue`.
- Multi-tier memory profiling fallback and robust CLI validation.
- Strict pure ASCII adherence (zero non-ASCII bytes).
- 100% test pass rate across benchmark suite and repository-wide regression suite.
- Zero linter or formatting issues.

**Final Verdict**: **CLEAN**. The work product is approved.

---

## 5. Verification Method

To independently reproduce the forensic audit:

1. **Verify ASCII Purity:**
   ```powershell
   python -c "
   for fn in ['scripts/speech_benchmark.py', 'tests/test_benchmark.py']:
       data = open(fn, 'rb').read()
       assert all(b < 128 for b in data), f'Non-ASCII bytes in {fn}'
   print('[OK] Zero non-ASCII bytes.')
   "
   ```

2. **Execute Benchmark Test Suite:**
   ```powershell
   uv run --locked pytest tests/test_benchmark.py
   ```
   *Expected*: 30 passed in < 6s.

3. **Execute Benchmark Runner:**
   ```powershell
   uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_auditor_m2_iter2
   ```
   *Expected*: Exit code 0, generates `benchmark_results.json` and `manifest.json`.

4. **Verify Exit Codes on Negative Seed and Invalid Options:**
   ```powershell
   uv run python scripts/speech_benchmark.py --offline-synthetic --seed -1; Write-Host "ExitCode:" $LASTEXITCODE
   uv run python scripts/speech_benchmark.py --corpus invalid_choice; Write-Host "ExitCode:" $LASTEXITCODE
   ```
   *Expected*: ExitCode 1 for seed -1; ExitCode 2 for invalid_choice.

5. **Verify Linters and Format:**
   ```powershell
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   *Expected*: All checks passed.

6. **Verify Full Regression Suite:**
   ```powershell
   uv run --locked pytest
   ```
   *Expected*: 677 passed, 1 skipped.

---

## Evidence Attachments

### Attachment 1: Byte-by-Byte Non-ASCII Scan Output
```
scripts/speech_benchmark.py: 37886 bytes, 0 non-ASCII bytes
tests/test_benchmark.py: 40624 bytes, 0 non-ASCII bytes
```

### Attachment 2: Pytest Benchmark Output
```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\nurym\Desktop\local-subtitle-workbench
configfile: pyproject.toml
collected 30 items

tests\test_benchmark.py ..............................                   [100%]

============================= 30 passed in 5.69s ==============================
```

### Attachment 3: Benchmark Runner Output
```
[*] Speech Alignment Benchmark Suite
[*] Corpus: timit (offline_synthetic=True)
[*] Output directory: dist\test_auditor_m2_iter2
[*] Random seed: 42, Bootstrap resamples: 2000
[*] Selected modes: mode1_whisper, mode2_ctc, mode3_hybrid
[+] Loaded 10 utterances (total audio duration: 17.10s)
[*] Executing Whisper Large-v3 INT8 (Internal Timestamps)...
[+] mode1_whisper complete: Word MAE = 119.1 ms, Acc@20ms = 0.0%, Acc@50ms = 0.0%
[*] Executing CTC Trellis (MMS_FA)...
[+] mode2_ctc complete: Word MAE = 35.1 ms, Acc@20ms = 12.1%, Acc@50ms = 84.8%, Phone MAE = 35.8 ms
[*] Executing Proposed Hybrid (Whisper + Bounded DTW + MFA)...
[+] mode3_hybrid complete: Word MAE = 11.7 ms, Acc@20ms = 100.0%, Acc@50ms = 100.0%, Phone MAE = 12.9 ms
[+] Proposed vs Whisper: W = 0.0, p = 1.6791e-12, Cliff's Delta = +1.00 (large)
[+] Proposed vs CTC: W = 8.0, p = 2.4223e-12, Cliff's Delta = +0.94 (large)
[*] Writing dist\test_auditor_m2_iter2\benchmark_results.json...
[*] Writing dist\test_auditor_m2_iter2\manifest.json...
[OK] Benchmark execution and artifact generation completed successfully.
```

### Attachment 4: Cryptographic Hash Verification
```
Calculated sha256: ee52c1a9bbc25656450a2b30ea3f1ef6590744a575e3e0af696457a63bb77ac0
Manifest sha256:   ee52c1a9bbc25656450a2b30ea3f1ef6590744a575e3e0af696457a63bb77ac0
Status: MATCH
```

### Attachment 5: Ruff Quality Gates
```
uv run --locked ruff check . -> All checks passed!
uv run --locked ruff format --check . -> 396 files already formatted
```

### Attachment 6: Full Regression Test Suite
```
======================= 677 passed, 1 skipped in 22.47s =======================
```
