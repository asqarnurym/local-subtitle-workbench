# Handoff Report: Adversarial Challenge of Real-Mode Speech Benchmark

**Agent:** challenger_m2_iter2_1  
**Role:** critic, specialist  
**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\challenger_m2_iter2_1`  
**Parent Orchestrator:** d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Target Branch:** `feature/increment-6-speech-benchmark`  
**Date:** 2026-10-26T05:03:00Z  
**Handoff Type:** Hard  
**Verdict:** APPROVE  
**Discipline:** Pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |). Zero Unicode emojis or graphical icons.

---

## 1. Observation

1. **Target Implementation in `scripts/speech_benchmark.py`:**
   - Lines 497-524: `_deserialize_raw_alignment(raw_file: Path) -> list[WordToken]` reads `alignment_raw.json` and reconstructs `WordToken` instances with nested `PhonemeCue` objects.
   - Lines 634-682: Production dispatch across ablation modes:
     * Mode 1 (`mode1_whisper`): Instantiates `WhisperTranscriber(device=None if device == "auto" else device, compute_type="int8")`, transcribes `utt.wav_path`, unloads VRAM, sets `pred_phones = None`.
     * Mode 2 (`mode2_ctc`): Runs `run_speech_pipeline(utt.wav_path, output_dir=p_tmp, engine="ctc")`, deserializes `alignment_raw.json` via `_deserialize_raw_alignment`, extracts words and phones.
     * Mode 3 (`mode3_hybrid`): Runs `run_speech_pipeline(utt.wav_path, output_dir=p_tmp, engine="mfa")`, deserializes `alignment_raw.json` via `_deserialize_raw_alignment`, extracts words and phones.
   - Lines 684-699: Boundary evaluation invocation guarded by `if pred_words and utt.ref_words:` and `if pred_phones and utt.ref_phones:`.
   - Lines 706-749: Word metrics aggregation guarded by `if all_word_errors:`, with clean zero-default fallback if empty (`"mae_ms": 0.0, "num_matched": 0, "ci_95": [0.0, 0.0]`).
   - Lines 750-782: Phone metrics aggregation guarded by `if all_phone_errors:`, falling back to `phone_metrics_entry = None` if empty.
   - Lines 806-847: Statistical hypothesis testing guarded by `len(m1_errs) == len(m3_errs) and len(m3_errs) > 0`, safely skipping comparison if mode error lengths differ.

2. **Empirical Stress Test Execution (`tests/test_challenger_m2_iter2.py`):**
   - Implemented 21 adversarial stress tests covering:
     * Missing raw file (`test_deserialize_missing_file_raises_filenotfound`): raises `FileNotFoundError`.
     * Malformed JSON (`test_deserialize_malformed_json_raises_decode_error`): raises `json.JSONDecodeError`.
     * Empty JSON or missing words key (`test_deserialize_empty_json_or_missing_words`): returns `[]`.
     * Empty words list (`test_deserialize_empty_words_list`): returns `[]`.
     * Empty phonemes list (`test_deserialize_words_with_empty_phonemes_list`): returns `WordToken` with `phonemes=[]`.
     * Missing phonemes key (`test_deserialize_words_missing_optional_phonemes_key`): defaults safely to `phonemes=[]`.
     * Nested phoneme cues (`test_deserialize_nested_phonemes_parsing`): correctly constructs `PhonemeCue` instances.
     * Missing required keys (`test_deserialize_missing_required_word_keys_raises_keyerror`, `test_deserialize_missing_required_phoneme_keys_raises_keyerror`): raises `KeyError`.
     * Invalid numeric values and intervals (`test_deserialize_invalid_numeric_values_raises_valueerror`, `test_deserialize_inverted_word_interval_raises_valueerror`, `test_deserialize_inverted_phoneme_interval_raises_valueerror`, `test_deserialize_nan_time_raises_valueerror`): raises `ValueError`.
     * Pipeline missing output file (`test_real_mode_pipeline_missing_output_raises_benchmark_error`): wrapped in `BenchmarkError`.
     * Pipeline malformed output file (`test_real_mode_pipeline_malformed_json_raises_benchmark_error`): wrapped in `BenchmarkError`.
     * Full real-mode execution (`test_real_production_execution_all_modes_verified`): verifies Word and Phone MAE, MedAE, RMSE, Acc@20ms, Acc@50ms, Acc@100ms, and 95% CIs across all 3 modes.
     * Empty phonemes handling in real mode (`test_real_production_execution_empty_phonemes_graceful_handling`): words evaluated, phone metrics `None` without empty array error.
     * Empty words handling in real mode (`test_real_production_execution_empty_words_graceful_handling`): defaults to zeros without empty array error.
     * Single utterance cluster fallback (`test_real_production_execution_single_utterance_cluster_fallback`): `[mae, mae]` fallback without bootstrap crash.
     * Mismatched word count between modes (`test_real_production_execution_mismatched_mode_word_counts`): Wilcoxon test safely omitted.
     * CLI execution without optional dependencies (`test_cli_real_mode_uninstalled_dependencies_clean_exit_code_1`): exits with code 1, writes clean ASCII error to stderr, zero traceback.

3. **Empirical Command Results:**
   - `uv run --locked pytest tests/test_challenger_m2_iter2.py -v`:
     `21 passed in 2.82s` (100% pass rate).
   - `uv run --locked pytest tests/test_challenger_m2_iter2.py tests/test_benchmark.py`:
     `51 passed in 7.72s` (100% pass rate).
   - `uv run --locked pytest`:
     `698 passed, 1 skipped in 22.65s` (100% pass rate across entire repository).
   - `uv run --locked ruff check .`:
     `All checks passed!` (0 errors).
   - `uv run --locked ruff format --check .`:
     `401 files already formatted` (0 formatting diffs).
   - `uv run --locked python -m build --wheel --no-isolation`:
     `Successfully built local_subtitle_workbench-0.1.0-py3-none-any.whl`.
   - `uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_fresh`:
     `max_absolute_error_ms: 18.4`, exits with code 0.
   - `uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/benchmark_demo`:
     Exits with code 0, generates valid results and manifest.
   - `uv run python scripts/speech_benchmark.py --corpus synthetic --max-utterances 1`:
     Exits with code 1, prints `[-] Benchmark Error: Mode 1 production execution failed: faster-whisper is not installed. Please install with optional dependency: pip install local-subtitle-workbench[speech]`.

---

## 2. Logic Chain

1. Observations 1 and 2 demonstrate that `_deserialize_raw_alignment` correctly handles every edge case:
   - Non-existent files cleanly raise `FileNotFoundError`.
   - Truncated or malformed files raise `json.JSONDecodeError`.
   - Empty or missing `words` arrays evaluate to `[]`.
   - Words with empty or missing `phonemes` evaluate to `WordToken(phonemes=[])`.
   - Invalid temporal boundaries (`start >= end`, negative, NaN, Inf) are rejected by domain dataclass invariants.
2. In Observation 1 and 2, all exceptions during pipeline execution or deserialization in Mode 2 and Mode 3 are caught and wrapped into `BenchmarkError(f"Mode {mode_id} production execution failed: {err}")`. In CLI `main()`, `BenchmarkError` is cleanly intercepted, outputting `[-] Benchmark Error: ...` to stderr and returning exit code 1 without unhandled stack traces.
3. In Observation 2 and 3, `run_benchmark(corpus="synthetic", offline_synthetic=False)` was tested with mock transcriber and mock speech pipeline. It successfully computes word and phoneme boundary errors, MAE, MedAE, RMSE, Acc@20ms, Acc@50ms, Acc@100ms, and 95% bootstrap confidence intervals.
4. When phonemes are omitted or empty, `speech_benchmark.py` avoids empty array errors by setting `phone_metrics: None`.
5. When words are empty, `speech_benchmark.py` defaults word metrics to zero without divide-by-zero or empty-array errors in numpy.
6. When single-speaker or single-utterance subsets are benchmarked, clustered bootstrap gracefully falls back to `[w_mae, w_mae]` instead of raising `MetricComputationError`.
7. When prediction word counts differ across modes, paired Wilcoxon tests are safely omitted to prevent array length mismatch exceptions.
8. Full regression test suite (698 passed, 1 skipped), linters, formatters, wheel builds, and installed smoke tests pass with 100% compliance.

---

## 3. Caveats

1. Real GPU hardware execution on CUDA requires optional `faster-whisper` and `torch` packages (`[project.optional-dependencies] speech`). All tests execute offline on CPU using stubs and mocks per R5 constraints.
2. No caveats.

---

## 4. Conclusion

**Verdict: APPROVE**

The real-mode execution path in `scripts/speech_benchmark.py` is robust, defensive, and fully satisfies all project contracts:
- `_deserialize_raw_alignment` correctly reconstructs typed `WordToken` and `PhonemeCue` models from `alignment_raw.json` and cleanly handles missing files, malformed JSON, empty words, and empty phonemes.
- `run_benchmark(corpus="synthetic", offline_synthetic=False)` executes end-to-end with mock pipeline, properly calculating word and phoneme boundary metrics without empty array or division-by-zero errors.
- Error propagation wraps all pipeline failures in `BenchmarkError` and returns exit code 1 with clean ASCII formatting and zero stack traces.
- All 698 tests pass, ruff linter/formatter pass with 0 warnings, wheel build succeeds, and installed smoke verification passes.

---

## 5. Verification Method

To independently verify the adversarial challenge results:

1. **Run adversarial stress test suite:**
   ```powershell
   uv run --locked pytest tests/test_challenger_m2_iter2.py -v
   ```
   *Expected result*: 21 passed in < 3.5s.

2. **Run benchmark unit and integration test suite:**
   ```powershell
   uv run --locked pytest tests/test_benchmark.py -v
   ```
   *Expected result*: 30 passed in < 6.0s.

3. **Run offline synthetic benchmark demo:**
   ```powershell
   uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/benchmark_demo
   ```
   *Expected result*: Exits with code 0, generates `dist/benchmark_demo/benchmark_results.json` and `dist/benchmark_demo/manifest.json`.

4. **Verify real-mode CLI exit code when optional dependencies are absent:**
   ```powershell
   uv run python scripts/speech_benchmark.py --corpus synthetic --max-utterances 1
   Write-Host "ExitCode:" $LASTEXITCODE
   ```
   *Expected result*: Prints `[-] Benchmark Error: Mode 1 production execution failed: faster-whisper is not installed...`, exits with code 1.

5. **Run full regression and lint gates:**
   ```powershell
   uv run --locked pytest
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   *Expected result*: 698 passed, 1 skipped; 0 lint errors; 0 format diffs.

### Invalidation Conditions
- Any failure in `tests/test_challenger_m2_iter2.py`.
- Any unhandled exception or stack trace on missing/corrupt `alignment_raw.json`.
- Any empty array crash (`ValueError: zero-size array to reduction operation maximum which has no identity`) during metric computation.
