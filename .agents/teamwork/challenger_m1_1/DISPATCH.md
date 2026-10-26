## 2026-10-26T03:38:49Z

You are challenger_m1_1. Your working directory is C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\challenger_m1_1.
Your parent orchestrator is d7780ee7-0d12-43b1-8cad-0dd6f3550ad6.

MANDATORY FIRST STEP:
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md under header ## 2026-10-26T03:14:07Z.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\orchestrator_3\DISPATCH.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m1_1\handoff.md.

TASK:
Adversarially challenge and stress-test `src/subtitle_workbench/corpora.py` and `scripts/download_reference_corpora.py`:
1. Test malformed TIMIT `.phn` and `.wrd` files (negative timestamps, non-monotonic times, extra/missing columns, invalid floats). Verify `CorpusFormatError` is raised defensively.
2. Test Buckeye TextGrid edge cases: empty tiers, weird interval labels, non-speech tokens.
3. Test `stage_synthetic_benchmark` in temporary isolated directory:
   - Verify all 10 utterances generate valid PCM16 16kHz mono WAV files that pass `validate_wav` and `load_wav` (RMS >= 1e-4).
   - Verify exact correspondence between generated audio duration and boundary files (.phn, .wrd, .TextGrid).
4. Run stress tests and report findings.
5. Conclude with clear verdict: APPROVE or REQUEST_CHANGES.

CONSTRAINTS:
- ZERO-EMOJI DISCIPLINE: strictly pure ASCII formatting ([+], [-], [*], [OK], [FAIL], ->, |).
- Write report to C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\challenger_m1_1\handoff.md.
- Send completion message with verdict to parent orchestrator.
