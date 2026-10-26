## 2026-10-26T01:29:01Z

You are Worker 2 for Milestone 2 of Increment 5.
Working directory: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m2_1
Authoritative requirements: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md (read section ## 2026-10-26T00:58:19Z).
Explorer reports to follow:
- C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_inc5_2\handoff.md (Pipeline Architecture)
- C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_inc5_3\handoff.md (CLI Architecture & Exit Codes)

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Zero-Emoji Discipline:
Strictly no emojis or graphical Unicode icons anywhere in code, comments, docstrings, logs, git commits, or reports. Use clean ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |).

Write Ownership (Exclusive to this worker):
- src/subtitle_workbench/text_norm.py
- src/subtitle_workbench/audio.py
- src/subtitle_workbench/pipeline.py
- src/subtitle_workbench/cli.py
- src/subtitle_workbench/__init__.py
- tests/test_pipeline_speech.py

Milestone 2 Implementation Tasks:
1. In src/subtitle_workbench/text_norm.py:
   - Add normalize_transcript(transcript: str) -> list[TokenSpan]: return normalize_text_spans(transcript).
   - Export in __all__.
2. In src/subtitle_workbench/audio.py:
   - Add get_duration(path: Path | str) -> float: open with wave.open and return w.getnframes() / float(w.getframerate()).
   - Export in __all__.
3. In src/subtitle_workbench/pipeline.py:
   - Implement run_speech_pipeline(audio_path, output_dir, transcript=None, engine="auto", vad_silence_min_sec=0.4, max_chunk_sec=30.0, chunk_padding_sec=0.5, fallback_to_ctc=True, transcriber=None, aligner=None) -> dict
   - Execute all 7 stages:
     Stage 1 (Audio Validation): validate_wav, get_duration, output collision / overwrite protection (raise ValueError if output files exist or output resolves to input).
     Stage 2 (VAD & ASR): if transcript is None: extract_vad_silences, WhisperTranscriber transcribe inside try ... finally: transcriber.unload() (strict VRAM lifecycle). If transcript provided: read text (file or string), validate non-empty, silences via extract_vad_silences or empty list on fallback.
     Stage 3 (Normalization): if transcript provided: spans = normalize_transcript(text), create initial WordTokens across duration, form ASRSegments. If ASR run, segments already normalized.
     Stage 4 (Macro-chunking): partition_into_chunks with ChunkConfig(max_chunk_sec, min_silence_duration=vad_silence_min_sec, overlap_padding=chunk_padding_sec).
     Stage 5 & 6 (Forced Alignment & Global Reconciliation): aligner.align_chunks(chunks=chunks, audio_path=audio_path, engine=engine, fallback_to_ctc=fallback_to_ctc) returning reconciled WordTokens.
     Stage 7 (Artifact Export): mkdir output_dir, write subtitles.vtt (export_karaoke_vtt), timeline.jsonld (export_jsonld), alignment_raw.json (export_raw_alignment), and manifest.json (generate_manifest). Return manifest dictionary.
   - Retain align and provenance exports in __all__.
4. In src/subtitle_workbench/cli.py:
   - Support subcommands:
     - align-speech <audio_wav> -o <output_dir> [--engine auto|mfa|ctc] [--transcript <text_or_path>] [--vad-silence-min-sec 0.4] [--max-chunk-sec 30.0] [--chunk-padding-sec 0.5]
     - align-dtw <ref_wav> <target_wav> <cues_json> -o <output_dir> [--band-seconds 0.5] [--spectral-weight 0.15] [--max-frames 3000] [--max-cells 2000000]
     - Full backward compatibility with root flags: --reference, --target, --cues, -o / --output when no subcommand is specified.
   - Exit code contract:
     - 0 on success (print JSON summary metrics to stdout).
     - 2 on validation/contract/parsing errors with descriptive error message to stderr (error: <message>) and NO traceback.
5. In src/subtitle_workbench/__init__.py:
   - Export run_speech_pipeline, normalize_transcript, get_duration in __all__.
6. In tests/test_pipeline_speech.py:
   - Comprehensive offline CPU tests (< 5 seconds total runtime, no PyTorch or model downloads needed):
     - End-to-end pipeline test with mock transcriber and mock aligner on synthetic WAV, verifying all 4 output files on disk and return manifest structure.
     - ASR bypass test with explicit transcript.
     - VRAM lifecycle test verifying transcriber.unload() is invoked in success and error paths.
     - Output overwrite protection test (reject existing output directory files).
     - Output collision test (reject output resolving to input WAV).
     - Missing audio and corrupt audio error handling tests.
     - CLI tests: test align-speech exit 0 on mock, test align-speech exit 2 on invalid audio, test align-dtw, test legacy root flags backward compatibility.
7. Verify locally:
   - uv run --locked pytest tests/test_pipeline_speech.py
   - uv run --locked pytest
   - uv run --locked ruff check .
   - uv run --locked ruff format --check .
8. Git Commit:
   When verified, commit changes on feature/increment-5-exporters-and-pipeline with exact message:
   git commit -m "feat(pipeline): wire end-to-end speech alignment pipeline and CLI subcommands"
9. Write handoff.md in your working directory and notify me when complete.
