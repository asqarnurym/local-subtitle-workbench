# Quality and Adversarial Review Report: Milestone 2 Speech Benchmark Runner

**Reviewer / Adversarial Critic:** reviewer_m2_1  
**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\reviewer_m2_1`  
**Parent Orchestrator:** d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Artifact Reviewed:** `scripts/speech_benchmark.py` (Commit `8c5011e1905ad6b5a5d44d987a72f1fc5b648d41`)  
**Date:** 2026-10-26T04:38:30Z  
**Verdict:** REQUEST_CHANGES  
**Discipline:** Pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |). Zero Unicode emojis or graphical icons.

---

## Review Summary

**Verdict:** REQUEST_CHANGES

The speech benchmark runner `scripts/speech_benchmark.py` implements impressive architectural foundations: multi-tier host RAM profiling without `psutil`, GPU VRAM monitoring, reproducible offline synthetic simulation, cluster-robust bootstrap confidence intervals, paired Wilcoxon hypothesis testing, and cryptographic SHA-256 manifest generation.

However, an adversarial investigation of the production execution branch (`offline_synthetic=False`) revealed a **Critical Defect**: when executing Mode 2 (CTC Trellis) and Mode 3 (Proposed Hybrid) on real audio recordings, `res_pipe = run_speech_pipeline(...)` returns the execution manifest dictionary (which does not contain a `"words"` key). `scripts/speech_benchmark.py` attempts `pred_words = res_pipe.get("words", [])`, which silently evaluates to `[]`. Consequently, on real corpora, Mode 2 and Mode 3 evaluate zero words, report zero boundary errors, bypass Wilcoxon statistical tests, and produce all-zero evaluation tables.

---

## Findings

### [Critical] Finding 1: Mode 2 and Mode 3 Production Execution Silently Drops Word Predictions

- **What:** In `scripts/speech_benchmark.py`, lines 621-622 and lines 636-637, word predictions from `run_speech_pipeline` are extracted using `pred_words = res_pipe.get("words", [])`.
- **Where:** `scripts/speech_benchmark.py:616-623` and `scripts/speech_benchmark.py:631-638`.
- **Why:** `run_speech_pipeline()` (from `src/subtitle_workbench/pipeline.py:383`) returns the cryptographic execution manifest dictionary `manifest` (keys: `schema_version`, `tool`, `code`, `inputs`, `config`, `outputs`, `runtime`, `metrics`, `limitations`). The actual aligned words are written to `output_dir / "alignment_raw.json"`. Because `manifest` contains no `"words"` key, `res_pipe.get("words", [])` silently returns `[]`. In production mode (`offline_synthetic=False`), `if pred_words and utt.ref_words:` evaluates to `False`, `all_word_errors` remains empty, and Mode 2 and Mode 3 report 0 matched words, 0 ms MAE, and no paired Wilcoxon statistical significance.
- **Suggestion:** Within the `with tempfile.TemporaryDirectory() as p_tmp:` block, load and deserialize `raw_path = Path(p_tmp) / "alignment_raw.json"`, reconstructing `WordToken` and `PhonemeCue` objects:
  ```python
  raw_file = Path(p_tmp) / "alignment_raw.json"
  raw_data = json.loads(raw_file.read_text(encoding="utf-8"))
  pred_words = []
  for wd in raw_data.get("words", []):
      word_phones = [
          PhonemeCue(
              phoneme=pd["phoneme"],
              start=float(pd["start"]),
              end=float(pd["end"]),
              confidence=float(pd.get("confidence", 1.0)),
          )
          for pd in wd.get("phonemes", [])
      ]
      pred_words.append(
          WordToken(
              id=wd["id"],
              text=wd["text"],
              normalized=wd["normalized"],
              start=float(wd["start"]),
              end=float(wd["end"]),
              confidence=float(wd.get("confidence", 1.0)),
              phonemes=word_phones,
              char_start=wd.get("char_start"),
              char_end=wd.get("char_end"),
          )
      )
  pred_phones = [p for w in pred_words for p in w.phonemes]
  ```

### [Major] Finding 2: Production Execution Path Uncovered by Automated Test Suite

- **What:** All tests in `tests/test_benchmark.py` for `speech_benchmark.py` only exercise `--offline-synthetic` or `--corpus synthetic`. The real production branch (`else:` path in lines 597-642) has 0% test coverage.
- **Where:** `tests/test_benchmark.py:612-907`.
- **Why:** This complete coverage gap allowed Finding 1 to pass CI without being noticed.
- **Suggestion:** Add an integration test in `tests/test_benchmark.py` that executes `run_benchmark(corpus="synthetic", offline_synthetic=False)` with a mock `WhisperTranscriber` and mock `run_speech_pipeline` (or monkeypatching `run_speech_pipeline` to write a fixture `alignment_raw.json`), ensuring the production parsing and error aggregation logic is verified.

### [Minor] Finding 3: `device="auto"` Should Resolve to `None` for `WhisperTranscriber`

- **What:** In `scripts/speech_benchmark.py:603`, `WhisperTranscriber(device=device, compute_type="int8")` is invoked with `device="auto"` by default.
- **Where:** `scripts/speech_benchmark.py:603`.
- **Why:** In `src/subtitle_workbench/asr.py:70-87`, automatic device selection (`cuda` if available else `cpu`) triggers when `device is None`. If `device="auto"` is passed, `self._device` remains `"auto"`, which skips the CUDA detection logic.
- **Suggestion:** Pass `device_arg = None if device == "auto" else device` when constructing `WhisperTranscriber`.

---

## 1. Observation

1. **CLI Architecture and Flags:**
   - Evaluated flags: `--corpus`, `--data-dir`, `--output-dir`, `--offline-synthetic`, `--seed`, `--bootstrap-resamples`, `--device`, `--max-utterances`, `--modes`.
   - Verified default behaviors: `--corpus timit`, `--output-dir reports/benchmark`, `--seed 42`, `--bootstrap-resamples 2000`, `--device auto`.
   - Verified clean exit code handling: exit code 0 on success, exit code 1 on `BenchmarkError`, exit code 2 on unexpected exceptions or invalid CLI choices.

2. **Mandatory Verification Commands:**
   - Running speech benchmark offline synthetic demo:
     `uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_reviewer_m2`
     Result: Exited with code 0 in ~2.0s. Generated:
     * `dist/test_reviewer_m2/benchmark_results.json` (3,423 bytes)
     * `dist/test_reviewer_m2/manifest.json` (1,940 bytes)
   - Running linter:
     `uv run --locked ruff check .`
     Result: `All checks passed!` (0 warnings).
   - Running formatter check:
     `uv run --locked ruff format --check .`
     Result: `371 files already formatted` (0 formatting diffs).
   - Running benchmark test suite:
     `uv run --locked pytest tests/test_benchmark.py`
     Result: `25 passed in 4.75s`.
   - Full regression suite:
     `uv run --locked pytest`
     Result: `672 passed, 1 skipped in 14.82s`.

3. **Resource Profiling Verification:**
   - Inspected `get_peak_host_ram_mb()`: verified multi-tier fallback without `psutil`.
   - Tier 1: `psutil` (not installed, gracefully skipped).
   - Tier 2: Windows native `ctypes.WinDLL("psapi.dll").GetProcessMemoryInfo` reading `PeakWorkingSetSize`.
   - Verified that on Windows 11, `get_peak_host_ram_mb()` returned `37.55 MB`, which is a genuine peak working set measurement.
   - Inspected `get_peak_vram_mb()`: verified `torch.cuda.max_memory_allocated()` check with exception handling returning `0.0 MB` when CUDA is unavailable.

4. **Cryptographic Manifest Verification:**
   - Manifest `outputs["benchmark_results.json"]["sha256"]` contains:
     `322df452914abf3211ed8881e9e2907be3fd1fd3886444deb2316f2fc2115ba6`.
   - Independently calculated SHA-256 of `dist/test_reviewer_m2/benchmark_results.json`:
     `322df452914abf3211ed8881e9e2907be3fd1fd3886444deb2316f2fc2115ba6`.
     Result: Exact match.
   - Input audio file hashes: 10 synthetic WAV hashes recorded in `manifest.json`.

5. **Ablation Results in Synthetic Mode:**
   - Word MAE: Mode 1 = 119.12 ms, Mode 2 = 35.08 ms, Mode 3 = 11.68 ms (< 20 ms target).
   - Acc@20ms: Mode 3 = 100.0%, Mode 2 = 12.12%, Mode 1 = 0.0%.
   - Acc@50ms: Mode 3 = 100.0%, Mode 2 = 84.85%, Mode 1 = 0.0%.
   - Phone MAE: Mode 2 = 35.83 ms, Mode 3 = 12.86 ms (< 20 ms target).
   - Paired Wilcoxon:
     * Mode 3 vs Mode 1: W = 0.0, p = 1.6791e-12, Cliff's Delta = +1.00 (large).
     * Mode 3 vs Mode 2: W = 8.0, p = 2.4223e-12, Cliff's Delta = +0.94 (large).

6. **Adversarial Investigation of Production Execution Path:**
   - Inspected `scripts/speech_benchmark.py`, lines 611-641.
   - Traced `res_pipe = run_speech_pipeline(utt.wav_path, output_dir=p_tmp, engine=...)`.
   - Directly inspected `src/subtitle_workbench/pipeline.py:383`: `run_speech_pipeline` returns `manifest`, which does NOT have a `"words"` key.
   - Verified that `res_pipe.get("words", [])` returns `None` or `[]`.
   - Confirmed that in production mode, `pred_words` and `pred_phones` are always empty, causing Mode 2 and Mode 3 to report 0 matched words.

---

## 2. Logic Chain

1. In Observation 1, the CLI architecture properly exposes all required flags and conforms to project conventions.
2. In Observation 2, all automated verification gates specified in the dispatch (`scripts/speech_benchmark.py --offline-synthetic`, `ruff check`, `ruff format --check`, `pytest`) succeed cleanly.
3. In Observation 3 and 4, hardware resource profiling works without external dependencies (`psutil`), and the cryptographic manifest provides valid SHA-256 provenance.
4. In Observation 5, the synthetic simulation reproduces the empirical ablation shifts defined in the project specification.
5. In Observation 6, an adversarial trace of the production code path revealed that `run_speech_pipeline()` returns a manifest dictionary, while `scripts/speech_benchmark.py` expects `res_pipe.get("words", [])`.
6. Therefore, while synthetic evaluation functions as intended, production evaluation on real TIMIT/Buckeye recordings is broken.
7. Consequently, the deliverable cannot be approved in its current state and requires remediation.

---

## 3. Caveats

1. The offline synthetic mode (`--offline-synthetic`) is completely unaffected by Finding 1 because it bypasses `run_speech_pipeline()` and invokes `simulate_predictions()`.
2. Hardware profiling of GPU VRAM correctly reports 0.0 MB on environments without CUDA (or on CPU execution), which is expected behavior.
3. No other caveats.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

Milestone 2 cannot be approved due to Finding 1 (Critical):
- Mode 2 and Mode 3 production execution returns empty predictions because `res_pipe.get("words", [])` assumes `run_speech_pipeline` returns word tokens directly, whereas `run_speech_pipeline` returns the manifest dictionary and writes word tokens to `alignment_raw.json`.
- The worker must update `scripts/speech_benchmark.py` to read `p_tmp / "alignment_raw.json"` and reconstruct `WordToken` and `PhonemeCue` objects.
- The worker must add an integration test in `tests/test_benchmark.py` exercising the production branch with mock runners to ensure zero regression.

---

## 5. Verification Method

To independently verify the review findings:

1. **Verify the contract mismatch between `run_speech_pipeline` and `speech_benchmark.py`:**
   ```powershell
   uv run python -c "import tempfile, json, pathlib; from subtitle_workbench.pipeline import run_speech_pipeline; from tests.test_pipeline_speech import create_test_wav, make_mock_transcriber, make_mock_aligner; tmp = tempfile.TemporaryDirectory(); p = pathlib.Path(tmp.name) / 'test.wav'; create_test_wav(p, 2.0); out = pathlib.Path(tmp.name) / 'out'; res = run_speech_pipeline(p, out, transcriber=make_mock_transcriber(), aligner=make_mock_aligner()); print('res.get(\"words\"):', res.get('words')); raw_p = out / 'alignment_raw.json'; print('raw_p exists:', raw_p.exists()); print('raw_p words count:', len(json.loads(raw_p.read_text(encoding=\"utf-8\")).get('words', []))); tmp.cleanup()"
   ```
   *Expected output*: `res.get("words"): None`, `raw_p exists: True`, `raw_p words count: 2`. This proves `res_pipe.get("words", [])` in `speech_benchmark.py` receives empty words.

2. **Verify offline synthetic execution and gates:**
   ```powershell
   uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/test_reviewer_m2
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   uv run --locked pytest tests/test_benchmark.py
   ```
   *Expected output*: All commands exit 0.

### Invalidation Conditions
- Resolving Finding 1 by deserializing `alignment_raw.json` in `scripts/speech_benchmark.py`.
- Adding a production-mode unit/integration test in `tests/test_benchmark.py` verifying word extraction from `run_speech_pipeline`.
