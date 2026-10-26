# Scope: Increment 5 - Exporters and End-to-End Speech Pipeline

## Architecture
- Module/package boundaries:
  - `src/subtitle_workbench/provenance.py`: File SHA-256 calculation and git repository code provenance extraction. Extracted from `pipeline.py` to decouple from exporters and prevent circular imports. [DONE]
  - `src/subtitle_workbench/export.py`: WebVTT karaoke export (`export_karaoke_vtt`), JSON-LD export (`export_jsonld`), raw alignment export (`export_raw_alignment`), timestamp formatting (`format_vtt_timestamp`), provenance manifest generation (`generate_manifest`). [DONE]
  - `src/subtitle_workbench/text_norm.py`: Add `normalize_transcript` helper wrapping `normalize_text_spans`. [DONE]
  - `src/subtitle_workbench/audio.py`: Add `get_duration` O(1) header-only duration reader. [DONE]
  - `src/subtitle_workbench/pipeline.py`: Speech alignment orchestrator coordinating audio validation, VAD, ASR, text normalization, macro-chunking, forced alignment, global reconciliation, and artifact export. [DONE]
  - `src/subtitle_workbench/cli.py`: CLI entry point supporting `align-speech` and `align-dtw` subcommands alongside root flags. [DONE]
  - `tests/test_export.py`: Unit and contract tests for exporters. [DONE]
  - `tests/test_pipeline_speech.py`: Integration tests for end-to-end speech pipeline and CLI invocation using offline CPU mocks. [DONE]
  - `docs/increments/INCREMENT_5_EXPORTERS_AND_PIPELINE.md`: Increment 5 SDLC report. [DONE]

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | `format_vtt_timestamp` | Format seconds to `HH:MM:SS.mmm` with nonnegative finite validation | M1 (DONE) | R1 |
| 2 | `export_karaoke_vtt` | W3C WebVTT document with inline `<c.word><timestamp>text</c>` tags, line word/char limits, pause breaks | M1 (DONE) | R1 |
| 3 | `export_jsonld` | Semantic schema.org JSON-LD VideoObject with Clip parts | M1 (DONE) | R1 |
| 4 | `export_raw_alignment` | Hierarchical alignment structure with word/phoneme timing and metrics | M1 (DONE) | R1 |
| 5 | `generate_manifest` | Cryptographic provenance audit log with SHA-256 hashes and code provenance | M1 (DONE) | R1 |
| 6 | Provenance modularization | Extract `sha256` and `code_provenance` into `provenance.py` | M1 (DONE) | R1 |
| 7 | Unit tests for exporters | Comprehensive tests covering tags, limits, schema, provenance in `test_export.py` | M1 (DONE) | R4 |
| 8 | `normalize_transcript` | Wrapper in `text_norm.py` | M2 (DONE) | R2 |
| 9 | `get_duration` | Header-only duration reader in `audio.py` | M2 (DONE) | R2 |
| 10 | `run_speech_pipeline` | 7-stage speech alignment pipeline returning execution manifest | M2 (DONE) | R2 |
| 11 | CLI subcommands | `align-speech` and `align-dtw` subcommands with backward compatibility | M2 (DONE) | R3 |
| 12 | Pipeline integration tests | End-to-end pipeline tests on synthetic WAV with mocks and CLI subprocess tests | M2 (DONE) | R4 |
| 13 | Quality Gates & SDLC Report | Pytest, ruff check, ruff format, wheel build, smoke test, atomic git commits, and increment report | M3 (DONE) | R5, Gates |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 0 | Survey & Exploration | Investigate existing codebase, branch status, models, chunker, aligner, export, and cli | none | DONE |
| 1 | Accessibility Exporters | `provenance.py`, `export.py`, and `test_export.py` | M0 | DONE |
| 2 | Speech Pipeline & CLI | `text_norm.py`, `audio.py`, `pipeline.py`, `cli.py`, and `test_pipeline_speech.py` | M1 | DONE |
| 3 | Quality Gates, SDLC & Commits | All quality gates, `INCREMENT_5_EXPORTERS_AND_PIPELINE.md`, and 3 atomic git commits | M2 | DONE |

## Interface Contracts
### `provenance.py` API (Implemented)
- `sha256(path: Path) -> str`
- `code_provenance() -> dict`

### `export.py` API (Implemented)
- `format_vtt_timestamp(seconds: float) -> str`
- `export_karaoke_vtt(words: list[WordToken], max_line_words: int = 8, max_line_chars: int = 42, max_pause_break: float = 1.0) -> str`
- `export_jsonld(words: list[WordToken], audio_duration: float, media_urn: str, language: str = "en") -> dict`
- `export_raw_alignment(words: list[WordToken], audio_path: Path | str, alignment_method: str, metrics: dict | None = None) -> dict`
- `generate_manifest(input_audio_path: Path, output_dir: Path, words: list[WordToken], metrics: dict, config: dict | None = None) -> dict`

### `pipeline.py` API (Implemented)
- `run_speech_pipeline(audio_path, output_dir, transcript=None, engine="auto", vad_silence_min_sec=0.4, max_chunk_sec=30.0, chunk_padding_sec=0.5, fallback_to_ctc=True, transcriber=None, aligner=None) -> dict`

### `cli.py` Subcommands (Implemented)
- `align-speech <audio_wav> -o <output_dir> [--engine auto|mfa|ctc] [--transcript <text_or_path>]`
- `align-dtw <ref_wav> <target_wav> <cues_json> -o <output_dir>`
- Backward compatible root flags: `--reference`, `--target`, `--cues`, `--output`.
