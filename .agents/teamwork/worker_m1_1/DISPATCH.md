## 2026-10-26T03:25:17Z

You are worker_m1_1. Your working directory is C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m1_1.
Your parent orchestrator conversation ID is d7780ee7-0d12-43b1-8cad-0dd6f3550ad6.

MANDATORY FIRST STEP:
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md under header ## 2026-10-26T03:14:07Z.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\orchestrator_3\DISPATCH.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\orchestrator_3\SCOPE.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_inc6_1\handoff.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_inc6_2\handoff.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

ZERO-EMOJI DISCIPLINE:
Strictly no emojis or graphical Unicode icons anywhere in code, comments, docstrings, logs, git commits, or reports. Pure clean ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |).

MILESTONE 1 TASKS:
1. Branch Checkout:
   Ensure you are on branch `feature/increment-6-speech-benchmark` created from `feature/increment-5-exporters-and-pipeline`:
   `git checkout -b feature/increment-6-speech-benchmark` (or checkout if already exists).

2. Implement `src/subtitle_workbench/corpora.py`:
   - `parse_timit_phn(phn_path: Path | str, sample_rate: int = 16000) -> list[PhonemeCue]`:
     * Read lines `<start_sample> <end_sample> <phone>`.
     * Convert samples to seconds: t = s / float(sample_rate).
     * Filter silence markers ('h#', 'pau', 'epi').
     * Return list of `PhonemeCue(phoneme=phone, start=t_start, end=t_end, confidence=1.0)`.
     * Defensive validation: raise `CorpusFormatError` on malformed line or non-monotonic timestamps.
   - `parse_timit_wrd(wrd_path: Path | str, sample_rate: int = 16000) -> list[WordToken]`:
     * Read lines `<start_sample> <end_sample> <word>`.
     * Convert samples to seconds: t = s / float(sample_rate).
     * Generate valid ASCII word identifiers (`w_0000`, etc.), normalized text via `normalize_transcript` / `normalize_text_spans`.
     * Return list of `WordToken`.
   - `parse_buckeye_textgrid(textgrid_path: Path | str) -> list[WordToken]`:
     * Ingest Buckeye Praat TextGrid file using `mfa_wrapper.parse_textgrid`.
     * Filter non-speech artifact tokens (`{B_TRANS}`, `{E_TRANS}`, `<IVER>`, `<LAUGH>`, `<VOCNOISE>`, `<NOISE>`, `SIL`, `<SIL>`, `UNKNOWN`, `<EXCLUDE>`).
   - `stage_synthetic_benchmark(target_dir: Path | str) -> Path`:
     * Generate 10 offline synthetic utterances with valid PCM16 16kHz mono audio (modulated sine waves with RMS >= 1e-4 so `load_wav` succeeds).
     * Exact integer-sample mathematical ground-truth word and phoneme boundaries.
     * Write paired `.phn`, `.wrd`, and `.TextGrid` files completely offline without any external downloads.
     * Return `Path(target_dir)`.

3. Implement `scripts/download_reference_corpora.py`:
   - CLI script supporting `--target-dir <path>` and `--offline-synthetic`.
   - Clean ASCII logging output.

4. Implement `src/subtitle_workbench/metrics.py` (Core Contracts, Exceptions, and Boundary Evaluation):
   - Exceptions: `BenchmarkError(Exception)`, `CorpusFormatError(BenchmarkError)`, `MetricComputationError(BenchmarkError)`.
   - Dataclasses:
     * `BoundaryEvaluation`: frozen dataclass holding `mae: float`, `medae: float`, `rmse: float`, `acc_20ms: float`, `acc_50ms: float`, `acc_100ms: float`, `boundary_errors_ms: list[float]`, `num_matched: int`, `num_unmatched: int`.
     * `AlignmentEvaluationResult`: frozen dataclass capturing word & phone metrics, RTF, peak VRAM, peak RAM, and bootstrap_ci_95 mapping.
     * `WilcoxonTestResult`: frozen dataclass (can provide stub or initial implementation for M1).
   - `evaluate_alignment_boundaries(pred_tokens: list[WordToken] | list[PhonemeCue], ref_tokens: list[WordToken] | list[PhonemeCue], tolerance_ms: float = 20.0) -> BoundaryEvaluation`:
     * Evaluate start and end boundary absolute errors in milliseconds: `|t_pred - t_ref| * 1000.0`.
     * Support 1-to-1 matching and dynamic programming text sequence alignment to handle insertions/deletions.
     * Compute MAE, MedAE, RMSE, Acc@20ms (% of errors <= 20.0), Acc@50ms (% of errors <= 50.0), Acc@100ms (% of errors <= 100.0).
     * Raise `MetricComputationError` if input token lists are empty or no tokens matched (division-by-zero protection).
   - Export public symbols in `src/subtitle_workbench/__init__.py`.

5. Implement initial unit tests in `tests/test_benchmark.py`:
   - Test TIMIT `.phn` parser: silence marker filtering, timestamp conversion.
   - Test TIMIT `.wrd` parser: word token properties and monotonicity.
   - Test Buckeye parser and non-speech filtering.
   - Test `stage_synthetic_benchmark`: generates 10 utterances, audio loadable via `validate_wav` and `load_wav`.
   - Test boundary evaluation metrics against exact oracle offsets:
     * Fixed offset +15 ms -> MAE == 15.0, Acc@20ms == 100.0%, Acc@50ms == 100.0%.
     * Fixed offset +25 ms -> MAE == 25.0, Acc@20ms == 0.0%, Acc@50ms == 100.0%.
     * Fixed offset +60 ms -> MAE == 60.0, Acc@20ms == 0.0%, Acc@50ms == 0.0%, Acc@100ms == 100.0%.
   - Test division-by-zero protection (empty inputs raise `MetricComputationError`).
   - Execution time must be < 5 seconds offline on CPU.

6. Verification & Git Commit:
   - Run `uv run --locked pytest tests/test_benchmark.py` (must pass 100%).
   - Run `uv run --locked pytest` (all 637+ tests must pass).
   - Run `uv run --locked ruff check .` and `uv run --locked ruff format --check .`.
   - Stage and commit with atomic message:
     `git commit -m "feat(benchmark): implement reference corpora loaders and boundary evaluation metrics"`

OUTPUT:
Write detailed implementation and verification report to `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m1_1\handoff.md`.
Send completion message to parent orchestrator (d7780ee7-0d12-43b1-8cad-0dd6f3550ad6).
