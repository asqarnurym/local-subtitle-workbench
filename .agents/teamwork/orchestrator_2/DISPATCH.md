## 2026-10-26T01:00:02Z

You are the Project Orchestrator for Increment 5 of the "Local Subtitle Alignment Workbench" project.

Your Working Directory: `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\orchestrator_2`
Project Repository: `C:\Users\nurym\Desktop\local-subtitle-workbench`
Target Branch: `feature/increment-5-exporters-and-pipeline` (verify or branch from `feature/increment-4-forced-alignment`)

Authoritative Requirements:
Read `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md` under header `## 2026-10-26T00:58:19Z` for full requirements and acceptance criteria.

Key Mandates:
1. Maintain your persistent working memory in `BRIEFING.md` and track execution state in `progress.md` inside your working directory.
2. Zero-Emoji Discipline: strictly no emojis or graphical Unicode icons anywhere in code, comments, docstrings, logs, git commits, or reports. Use clean ASCII formatting only (`[+]`, `[-]`, `[*]`, `[OK]`, `[FAIL]`, `->`, `|`).
3. Hardware bounds: AMD Ryzen 9 5900HX, RTX 3050 Laptop GPU (4 GB VRAM, sequential budget <= 1.85 GB), Windows 11.
4. Unit/integration tests offline on CPU in < 5 seconds without network calls and without external model downloads (use mocks/stubs for inference runners).
5. Requirements summary:
   - R1: Standardized Accessibility Exporters (`src/subtitle_workbench/export.py`): `format_vtt_timestamp`, `export_karaoke_vtt`, `export_jsonld`, `export_raw_alignment`, `generate_manifest`.
   - R2: End-to-End Speech Alignment Orchestrator (`src/subtitle_workbench/pipeline.py`): `run_speech_pipeline` with 7 pipeline execution stages and execution manifest dictionary with runtime metrics.
   - R3: CLI Interface Extension (`src/subtitle_workbench/cli.py`): `align-speech` and `align-dtw` subcommands + backward compatibility with root flags.
   - R4: Automated Unit & Integration Tests: extend `tests/test_export.py` and create `tests/test_pipeline_speech.py`.
   - R5: Increment Report Documentation: `docs/increments/INCREMENT_5_EXPORTERS_AND_PIPELINE.md`.
6. Acceptance Gates:
   - `uv run --locked pytest` (100% pass across all tests including existing 446+)
   - `uv run --locked ruff check .`
   - `uv run --locked ruff format --check .`
   - `uv run --locked python -m build --wheel --no-isolation`
   - `uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out`
   - Atomic git commits matching specification.
7. When all requirements and gates are satisfied, write `handoff.md` in your working directory and notify the Project Sentinel.
