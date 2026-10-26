# Dispatch: worker_inc6_m3_1 (LaTeX Table Worker)

## Mission
Implement Milestone 3 of Increment 6: Publication LaTeX Table Generator (`scripts/generate_paper_tables.py`), generate publication tables in `docs/paper/`, write comprehensive unit tests in `tests/test_benchmark.py`, ensure 100% test pass rate and pure ASCII compliance, and create atomic git commit 3.

## Working Directory
`C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_inc6_m3_1`

## Authoritative Specification
Read `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md` (specifically Section 4: Paper 2 Publication Tables and Section 5: Verification & Quality Gates).

## Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Constraints
- Zero-Emoji Discipline: strictly pure ASCII only ([+], [-], [*], [OK], [FAIL], ->, |). Zero Unicode emojis or graphical icons in code, comments, docstrings, logs, git commits, or reports.
- CPU Offline Verification: all tests must run offline on CPU in < 5 seconds without network calls and without external dependencies.
- Git Branch: `feature/increment-6-speech-benchmark`.
- Atomic Commit: `feat(paper): implement LaTeX table generator for Publication 2`.
## 2026-10-26T05:03:55Z
You are worker_inc6_m3_1, the LaTeX Table Worker for Milestone 3 of Increment 6 on branch feature/increment-6-speech-benchmark.
Your working directory is: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_inc6_m3_1

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY ZERO-EMOJI RULE:
Zero-Emoji Discipline: strictly pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |). Zero Unicode emojis or graphical icons in code, comments, docstrings, logs, git commits, or reports.

Authoritative Specification:
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md (specifically Section 4: Paper 2 Publication Tables and Section 5: Verification & Quality Gates).
Also inspect scripts/speech_benchmark.py to see the exact structure and keys of benchmark_results.json.

Deliverables:
1. Implement `scripts/generate_paper_tables.py`:
   - Command-line interface with flags:
     * `--input`: path to benchmark JSON (default: `reports/benchmark/benchmark_results.json`)
     * `--output-dir`: directory where LaTeX tables are written (default: `docs/paper`)
     * `--format`: table format (default: `booktabs`)
   - Parses the benchmark JSON schema emitted by `scripts/speech_benchmark.py`:
     * `modes`: dictionary with entries for `mode1_whisper`, `mode2_ctc`, `mode3_hybrid` (each having `description`, `word_metrics`, `phone_metrics`, `computational_metrics`).
     * `statistical_tests`: dictionary with entries for `mode3_vs_mode1`, `mode3_vs_mode2` (each having `w_statistic`, `p_value`, `cliffs_delta`, `effect_size`).
   - Generates 3 production LaTeX tables using LaTeX `booktabs` package (`\toprule`, `\midrule`, `\bottomrule`):
     * Table 1 (`docs/paper/table_alignment_accuracy.tex`):
       - Title / Caption: TIMIT Core Test Alignment Accuracy Across Ablation Modes
       - Columns: Method, Word MAE [95% CI] (ms), Word MedAE (ms), Phone MAE (ms), Acc@20ms (\%), Acc@50ms (\%), Acc@100ms (\%)
       - Format numbers cleanly (e.g. 1 decimal place: `11.7 [11.2, 12.3]`, `12.9`, `100.0\%`).
       - If phone metrics are None (as in Mode 1), output `--` or `---`.
       - Escape all percent symbols (`\%`) and underscores (`\_`) properly in LaTeX so that tables compile without syntax errors.
     * Table 2 (`docs/paper/table_computational_performance.tex`):
       - Title / Caption: Computational Efficiency Across Ablation Modes
       - Columns: Method, Real-Time Factor (RTF), Peak VRAM (MB), Peak Host RAM (MB)
       - Format RTF to 3 decimal places (e.g. `0.045\(\times\)` or `0.045`).
       - Format Peak VRAM with 1 decimal place (or `--` if 0.0).
       - Format Peak Host RAM with 1 decimal place.
     * Table 3 (`docs/paper/table_statistical_significance.tex`):
       - Title / Caption: Paired Wilcoxon Signed-Rank Test and Cliff's Delta Effect Size
       - Columns: Comparison Pair, Wilcoxon \(W\), \(p\)-value, Cliff's \(\delta\), Effect Size
       - Comparison Pair: e.g. "Proposed Hybrid vs. Whisper Large-v3", "Proposed Hybrid vs. CTC Trellis".
       - Format p-values: e.g. `< 0.001` or `$1.68 \times 10^{-12}$`.
       - Format Cliff's delta with sign: e.g. `+1.00` or `+0.94`.
   - Exits with return code 0 on success, 1 on runtime/data errors, and 2 on argument parsing errors.

2. Comprehensive Unit & Integration Tests in `tests/test_benchmark.py`:
   - Test `scripts/generate_paper_tables.py` functions and CLI.
   - Test table generation from mock benchmark dictionary and from actual JSON file.
   - Assert all 3 `.tex` files are generated.
   - Verify presence of LaTeX elements: `\begin{table}`, `\begin{tabular}`, `\toprule`, `\midrule`, `\bottomrule`, `\end{tabular}`, `\end{table}`.
   - Assert that no unescaped `%` exists in tabular cells (so rows aren't commented out in LaTeX).
   - Test error handling when input file is missing or invalid JSON.

3. Generate Sample Tables:
   - Run `uv run python scripts/generate_paper_tables.py --input dist/benchmark_demo/benchmark_results.json --output-dir docs/paper`
   - Ensure `docs/paper/table_alignment_accuracy.tex`, `docs/paper/table_computational_performance.tex`, and `docs/paper/table_statistical_significance.tex` exist.

4. Full Verification Gates:
   - `uv run --locked pytest tests/test_benchmark.py` (all tests pass)
   - `uv run --locked pytest` (all 677+ tests pass, 0 regressions)
   - `uv run --locked ruff check .` (0 errors)
   - `uv run --locked ruff format --check .` (0 diffs)

5. Git Commit:
   Stage the changes and create atomic commit 3 on branch `feature/increment-6-speech-benchmark`:
   `git commit -m "feat(paper): implement LaTeX table generator for Publication 2"`

6. Report:
   Write a comprehensive handoff report to `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_inc6_m3_1\handoff.md`.
   Send a summary message back to orchestrator when finished.
