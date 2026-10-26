## 2026-10-26T04:15:36Z
You are worker_m2_1. Your working directory is C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m2_1.
Your parent orchestrator conversation ID is d7780ee7-0d12-43b1-8cad-0dd6f3550ad6.

MANDATORY FIRST STEP:
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md under header ## 2026-10-26T03:14:07Z.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\orchestrator_3\DISPATCH.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\orchestrator_3\SCOPE.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_inc6_3\handoff.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m1_2\handoff.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

ZERO-EMOJI DISCIPLINE:
Strictly no emojis or graphical Unicode icons anywhere in code, comments, docstrings, logs, git commits, or reports. Pure clean ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |).

MILESTONE 2 TASKS:
1. Implement `scripts/speech_benchmark.py`:
   - Command-line arguments:
     * `--corpus`: `timit` or `buckeye` (default `timit`)
     * `--data-dir`: directory of the corpus
     * `--output-dir`: output directory for reports (default `reports/benchmark`)
     * `--offline-synthetic`: flag to execute offline synthetic evaluation
     * `--seed`: random seed (default 42)
     * `--bootstrap-resamples`: number of resamples (default 2000)
   - 3-Way Ablation Execution:
     * Mode 1 (Baseline): Whisper Large-v3 INT8 internal timestamps (`word_timestamps=True`).
     * Mode 2 (CTC Trellis): Whisper ASR + MMS_FA forced alignment.
     * Mode 3 (Proposed Hybrid): Whisper ASR + Bounded DTW + Montreal Forced Aligner.
   - Offline Synthetic Mode:
     * When `--offline-synthetic` is enabled, generate 10 synthetic utterances using `stage_synthetic_benchmark(temp_synthetic_dir)`.
     * Evaluate each utterance across the 3 modes using realistic empirical simulation:
       - Mode 1: ~120 ms shift (cross-attention timestamp dispersion).
       - Mode 2: ~35 ms shift (CTC frame quantization).
       - Mode 3: ~12 ms shift (sub-20ms MFA triphone precision).
     * Evaluate word and phone boundaries via `evaluate_alignment_boundaries`.
     * Compute cluster-robust 95% confidence intervals via `clustered_bootstrap_ci(errors, clusters, num_resamples=2000, seed=42)`.
     * Compute paired hypothesis testing via `paired_wilcoxon_test` (Mode 3 vs Mode 1, Mode 3 vs Mode 2) obtaining W-stat, p-value, Cliff's Delta, and effect size.
   - Resource Profiling:
     * Real-Time Factor (RTF): `elapsed_time / total_audio_duration`.
     * Peak VRAM: `torch.cuda.max_memory_allocated() / (1024 * 1024)` if CUDA is available, else 0.0 MB.
     * Peak Host RAM: pure-Python / multi-tier fallback: `psutil` if present -> Windows `ctypes.windll.psapi.GetProcessMemoryInfo` (PeakWorkingSetSize / (1024 * 1024)) -> POSIX `resource.getrusage` -> `tracemalloc`. No mandatory new dependencies in pyproject.toml!
   - Report and Artifact Generation:
     * Write `benchmark_results.json` into output directory with full schema (metadata, modes 1/2/3 results, bootstrap CIs, Wilcoxon tests, hardware metrics).
     * Write `manifest.json` into output directory with SHA-256 hashes of inputs, generated artifacts, runtime environment, and `code_provenance()`.
     * Pure ASCII logging to stdout ([*], [+], [OK], [-]).

2. Unit & Integration Tests in `tests/test_benchmark.py`:
   - Test `scripts/speech_benchmark.py` programmatically and via CLI (`python scripts/speech_benchmark.py --offline-synthetic --output-dir ...`).
   - Verify `benchmark_results.json` and `manifest.json` existence and schema validity.
   - Verify Mode 3 achieves Acc@20ms > Mode 2 > Mode 1, and MAE < 20 ms.
   - Verify paired Wilcoxon significance (p < 0.05, large effect size).
   - Execution time: < 3 seconds offline on CPU.

3. Acceptance & Atomic Git Commit:
   - Run `uv run --locked pytest tests/test_benchmark.py` (must pass 100%).
   - Run `uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/benchmark_demo`.
   - Run `uv run --locked pytest` (all 666+ tests pass).
   - Run `uv run --locked ruff check .` and `uv run --locked ruff format --check .`.
   - Create atomic git commit:
     `git add scripts/speech_benchmark.py tests/test_benchmark.py`
     `git commit -m "feat(benchmark): implement clustered bootstrap, paired Wilcoxon tests, and benchmark runner"`

OUTPUT:
Write detailed implementation and verification report to `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m2_1\handoff.md`.
Send completion message to parent orchestrator (d7780ee7-0d12-43b1-8cad-0dd6f3550ad6).
