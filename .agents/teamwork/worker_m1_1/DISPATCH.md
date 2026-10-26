## 2026-10-26T01:08:19Z

[Message] timestamp=2026-10-26T01:08:19Z sender=38abfe49-ddb1-469c-979f-bc7467fda3c4 priority=MESSAGE_PRIORITY_HIGH content=You are Worker 1 for Milestone 1 of Increment 5.
Working directory: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m1_1
Authoritative requirements: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md (read section ## 2026-10-26T00:58:19Z).
Explorer Report to follow: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_inc5_1\handoff.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Zero-Emoji Discipline:
Strictly no emojis or graphical Unicode icons anywhere in code, comments, docstrings, logs, git commits, or reports. Use clean ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |).

Write Ownership (Exclusive to this worker):
- src/subtitle_workbench/provenance.py
- src/subtitle_workbench/export.py
- src/subtitle_workbench/pipeline.py (only for re-exporting sha256 and code_provenance)
- src/subtitle_workbench/__init__.py
- tests/test_export.py

Milestone 1 Implementation Tasks:
1. Create src/subtitle_workbench/provenance.py:
   Extract sha256(path: Path) -> str and code_provenance() -> dict from pipeline.py.
2. In src/subtitle_workbench/pipeline.py:
   Import sha256 and code_provenance from .provenance, and re-export them (__all__ or module namespace) to preserve backwards compatibility.
3. In src/subtitle_workbench/export.py:
   Implement:
   - format_vtt_timestamp(seconds: float) -> str: format HH:MM:SS.mmm with validation for nonnegative finite numbers. Preserve timestamp = format_vtt_timestamp alias.
   - export_karaoke_vtt(words: list[WordToken], max_line_words: int = 8, max_line_chars: int = 42, max_pause_break: float = 1.0) -> str: W3C WebVTT document with inline <c.word><timestamp>text</c> tags, cue segmentation by word/char limits and pause breaks, HTML escaping, empty input handling ("WEBVTT\n\n"), monotonic timestamps validation. Preserve webvtt(cues: list[Cue]) for backward compatibility.
   - export_jsonld(words: list[WordToken], audio_duration: float, media_urn: str, language: str = "en") -> dict: schema.org VideoObject with Clip parts, WCAG 2.1 compliance, ISO 8601 duration PT...S. Preserve jsonld(cues: list[Cue], duration: float, media_name: str) for backward compatibility.
   - export_raw_alignment(words: list[WordToken], audio_path: Path | str, alignment_method: str, metrics: dict | None = None) -> dict: hierarchical alignment structure (words and phonemes) and summary metrics (total words/phonemes, mean confidences, speech duration, pause duration, speech-to-pause ratio).
   - generate_manifest(input_audio_path: Path, output_dir: Path, words: list[WordToken], metrics: dict, config: dict | None = None) -> dict: provenance audit log manifest.json with SHA-256 hashes of input WAV and generated outputs (subtitles.vtt, timeline.jsonld, alignment_raw.json), incorporating code_provenance(). Writes to output_dir / "manifest.json".
4. In src/subtitle_workbench/__init__.py:
   Export the new functions in __all__.
5. In tests/test_export.py:
   Add comprehensive unit and contract tests verifying all new functions, edge cases, boundaries, negative inputs, and manifest generation.
6. Verify locally:
   Run:
   uv run --locked pytest tests/test_export.py
   uv run --locked pytest
   uv run --locked ruff check .
   uv run --locked ruff format --check .
7. Git Commit:
   When verified, commit changes on branch feature/increment-5-exporters-and-pipeline with exact message:
   git commit -m "feat(export): implement WebVTT karaoke, schema.org JSON-LD, raw alignment, and manifest exporters"
8. Write comprehensive handoff.md in your working directory and notify me when complete.
