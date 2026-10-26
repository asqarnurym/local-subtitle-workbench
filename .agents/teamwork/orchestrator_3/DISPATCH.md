## 2026-10-26T03:15:30Z

You are the Project Orchestrator for Increment 6 of the "Local Subtitle Alignment Workbench" project.

Your Working Directory: `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\orchestrator_3`
Project Repository: `C:\Users\nurym\Desktop\local-subtitle-workbench`
Target Branch: `feature/increment-6-speech-benchmark` (create and checkout from `feature/increment-5-exporters-and-pipeline`)

Authoritative Requirements:
Read `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md` under header `## 2026-10-26T03:14:07Z` for full requirements and acceptance criteria.

Key Mandates:
1. Maintain your persistent working memory in `BRIEFING.md` and track execution state in `progress.md` inside your working directory.
2. Zero-Emoji Discipline: strictly no emojis or graphical Unicode icons anywhere in code, comments, docstrings, logs, git commits, or reports. Use clean ASCII formatting only (`[+]`, `[-]`, `[*]`, `[OK]`, `[FAIL]`, `->`, `|`).
3. Hardware bounds: AMD Ryzen 9 5900HX, RTX 3050 Laptop GPU (4 GB VRAM, sequential budget <= 1.85 GB), Windows 11.
4. Unit/integration tests offline on CPU in < 5 seconds without network calls and without external model/corpora downloads (use offline synthetic dataset generator and stubs/mocks for inference runners).
5. Requirements summary:
   - R1: Reference Corpora Loader and Parser (`scripts/download_reference_corpora.py`):
     * Parse TIMIT `.phn` files (`parse_timit_phn`) to `list[PhonemeCue]`, mapping samples to seconds ($t = \text{sample} / 16000.0$) and filtering silence markers (`h#`, `pau`, `epi`).
     * Parse TIMIT `.wrd` files (`parse_timit_wrd`) to `list[WordToken]`.
     * Parse Buckeye Speech Corpus Praat TextGrids (`parse_buckeye_textgrid`) using `mfa_wrapper.parse_textgrid`.
     * Provide `stage_synthetic_benchmark(target_dir: Path) -> Path` generating an offline synthetic dataset (10 utterances with exact mathematical ground-truth boundaries) for deterministic unit testing without external downloads.
   - R2: Alignment Metrics and Statistical Analysis Module (`src/subtitle_workbench/metrics.py`):
     * Implement frozen dataclass `AlignmentEvaluationResult` capturing word and phone MAE, MedAE, RMSE, Acc@20ms, Acc@50ms, Acc@100ms, RTF, peak VRAM, and 95% bootstrap confidence intervals.
     * Implement `evaluate_alignment_boundaries(pred_tokens, ref_tokens, tolerance_ms=20.0)` for token matching and metrics computation.
     * Implement `clustered_bootstrap_ci(errors, clusters, num_resamples=2000, alpha=0.05, seed=42)` for speaker/utterance cluster-robust 95% confidence intervals.
     * Implement `paired_wilcoxon_test(errors_baseline, errors_proposed)` computing W-statistic, p-value, and Cliff's Delta effect size.
     * Ensure strict division-by-zero protection and typed exceptions (`BenchmarkError`, `CorpusFormatError`, `MetricComputationError`).
   - R3: Speech Benchmark Suite Runner (`scripts/speech_benchmark.py`):
     * CLI runner supporting `--corpus timit --data-dir <path> --output-dir <path> [--offline-synthetic]`.
     * Perform three-way ablation:
       - Mode 1 (Baseline): Whisper Large-v3 INT8 internal timestamps (`word_timestamps=True`).
       - Mode 2 (CTC Trellis): Whisper ASR + MMS_FA forced alignment.
       - Mode 3 (Proposed Hybrid): Whisper ASR + Bounded DTW + Montreal Forced Aligner.
     * Record Real-Time Factor (RTF), peak VRAM, and host RAM.
     * Output structured report `reports/benchmark/benchmark_results.json` and cryptographic `manifest.json`.
   - R4: Publication LaTeX Table Generator (`scripts/generate_paper_tables.py`):
     * Ingest `reports/benchmark/benchmark_results.json`.
     * Generate production-quality `booktabs` LaTeX tables:
       - Table 1: Alignment Accuracy comparison on TIMIT Core Test (Word/Phone MAE, Acc@20ms, Acc@50ms, Acc@100ms, 95% CI).
       - Table 2: Computational Performance (RTF, peak VRAM, peak RAM on RTX 3050 Laptop GPU).
       - Table 3: Statistical Significance (Wilcoxon W, p-value, Cliff's Delta).
     * Save tables to `docs/paper/table_alignment_accuracy.tex` and `docs/paper/table_computational_performance.tex`.
   - R5: Unit Test Suite (`tests/test_benchmark.py`):
     * Comprehensive tests for TIMIT `.phn` and `.wrd` parsers on synthetic data.
     * Oracle boundary tests for MAE, MedAE, Acc@20ms, Acc@50ms with fixed offsets (+15 ms, +25 ms, +60 ms).
     * Clustered bootstrap reproducibility and coverage tests.
     * Paired Wilcoxon hypothesis rejection tests.
     * LaTeX table syntax validation tests.
     * Execution requirement: 100% offline on CPU in < 5 seconds.
   - R6: SDLC Increment Report (`docs/increments/INCREMENT_6_EMPIRICAL_BENCHMARK.md`):
     * Formalize increment report following `docs/increments/TEMPLATE_INCREMENT_REPORT.md`.
     * Document benchmark methodology, statistical equations, test counts, execution logs, and LaTeX table snippets.
6. Acceptance Gates:
   - All existing 637 tests + all new benchmark tests pass: `uv run --locked pytest`
   - Linter passes with 0 warnings: `uv run --locked ruff check .`
   - Formatter passes: `uv run --locked ruff format --check .`
   - Offline benchmark run succeeds: `uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/benchmark_demo`
   - Package wheel build and smoke verification succeed:
     `uv run --locked python -m build --wheel --no-isolation`
     `uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out`
   - Git commit history on branch `feature/increment-6-speech-benchmark` contains atomic commits:
     * `feat(benchmark): implement reference corpora loaders and boundary evaluation metrics`
     * `feat(benchmark): implement clustered bootstrap, paired Wilcoxon tests, and benchmark runner`
     * `feat(paper): implement LaTeX table generator for Publication 2`
     * `docs(sdlc): formalize Increment 6 verification report and audit logs`
   - Formal increment report committed at `docs/increments/INCREMENT_6_EMPIRICAL_BENCHMARK.md`.
7. When all requirements and gates are satisfied, write `handoff.md` in your working directory and notify the Project Sentinel.
