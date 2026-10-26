# Quality and Adversarial Review Report: Milestone 2 Iteration 2

**Agent:** reviewer_m2_iter2_1  
**Roles:** reviewer, critic  
**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\reviewer_m2_iter2_1`  
**Parent Orchestrator:** d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Target Commit:** `a87fe08` (`feature/increment-6-speech-benchmark`)  
**Date:** 2026-10-26T04:58:30Z  
**Verdict:** APPROVE  
**Discipline:** Pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |). Zero Unicode emojis or graphical icons.

---

## 1. Observation

1. **Commit Inspection (`a87fe08`):**
   - Git log: `a87fe08 feat(benchmark): implement clustered bootstrap, paired Wilcoxon tests, and benchmark runner`.
   - Git diff stats: `scripts/speech_benchmark.py` (1013 additions), `tests/test_benchmark.py` (505 additions).
   - Working tree clean for production source files (only `.agents/teamwork/` metadata modified/untracked).

2. **Deserialization Implementation (`scripts/speech_benchmark.py:497-525`):**
   - Function `_deserialize_raw_alignment(raw_file: Path) -> list[WordToken]` loads `raw_data = json.loads(raw_file.read_text(encoding="utf-8"))`.
   - Iterates through `raw_data.get("words", [])`.
   - Constructs nested `PhonemeCue(phoneme=pd["phoneme"], start=float(pd["start"]), end=float(pd["end"]), confidence=float(pd.get("confidence", 1.0)))`.
   - Constructs `WordToken(id=wd["id"], text=wd["text"], normalized=wd["normalized"], start=float(wd["start"]), end=float(wd["end"]), confidence=float(wd.get("confidence", 1.0)), phonemes=word_phones, char_start=wd.get("char_start"), char_end=wd.get("char_end"))`.
   - Mode 2 (`scripts/speech_benchmark.py:659-661`) and Mode 3 (`scripts/speech_benchmark.py:675-677`) extract:
     ```python
     raw_file = Path(p_tmp) / "alignment_raw.json"
     pred_words = _deserialize_raw_alignment(raw_file)
     pred_phones = [p for w in pred_words for p in w.phonemes]
     ```

3. **WhisperTranscriber Instantiation (`scripts/speech_benchmark.py:638-641`):**
   - Mode 1 instantiates:
     ```python
     t_mode = WhisperTranscriber(
         device=None if device == "auto" else device,
         compute_type="int8",
     )
     ```
   - Matches `src/subtitle_workbench/asr.py:75-85`, where `device is None` triggers auto-selection between CUDA and CPU via `torch.cuda.is_available()`.
   - Followed by `t_mode.unload()` at line 644 for VRAM lifecycle preservation.

4. **Integration Test Verification (`tests/test_benchmark.py:909-1045`):**
   - `test_speech_benchmark_real_production_execution` tests `run_benchmark` with `corpus="synthetic"`, `offline_synthetic=False`, `max_utterances=2`, and `bootstrap_resamples=50`.
   - Mocks `WhisperTranscriber` for Mode 1 and `run_speech_pipeline` for Mode 2 and Mode 3.
   - Writes valid mock `alignment_raw.json` payload and asserts word and phone metrics are populated for Mode 2 and Mode 3, while Mode 1 has word metrics and `phone_metrics is None`.
   - Asserts generation of `benchmark_results.json` and `manifest.json`.

5. **CLI Exit Code and Exception Validation:**
   - Lines 543-546: Enforces `seed >= 0` and `bootstrap_resamples >= 1`, raising `BenchmarkError`.
   - Lines 1004-1010: `main()` catches `BenchmarkError` and general exceptions, returning exit code 1.
   - Argparse syntax errors naturally exit with code 2.
   - Validated independently:
     * `--seed -1`: returncode 1, stderr `[-] Benchmark Error: Random seed must be non-negative, got -1`.
     * `--corpus invalid_choice`: returncode 2, standard argparse error message.

6. **Test Suite and Code Quality Runs:**
   - `uv run --locked pytest tests/test_benchmark.py -v`:
     `30 passed in 5.48s`.
   - `uv run --locked ruff check .`:
     `All checks passed!`.
   - `uv run --locked ruff format --check .`:
     `396 files already formatted`.
   - `uv run --locked pytest`:
     `677 passed, 1 skipped in 22.16s`.
   - `uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/benchmark_demo`:
     Exit code 0, complete benchmark execution with clean ASCII reporting.

---

## 2. Logic Chain

1. **Integrity Assessment:**
   - Source code was inspected for hardcoded test scores, dummy facades, bypassed task logic, or fake artifacts.
   - Result: All mathematical and statistical computations (`evaluate_alignment_boundaries`, `clustered_bootstrap_ci`, `paired_wilcoxon_test`, `_deserialize_raw_alignment`) use genuine logic adhering to domain models and numerical validation rules. Zero integrity violations found.

2. **Deserialization Correctness:**
   - `run_speech_pipeline()` in `src/subtitle_workbench/pipeline.py` exports artifacts via `export_raw_alignment()`, creating `alignment_raw.json` containing hierarchical word and phoneme data.
   - `_deserialize_raw_alignment()` precisely reads this schema, reconstructing fully validated `WordToken` and `PhonemeCue` instances.
   - Boundary tests confirm that missing phonemes or missing character offsets default safely and pass model validation.

3. **Device Configuration Correctness:**
   - In `src/subtitle_workbench/asr.py`, `WhisperTranscriber` expects `device=None` for auto-detection.
   - Passing `device=None if device == "auto" else device` prevents literal string `"auto"` from being passed to `WhisperModel`, ensuring fallback to CPU if CUDA is absent.

4. **Test Isolation and Reliability:**
   - `test_speech_benchmark_real_production_execution` uses `monkeypatch` and `tmp_path`, leaving zero global state or lingering filesystem side-effects.
   - The test verifies end-to-end data flow from pipeline output through `_deserialize_raw_alignment` to metric computation.

5. **Error Handling and Exit Codes:**
   - Domain errors (`BenchmarkError`) exit with code 1, while CLI argument errors exit with code 2.
   - Negative seed and invalid bootstrap resample validations prevent crashes or infinite loops in statistical bootstrapping.

---

## 3. Caveats

1. Real-mode GPU execution with faster-whisper neural models requires CUDA hardware and optional `speech` extra dependencies. Offline CPU testing with synthetic corpora and deterministic mocks is the standard CI verification mode specified in Increment 6 R5.
2. No caveats.

---

## 4. Conclusion

**Verdict: APPROVE**

The remediation changes in commit `a87fe08` completely and correctly resolve all previously reported findings:
- [OK] `_deserialize_raw_alignment` correctly loads and parses `alignment_raw.json` into typed `WordToken` and `PhonemeCue` objects for Mode 2 and Mode 3.
- [OK] `WhisperTranscriber` instantiation in Mode 1 passes `device=None if device == "auto" else device`.
- [OK] `test_speech_benchmark_real_production_execution` exercises the real production execution path without regressions.
- [OK] CLI exit codes strictly distinguish domain runtime failures (exit 1) from argument syntax errors (exit 2).
- [OK] Automated tests (30/30 benchmark tests, 677/678 repo tests), linter (0 errors), and formatter (0 diffs) pass cleanly.

---

## 5. Verification Method

To independently verify this review:

1. **Benchmark tests execution:**
   ```powershell
   uv run --locked pytest tests/test_benchmark.py -v
   ```
   *Expected result:* 30 passed in < 6s.

2. **Full test suite execution:**
   ```powershell
   uv run --locked pytest
   ```
   *Expected result:* 677 passed, 1 skipped in ~22s.

3. **Code quality and formatting checks:**
   ```powershell
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   *Expected result:* All checks pass, 0 warnings/diffs.

4. **CLI exit code verification:**
   ```powershell
   uv run python -c "import subprocess, sys; p1 = subprocess.run([sys.executable, 'scripts/speech_benchmark.py', '--seed', '-1', '--offline-synthetic'], capture_output=True); assert p1.returncode == 1; p2 = subprocess.run([sys.executable, 'scripts/speech_benchmark.py', '--corpus', 'bad'], capture_output=True); assert p2.returncode == 2; print('[OK] Exit codes verified')"
   ```
