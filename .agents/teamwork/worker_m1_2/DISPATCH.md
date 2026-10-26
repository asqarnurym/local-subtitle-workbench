## 2026-10-26T03:56:11Z
You are worker_m1_2. Your working directory is C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m1_2.
Your parent orchestrator conversation ID is d7780ee7-0d12-43b1-8cad-0dd6f3550ad6.

MANDATORY FIRST STEP:
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md under header ## 2026-10-26T03:14:07Z.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\orchestrator_3\DISPATCH.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\orchestrator_3\SCOPE.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_m1_fix_1\handoff.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_m1_fix_2\handoff.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_m1_fix_3\handoff.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

ZERO-EMOJI DISCIPLINE:
Strictly no emojis or graphical Unicode icons anywhere in code, comments, docstrings, logs, git commits, or reports. Pure clean ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |).

MILESTONE 1 ITERATION 2 TASKS:
1. Fix TIMIT Token Validation in `src/subtitle_workbench/corpora.py`:
   - Line 64 in `parse_timit_phn`: change `if len(parts) < 3:` to `if len(parts) != 3:`
   - Line 141 in `parse_timit_wrd`: change `if len(parts) < 3:` to `if len(parts) != 3:`
   - Ensure `CorpusFormatError` is raised whenever a line has fewer OR more than 3 tokens.

2. Fix IEEE-754 Boundary Threshold Precision in `src/subtitle_workbench/metrics.py`:
   - In `evaluate_alignment_boundaries`:
     Add `BOUNDARY_EPSILON_MS: float = 1e-4` (or round boundary error comparisons), and evaluate:
     `acc_20ms = float(np.mean(errors_arr <= (20.0 + BOUNDARY_EPSILON_MS)) * 100.0)`
     `acc_50ms = float(np.mean(errors_arr <= (50.0 + BOUNDARY_EPSILON_MS)) * 100.0)`
     `acc_100ms = float(np.mean(errors_arr <= (100.0 + BOUNDARY_EPSILON_MS)) * 100.0)`
     This prevents exact IEEE-754 floating point subtraction differences (e.g. 1.020 - 1.0 = 20.000000000000018 ms) from spuriously failing threshold checks.

3. Fix Wilcoxon Signed-Rank Continuity Correction Inversion in `src/subtitle_workbench/metrics.py`:
   - In `paired_wilcoxon_test`:
     Clamp deviation to zero when deviation is less than 0.5:
     `deviation = max(0.0, abs(w_stat - mean_w) - 0.5)`
     `z = deviation / math.sqrt(var_w)` (with `0.0` guard if `var_w == 0.0`)
     `p_value = 2.0 * (1.0 - _standard_normal_cdf(abs(z)))`
     Ensure exact null symmetry (identical or symmetric paired arrays) evaluates to `z = 0.0` and `p = 1.0`.

4. Unit Tests:
   - Clean up or update `tests/test_metrics_stress.py` if present (make all tests pass cleanly without xfail).
   - In `tests/test_benchmark.py`, add regression tests:
     * TIMIT lines with > 3 tokens raise `CorpusFormatError` in `parse_timit_phn` and `parse_timit_wrd`.
     * Exact 20.0ms shift at t=1.0s (e.g. 16320/16000 vs 1.0) achieves Acc@20ms == 100.0%.
     * Symmetric Wilcoxon paired differences evaluate to p-value == 1.0.

5. Verification & Git Commit:
   - Run `uv run --locked pytest tests/test_benchmark.py` (must pass 100%).
   - Run `uv run --locked pytest` (all tests must pass).
   - Run `uv run --locked ruff check .` and `uv run --locked ruff format --check .`.
   - Update / amend the commit on `feature/increment-6-speech-benchmark`:
     `git add .`
     `git commit --amend -m "feat(benchmark): implement reference corpora loaders and boundary evaluation metrics"`

OUTPUT:
Write detailed implementation and verification report to `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m1_2\handoff.md`.
Send completion message to parent orchestrator (d7780ee7-0d12-43b1-8cad-0dd6f3550ad6).
