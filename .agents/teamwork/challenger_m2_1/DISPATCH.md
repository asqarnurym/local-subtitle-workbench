## 2026-10-26T04:32:06Z

You are challenger_m2_1. Your working directory is C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\challenger_m2_1.
Your parent orchestrator is d7780ee7-0d12-43b1-8cad-0dd6f3550ad6.

MANDATORY FIRST STEP:
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md under header ## 2026-10-26T03:14:07Z.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\orchestrator_3\DISPATCH.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m2_1\handoff.md.

TASK:
Adversarially challenge `scripts/speech_benchmark.py`:
1. Stress test CLI arguments: invalid corpus names, non-existent directories, invalid modes, zero or negative resamples, extreme seeds.
2. Stress test memory profiling fallback: test with psutil uninstalled/mocked as None, verify Windows ctypes and tracemalloc fallbacks operate without crashing.
3. Verify exit codes and clean error handling (exit code 1 on runtime error, 2 on argparse error).
4. Issue verdict: APPROVE or REQUEST_CHANGES.

CONSTRAINTS:
- ZERO-EMOJI DISCIPLINE: strictly pure ASCII ([+], [-], [*], [OK], [FAIL], ->, |).
- Write report to C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\challenger_m2_1\handoff.md.
- Send completion message to parent orchestrator.
