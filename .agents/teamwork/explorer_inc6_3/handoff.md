# Increment 6 Handoff Report: Benchmark Suite, LaTeX Tables, Unit Tests, and SDLC Formalization

**Agent:** explorer_inc6_3  
**Target:** Orchestrator (d7780ee7-0d12-43b1-8cad-0dd6f3550ad6)  
**Date:** 2026-10-26T03:24:00Z  
**Type:** Hard Handoff (Investigation Complete)  
**Discipline:** Pure ASCII formatting ([+], [-], [*], [OK], [FAIL], ->, |). Zero Unicode emojis or graphical icons.

---

## 1. Observation

1. **Test Suite Baseline:**
   - Ran `uv run --locked pytest`.
   - Tool Command & Result:
     ```
     collected 638 items
     637 passed, 1 skipped in 12.03s
     SKIPPED [1] tests\test_asr.py:1129: faster-whisper is not installed
     ```
   - Confirmed exact existing baseline test count is 637 passed tests.

2. **Git Working Tree Status:**
   - Command `git status` output:
     ```
     On branch feature/increment-5-exporters-and-pipeline
     Untracked files:
       .agents/teamwork/explorer_inc6_1/
       .agents/teamwork/explorer_inc6_2/
       .agents/teamwork/explorer_inc6_3/
       .agents/teamwork/orchestrator_3/
     no changes added to commit
     ```
   - Target branch `feature/increment-6-speech-benchmark` needs to be created from `feature/increment-5-exporters-and-pipeline`.

3. **Dependency Footprint (`pyproject.toml:13-19`):**
   - Base dependencies: `dependencies = ["numpy>=2.1,<3"]`.
   - Optional speech dependencies: `faster-whisper>=1.0.0`, `torch>=2.2.0`.
   - No `psutil` or `scipy` in base or optional dependencies. Base distribution must remain lightweight (standard library + NumPy only).

4. **Speech Pipeline Integration (`src/subtitle_workbench/pipeline.py:157-384`):**
   - `run_speech_pipeline(audio_path, output_dir, engine="auto"|"mfa"|"ctc", ...)` already implements 7 deterministic stages: audio validation, VAD/ASR with `unload()` VRAM cleanup, text normalization, macro-chunking (30s bound, 0.5s padding), forced alignment, monotonic reconciliation, and artifact export (`subtitles.vtt`, `timeline.jsonld`, `alignment_raw.json`, `manifest.json`).

5. **Existing Scripts Inventory (`scripts/`):**
   - `scripts/benchmark.py`: Evaluates legacy DTW time-transfer against synthetic timing oracle (not speech recognition/alignment).
   - `scripts/smoke_wheel.py`: Offline socket guard smoke test.
   - Requirement R3 calls for `scripts/speech_benchmark.py` and Requirement R4 calls for `scripts/generate_paper_tables.py`.

6. **SDLC Documentation Architecture (`docs/increments/TEMPLATE_INCREMENT_REPORT.md`):**
   - Verified 7 required sections: (1) Executive Summary & Objective, (2) Traceability to Individual Plan & Quality Gates, (3) Inventory of Changes, (4) Verification Evidence & Quality Gate Results, (5) Architectural Decisions, (6) Edge Cases Tested, (7) Handover & Prerequisites.

---

## 2. Logic Chain

1. **From Observation 1 & 3 to Resource Profiling Design:**
   - Because base dependencies only include NumPy and standard library, and `pytest` runs offline without heavy dependencies, profiling host RAM in `scripts/speech_benchmark.py` must not strictly depend on `psutil`.
   - A multi-tier memory reader is required: attempt `psutil` if present; fallback to Windows `ctypes.windll.psapi.GetProcessMemoryInfo` (PeakWorkingSetSize); fallback to POSIX `resource.getrusage`; fallback to `tracemalloc`. This guarantees 100% offline portability without new dependencies.
   - For GPU VRAM: query `torch.cuda.max_memory_allocated()` if CUDA is available, otherwise default to 0.0 MB.
   - For Real-Time Factor (RTF): compute ratio of monotonic wall-clock elapsed time (`time.perf_counter()`) to total audio duration (`audio.get_duration`).

2. **From Observation 1 & 4 to Offline Benchmark Harness:**
   - Unit tests (`tests/test_benchmark.py`) and smoke runs must complete offline on CPU in < 5 seconds without GPU or external model weights downloads.
   - Therefore, `scripts/speech_benchmark.py` must support an `--offline-synthetic` mode that integrates with `stage_synthetic_benchmark()` (from `scripts/download_reference_corpora.py`).
   - In synthetic mode, mock predictors generate deterministic token alignments simulating the empirical characteristics of each ablation mode:
     * Mode 1 (Whisper Baseline): shifts ground truth by ~120 ms (simulating cross-attention timestamp dispersion).
     * Mode 2 (CTC Trellis): shifts ground truth by ~35 ms (simulating CTC frame quantization).
     * Mode 3 (Proposed Hybrid): shifts ground truth by ~12 ms (simulating sub-20ms MFA triphone precision).
   - This allows end-to-end execution of data loading, boundary metric evaluation, clustered bootstrap CI estimation, Wilcoxon significance testing, JSON serialization, and manifest hashing in < 2 seconds on CPU.

3. **From Requirement R4 to Publication LaTeX Generator:**
   - Ingesting `reports/benchmark/benchmark_results.json` directly into `scripts/generate_paper_tables.py` completely decouples benchmark execution from LaTeX typesetting.
   - Emits three production-quality `booktabs` tables into `docs/paper/`:
     * Table 1 (`table_alignment_accuracy.tex`): Method, Word MAE [95% CI], Word MedAE, Phone MAE, Acc@20ms, Acc@50ms, Acc@100ms.
     * Table 2 (`table_computational_performance.tex`): Method, RTF, Peak VRAM, Peak Host RAM, Throughput.
     * Table 3 (`table_statistical_significance.tex`): Comparison Pair, Wilcoxon W, p-value, Cliff's Delta, Effect Size.
   - Escapes `%` and `_` characters to prevent LaTeX compiler failures, with strict ASCII discipline (zero emojis).

4. **From Observation 1 & 6 to Test Suite Architecture:**
   - `tests/test_benchmark.py` must test:
     * Parser correctness on synthetic TIMIT `.phn` (silence filtering: `h#`, `pau`, `epi`) and `.wrd`.
     * Oracle boundary tests with fixed known offsets (+15ms -> Acc@20ms 100%, +25ms -> Acc@20ms 0% / Acc@50ms 100%, +60ms -> Acc@50ms 0% / Acc@100ms 100%).
     * Clustered bootstrap reproducibility with `seed=42` and valid coverage.
     * Paired Wilcoxon hypothesis rejection and Cliff's Delta magnitude.
     * CLI runner invocation (`speech_benchmark.py --offline-synthetic`).
     * LaTeX table generation and booktabs syntax validation (`\toprule`, `\midrule`, `\bottomrule`).
   - All tests use synthetic mathematical signals or deterministic mocks, running in < 3 seconds on CPU.

---

## 3. Caveats

1. **MFA External Binary on Local Windows:**
   - Montreal Forced Aligner (`mfa`) requires Anaconda/Miniforge or standalone binary. In environments where `mfa` binary is not on system `PATH`, `ForcedAligner` automatically falls back to CTC Trellis unless mock/offline mode is used.
2. **TIMIT Corpus Availability:**
   - Real TIMIT (LDC93S1) and Buckeye speech corpora are restricted by academic licensing. Offline synthetic staging (`--offline-synthetic`) provides 100% test coverage for development, while real corpora are mounted via `--data-dir` during production evaluation.
3. No other caveats.

---

## 4. Conclusion

Requirements R3, R4, R5, and R6 are fully analyzed, structurally specified, and ready for immediate implementation:
- `scripts/speech_benchmark.py`: 3-way ablation harness (Whisper, CTC Trellis, Proposed Hybrid), pure-Python resource profiling (RTF, peak VRAM, host RAM), deterministic offline synthetic path, generating `reports/benchmark/benchmark_results.json` and `manifest.json`.
- `scripts/generate_paper_tables.py`: Automated generation of Tables 1, 2, and 3 in LaTeX `booktabs` format with proper escaping and formatting for Publication 2 in the *Scientific Journal of Astana IT University*.
- `tests/test_benchmark.py`: Comprehensive test suite verifying parsers, boundary metrics oracle offsets (+15ms, +25ms, +60ms), clustered bootstrap determinism, Wilcoxon hypothesis testing, CLI execution, and LaTeX syntax, running in < 5 seconds offline on CPU.
- `docs/increments/INCREMENT_6_EMPIRICAL_BENCHMARK.md`: SDLC audit report formalization based on `TEMPLATE_INCREMENT_REPORT.md`.

Detailed findings, data contracts, mathematical formulas, and LaTeX code snippets are documented in:
`C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_inc6_3\analysis.md`.

---

## 5. Verification Method

To independently verify the facts and designs stated in this report:

1. **Verify Baseline Test Count (637 passing):**
   ```bash
   uv run --locked pytest
   ```
   Expected: 637 passed, 1 skipped.

2. **Verify Codebase Layout & Absence of New Dependencies:**
   ```bash
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```

3. **Inspect Detailed Analysis:**
   Read `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_inc6_3\analysis.md`.

4. **Invalidation Conditions:**
   - Any requirement for new third-party dependencies in the base distribution (e.g. mandatory `psutil` or `scipy`).
   - Unit test suite execution exceeding 5.0 seconds on standard CPU.
   - Presence of any graphical Unicode emojis in code, reports, or generated LaTeX tables.
