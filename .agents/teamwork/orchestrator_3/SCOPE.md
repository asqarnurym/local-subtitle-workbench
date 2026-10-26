# Scope: Increment 6 - Speech Benchmark Suite & Statistical Analysis

## Architecture
- Module/package boundaries:
  - `src/subtitle_workbench/corpora.py`: Reference corpora parsers (`parse_timit_phn`, `parse_timit_wrd`, `parse_buckeye_textgrid`) and synthetic benchmark data generator (`stage_synthetic_benchmark`). [DONE]
  - `scripts/download_reference_corpora.py`: CLI wrapper for downloading / staging reference corpora and synthetic benchmark data. [DONE]
  - `src/subtitle_workbench/metrics.py`: Data contracts (`AlignmentEvaluationResult`, `BoundaryEvaluation`, `WilcoxonTestResult`), boundary evaluation (`evaluate_alignment_boundaries`), clustered bootstrap CI (`clustered_bootstrap_ci`), paired Wilcoxon signed-rank test & Cliff's Delta (`paired_wilcoxon_test`), and typed exceptions (`BenchmarkError`, `CorpusFormatError`, `MetricComputationError`). [DONE]
  - `scripts/speech_benchmark.py`: Benchmark suite runner with 3-way ablation (Whisper baseline, CTC Trellis, Proposed Hybrid), resource profiling (RTF, peak VRAM, host RAM without psutil dependency), offline synthetic execution mode, `benchmark_results.json` and `manifest.json` generation. [PLANNED - M2]
  - `scripts/generate_paper_tables.py`: LaTeX booktabs table generator for Paper 2 (Tables 1, 2, 3 in `docs/paper/`). [PLANNED - M3]
  - `tests/test_benchmark.py`: Offline CPU test suite (< 5s) covering parsers, boundary metrics oracle tests (+15ms, +25ms, +60ms), clustered bootstrap determinism, Wilcoxon hypothesis testing, benchmark runner, and LaTeX syntax. [IN_PROGRESS - 29 tests active]
  - `docs/increments/INCREMENT_6_EMPIRICAL_BENCHMARK.md`: SDLC Increment 6 report. [PLANNED - M4]

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Git branch setup | Create and checkout branch `feature/increment-6-speech-benchmark` from `feature/increment-5-exporters-and-pipeline` | M1 (DONE) | Dispatch |
| 2 | `parse_timit_phn` | Parse TIMIT `.phn` to `list[PhonemeCue]`, convert sample to seconds (t = s / 16000.0), filter silence markers ('h#', 'pau', 'epi') | M1 (DONE) | R1 |
| 3 | `parse_timit_wrd` | Parse TIMIT `.wrd` to `list[WordToken]` with valid identifiers and timestamps | M1 (DONE) | R1 |
| 4 | `parse_buckeye_textgrid` | Parse Buckeye Praat TextGrid using `mfa_wrapper.parse_textgrid` and filter non-speech artifact tokens | M1 (DONE) | R1 |
| 5 | `stage_synthetic_benchmark` | Generate 10 offline synthetic utterances with exact mathematical ground-truth boundaries and valid PCM16 audio | M1 (DONE) | R1 |
| 6 | `download_reference_corpora.py` | CLI interface for downloading/staging reference corpora and generating synthetic benchmark data | M1 (DONE) | R1 |
| 7 | Exception hierarchy | `BenchmarkError(Exception)`, `CorpusFormatError(BenchmarkError)`, `MetricComputationError(BenchmarkError)` | M1 (DONE) | R2 |
| 8 | `AlignmentEvaluationResult` | Frozen dataclass capturing word/phone MAE, MedAE, RMSE, Acc@20ms, Acc@50ms, Acc@100ms, RTF, peak VRAM, peak RAM, bootstrap CIs | M1 (DONE) | R2 |
| 9 | `evaluate_alignment_boundaries` | Boundary error calculation (|t_pred - t_ref| * 1000.0 ms), dual boundary start/end, 1-to-1 and DP sequence matching, Acc@20/50/100ms, division-by-zero protection | M1 (DONE) | R2 |
| 10 | `clustered_bootstrap_ci` | Clustered bootstrap resampling by speaker/utterance (B=2000, alpha=0.05, seed=42) in pure NumPy | M1 (DONE) | R2 |
| 11 | `paired_wilcoxon_test` | Pure-NumPy Wilcoxon signed-rank test (W-statistic, p-value via math.erf) and O((N+M)log(N+M)) Cliff's Delta effect size | M1 (DONE) | R2 |
| 12 | `speech_benchmark.py` | CLI runner supporting `--corpus timit --data-dir <path> --output-dir <path> [--offline-synthetic]` with 3-way ablation | M2 | R3 |
| 13 | Hardware profiling | Real-Time Factor (RTF), peak VRAM (torch.cuda), host RAM (Windows ctypes / psutil fallback) | M2 | R3 |
| 14 | Benchmark artifacts | Structured report `reports/benchmark/benchmark_results.json` and cryptographic `manifest.json` | M2 | R3 |
| 15 | `generate_paper_tables.py` | CLI ingesting `benchmark_results.json` and emitting LaTeX booktabs tables | M3 | R4 |
| 16 | LaTeX Table 1 | Alignment accuracy comparison on TIMIT Core Test (`docs/paper/table_alignment_accuracy.tex`) | M3 | R4 |
| 17 | LaTeX Table 2 | Computational performance (RTF, peak VRAM, host RAM) (`docs/paper/table_computational_performance.tex`) | M3 | R4 |
| 18 | LaTeX Table 3 | Statistical significance (Wilcoxon W, p-value, Cliff's Delta) | M3 | R4 |
| 19 | Unit tests in `test_benchmark.py` | Offline CPU tests (< 5s) for parsers, metrics (+15ms, +25ms, +60ms oracles), bootstrap, Wilcoxon, runner, and LaTeX tables | M1-M3 | R5 |
| 20 | Quality gates & build smoke | `pytest` (666+ new tests), `ruff check`, `ruff format`, `speech_benchmark.py --offline-synthetic`, wheel build & smoke | M4 | Gates |
| 21 | SDLC report formalization | `docs/increments/INCREMENT_6_EMPIRICAL_BENCHMARK.md` following template | M4 | R6 |
| 22 | Atomic git commits | 4 Conventional Commits on `feature/increment-6-speech-benchmark` | M1-M4 | Gates |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 0 | Survey & Exploration | Codebase, models, statistical requirements, benchmark runner architecture | none | DONE |
| 1 | Reference Corpora & Boundary Metrics | Git branch checkout, `corpora.py`, `download_reference_corpora.py`, `metrics.py` (contracts, exceptions, `evaluate_alignment_boundaries`), and unit tests | M0 | DONE (commit daefa6a) |
| 2 | Statistical Analysis & Benchmark Runner | `scripts/speech_benchmark.py` (3-way ablation, profiling, JSON/manifest outputs), and unit tests | M1 | DONE (commit a87fe08) |
| 3 | Publication LaTeX Tables | `scripts/generate_paper_tables.py`, LaTeX booktabs generation (`table_alignment_accuracy.tex`, `table_computational_performance.tex`), and unit tests | M2 | PLANNED |
| 4 | Quality Gates, SDLC Report & Atomic Commits | Full test pass, ruff, wheel build & smoke, `INCREMENT_6_EMPIRICAL_BENCHMARK.md`, and 4 atomic git commits | M3 | PLANNED |

## Interface Contracts
### `corpora.py` API (Implemented & Verified)
- `parse_timit_phn(phn_path: Path | str, sample_rate: int = 16000) -> list[PhonemeCue]`
- `parse_timit_wrd(wrd_path: Path | str, sample_rate: int = 16000) -> list[WordToken]`
- `parse_buckeye_textgrid(textgrid_path: Path | str) -> list[WordToken]`
- `stage_synthetic_benchmark(target_dir: Path | str) -> Path`

### `metrics.py` API (Implemented & Verified)
- Exceptions: `BenchmarkError(Exception)`, `CorpusFormatError(BenchmarkError)`, `MetricComputationError(BenchmarkError)`
- `AlignmentEvaluationResult`: frozen dataclass with word and phone metrics, RTF, memory, and confidence intervals
- `evaluate_alignment_boundaries(pred_tokens: list[WordToken] | list[PhonemeCue], ref_tokens: list[WordToken] | list[PhonemeCue], tolerance_ms: float = 20.0) -> BoundaryEvaluation`
- `clustered_bootstrap_ci(errors: np.ndarray | list[float], clusters: np.ndarray | list[str | int], num_resamples: int = 2000, alpha: float = 0.05, seed: int = 42) -> tuple[float, float]`
- `paired_wilcoxon_test(errors_baseline: np.ndarray | list[float], errors_proposed: np.ndarray | list[float]) -> WilcoxonTestResult`
