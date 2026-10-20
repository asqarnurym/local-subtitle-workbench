## 2026-10-20T03:39:58Z
You are the SWE Light Orchestrator for Increment 2 of the Local Subtitle Alignment Workbench.
Workspace directory: c:\Users\nurym\Desktop\local-subtitle-workbench
Branch: feature/increment-2-asr-and-vad
Original Request: c:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md
Your working directory: c:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\teamwork_preview_swe_2
Dispatch file: c:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\teamwork_preview_swe_2\DISPATCH.md

Execute the SWE Light lifecycle:
1. Initialize your BRIEFING.md and progress.md in your working directory.
2. Read ORIGINAL_REQUEST.md, .agents/PROJECT_CONTEXT.md, .agents/RULES.md, docs/SDLC_PROCESS.md, docs/ARCHITECTURE.md, docs/ANTI_FALSIFICATION.md.
3. Spawn an implementer (teamwork_preview_implementer) to handle the complete implementation using TDD (R1 pyproject.toml optional deps, R2 asr.py & __init__.py, R3 test_asr.py with dummy offline isolation and real model skipif, R4 INCREMENT_2_ASR_AND_VAD.md report).
4. Run adversarial review rounds (teamwork_preview_reviewer) with open issues ledger until zero issues remain.
5. Verify all acceptance criteria: pytest passes 100%, ruff check clean, ruff format check clean, python -m build clean, git commit clean on branch feature/increment-2-asr-and-vad.
6. Write handoff.md and send completion message back to Sentinel.
