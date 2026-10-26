# Dispatch: challenger_m3_2 (Table CLI Challenger)

## Mission
Adversarially challenge `scripts/generate_paper_tables.py` against edge cases and malformed inputs:
- Test missing input file, malformed JSON, missing optional modes or missing metrics (e.g. absent phone_metrics, absent computational_metrics, empty statistical_tests).
- Test CLI argument validation: invalid `--format`, non-existent `--output-dir` (auto-creation vs failure), exit code contract (exit 0 on success, exit 1 on runtime error, exit 2 on argparse error).
- Execute adversarial test harness and verify full regression suite.

## Target Commit & Branch
Commit `4620674` on branch `feature/increment-6-speech-benchmark`.

## Authoritative Specification
Read `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md`.

## Constraints
- Zero-Emoji Discipline: strictly pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |). Zero Unicode emojis or graphical icons.
- Deliver 5-component handoff report (Observation, Logic Chain, Caveats, Conclusion with explicit APPROVE/REQUEST_CHANGES, Verification Method) to `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\challenger_m3_2\handoff.md`.
