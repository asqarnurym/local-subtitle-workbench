# Handoff Report - Increment 5 Speech Pipeline Orchestrator & Testing Strategy

Date: 2026-10-26T01:08:00Z
Explorer: Explorer 2 (Increment 5)
Working Directory: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_inc5_2
Authoritative Requirements: C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md (Section ## 2026-10-26T00:58:19Z)

--------------------------------------------------------------------------------

## 1. Observation

### 1.1 Existing Component Inventory & Functionality
1. `src/subtitle_workbench/audio.py`:
   - Line 24: `def validate_wav(path: Path | str, sample_rate: int = 16000) -> None`: Validates uncompressed mono PCM16 at specified sample rate. Checks channel count, sample width (2 bytes), compression type ("NONE"), framerate, non-empty frame count, and EOF byte consistency in 64 KB chunks. Raises `TypeError`, `FileNotFoundError`, or `ValueError`.
   - Line 59: `def load_wav(path: Path, config: Config) -> Audio`: Loads whole audio into `Audio` dataclass (samples in float64 / 32768.0). Enforces `config.max_frames` and non-silence checks (RMS >= 1e-4).
   - Line 98: `def slice_wav(source_path: Path | str, target_path: Path | str, start_sec: float, end_sec: float) -> None`: Slices audio range `[start_sec, end_sec]` into `target_path`. Enforces `0.0 <= start_sec < total_dur` and `end_sec > start_sec`.
   - Duration Calculation: There is currently no standalone `get_duration()` helper function in `audio.py`. `Audio.duration` property exists on loaded `Audio` dataclasses (`len(self.samples) / self.sample_rate`), but loading the full audio array is memory-intensive for multi-minute audio files.
2. `src/subtitle_workbench/asr.py`:
   - Line 89: `class WhisperTranscriber`:
     - `__init__(self, model_size_or_path: str = "large-v3", device: str | None = None, compute_type: str | None = None, vad_filter: bool = True, min_silence_duration_ms: int = 400, model_instance: Any | None = None)`
     - `transcribe(self, audio_path: Path | str, language: str = "en", **kwargs: Any) -> list[ASRSegment]`: Runs Faster-Whisper with `word_timestamps=True`, returns typed `ASRSegment`s containing `WordToken`s. Normalizes text via `normalize_text_spans`.
     - Line 334: `def unload(self) -> None`: Sets `self._model = None`, executes `gc.collect()`, and if `torch.cuda.is_available()`, calls `torch.cuda.empty_cache()`.
     - Lines 346-350: Implements context manager `__enter__` and `__exit__`, which delegates to `self.unload()`.
   - Line 353: `def extract_vad_silences(audio_path: Path | str, min_silence_duration_ms: int = 400, vad_backend: Any | None = None) -> list[tuple[float, float]]`: Extracts acoustic silence intervals. When `vad_backend` is `None`, imports `faster_whisper.vad.VadOptions` and `get_speech_timestamps`. If `faster-whisper` is not installed, it raises `ASRInferenceError`.
3. `src/subtitle_workbench/text_norm.py`:
   - Line 327: `def normalize_text_spans(text: str) -> list[TokenSpan]`: Bidirectional token-to-span normalizer. Handles contractions, number-to-words, hyphenated words, lowercase NFKD normalization, and punctuation trimming. Returns `TokenSpan(token, normalized, char_start, char_end)`.
   - Function `normalize_transcript` is currently NOT defined in `text_norm.py` (ripgrep search returned zero matches in `src/`).
   - Line 404: `def project_tokens_to_cues(tokens: list[WordToken], original_text: str, id_prefix: str = "c") -> list[Cue]`: Reversible projection from WordTokens back to display cues.
4. `src/subtitle_workbench/chunker.py`:
   - Line 309: `class ChunkConfig(max_chunk_duration=30.0, min_chunk_duration=1.0, overlap_padding=0.5, min_silence_duration=0.4)`.
   - Line 29: `def partition_into_chunks(segments: list[ASRSegment], silences: list[tuple[float, float]], total_duration: float, config: ChunkConfig | None = None) -> list[AudioChunk]`: Hierarchical anchor partitioning bounded by `max_chunk_duration` (30s) and symmetric padding (0.5s clamped within `[0.0, total_duration]`).
   - Line 227: `def reconcile_chunk_alignments(chunks: list[AudioChunk], chunk_aligned_words: list[list[WordToken]], padded_coordinates: bool = False) -> list[WordToken]`: Translates chunk timestamps to global timeline, strips overlap padding seam words, and enforces strict monotonicity (`word[i+1].start >= word[i].end`), raising `MonotonicityError` on corruption.
5. `src/subtitle_workbench/aligner.py`:
   - Line 43: `class ForcedAligner`:
     - `__init__(self, mfa_runner: SubprocessRunner | None = None, ctc_aligner: TorchAudioAligner | None = None)`
     - Line 54: `def align_chunks(self, chunks: list[AudioChunk], audio_path: Path | str, transcripts: list[str] | None = None, engine: Literal["auto", "mfa", "ctc"] = "auto", fallback_to_ctc: bool = True, dictionary: str = "english_us_arpa", acoustic_model: str = "english_us_arpa") -> list[WordToken]`:
       - Slices audio chunks into temporary directory via `audio.slice_wav`.
       - Dispatches alignment to `mfa` (`run_mfa_batch`) or `ctc` (`aligner.align(...)`).
       - Internally calls `reconcile_chunk_alignments(chunks=chunks, chunk_aligned_words=chunk_aligned_words, padded_coordinates=True)`!
       - Cleans up temporary directory in a `finally` block.
       - Returns globally reconciled `list[WordToken]`.
   - Line 187: Module-level wrapper `align_chunks(...)`.
6. `src/subtitle_workbench/pipeline.py`:
   - Currently contains DTW-based alignment:
     - `sha256(path: Path) -> str`: standard SHA-256 file hashing.
     - `code_provenance() -> dict`: computes sha256 hash of all `*.py` files in package, plus git revision and dirty status.
     - `align(...)`: existing DTW alignment pipeline writing `subtitles.vtt`, `timeline.jsonld`, `alignment-path.json`, `manifest.json`.
     - Output overwrite protection: Lines 75-78:
       `if any(path.exists() for path in outputs): raise ValueError("output files already exist; choose a new output directory")`
       `if any(output.resolve() == source.resolve() for output in outputs for source in paths): raise ValueError("output may not overwrite an input")`
       Uses `open("x", encoding="utf-8")` for atomic creation.
7. `src/subtitle_workbench/cli.py`:
   - Currently only supports root flags `--reference`, `--target`, `--cues`, `--output`, `--band-seconds`, etc., returning exit code 0 on success and 2 on error.
8. Current Test Execution Baseline:
   - Tool execution `uv run --locked pytest`:
     `446 passed, 1 skipped in 4.37s` (the skipped test is in `test_asr.py` because `faster-whisper` is intentionally not installed in the lightweight base environment).

--------------------------------------------------------------------------------

## 2. Logic Chain

### 2.1 Missing Function Resolution (`normalize_transcript`)
- Observation: R2 states "3. Normalization: apply `text_norm.normalize_transcript` preserving word mappings." However, `text_norm.py` only exports `normalize_text_spans`.
- Deduction: A wrapper `def normalize_transcript(transcript: str) -> list[TokenSpan]: return normalize_text_spans(transcript)` must be added to `src/subtitle_workbench/text_norm.py` and exported in `__init__.py`. This provides the exact requested API without duplicating normalization logic.

### 2.2 Audio Duration Helper
- Observation: In `run_speech_pipeline`, total audio duration is required in Stage 1, Stage 4 (`partition_into_chunks`), Stage 7 (`export_jsonld`), and runtime metrics (`pipeline_rtf`). Currently, duration requires either loading the entire array via `load_wav` (which runs RMS checks and restricts `max_frames`) or opening with `wave.open`.
- Deduction: An O(1) header-only duration reader should be implemented in `audio.py` (or as a helper in `pipeline.py`):
  ```python
  def get_duration(audio_path: Path | str) -> float:
      with wave.open(str(audio_path), "rb") as w:
          return w.getnframes() / float(w.getframerate())
  ```

### 2.3 Execution Flow of `run_speech_pipeline` (7 Stages)
The orchestrator signature is defined as:
```python
def run_speech_pipeline(
    audio_path: Path | str,
    output_dir: Path | str,
    transcript: str | Path | None = None,
    engine: Literal["auto", "mfa", "ctc"] = "auto",
    vad_silence_min_sec: float = 0.4,
    max_chunk_sec: float = 30.0,
    chunk_padding_sec: float = 0.5,
    fallback_to_ctc: bool = True,
    transcriber: WhisperTranscriber | Any | None = None,
    aligner: ForcedAligner | Any | None = None,
) -> dict:
```

Step-by-step stage execution:
- **Stage 1 (Audio Validation & Target Pre-flight)**:
  - Convert `audio_path` and `output_dir` to `Path`.
  - Validate file existence: `validate_wav(audio_path)`.
  - Read `audio_duration = get_duration(audio_path)`.
  - Check target collision: Define expected outputs `subtitles.vtt`, `timeline.jsonld`, `alignment_raw.json`, `manifest.json`.
  - If any output file already exists: `raise ValueError("output files already exist; choose a new output directory")`.
  - If any output path resolves to `audio_path`: `raise ValueError("output may not overwrite an input")`.
- **Stage 2 (VAD & ASR / Transcript Branching)**:
  - If `transcript is None`:
    - Extract silences: `silences = extract_vad_silences(audio_path, min_silence_duration_ms=int(round(vad_silence_min_sec * 1000)))`.
    - Instantiate transcriber if `transcriber is None`: `transcriber_inst = WhisperTranscriber(min_silence_duration_ms=int(round(vad_silence_min_sec * 1000)))`.
    - Run ASR inside `try ... finally` to guarantee VRAM release:
      ```python
      try:
          segments = transcriber_inst.transcribe(audio_path)
      finally:
          if hasattr(transcriber_inst, "unload"):
              transcriber_inst.unload()
      ```
  - If `transcript is not None`:
    - Resolve text: if path to existing file, read file text; else treat as string.
    - Validate non-empty text (raise `ValueError` if empty or whitespace only).
    - Silences: attempt `extract_vad_silences(...)`; on `ASRError` or missing model, fallback safely to `silences = []`.
- **Stage 3 (Normalization)**:
  - If `transcript` was provided:
    - Call `spans = normalize_transcript(transcript_text)`.
    - Map spans to uniform initial `WordToken`s across `[0.0, audio_duration]`:
      Each token gets `id=f"w_{idx}"`, `text=span.token`, `normalized=span.normalized`, `char_start=span.char_start`, `char_end=span.char_end`, `confidence=0.9`.
    - Form initial `segments = [ASRSegment(id="seg_0", start=0.0, end=audio_duration, text=transcript_text, words=words_list)]`.
  - If ASR was run, `segments` already contain normalized `WordToken`s.
- **Stage 4 (Macro-chunking)**:
  - Instantiate `chunk_cfg = ChunkConfig(max_chunk_duration=max_chunk_sec, min_silence_duration=vad_silence_min_sec, overlap_padding=chunk_padding_sec)`.
  - Call `chunks = partition_into_chunks(segments=segments, silences=silences, total_duration=audio_duration, config=chunk_cfg)`.
- **Stage 5 & 6 (Forced Alignment & Global Reconciliation)**:
  - If `aligner is None`: `aligner_inst = ForcedAligner()`.
  - Call `aligned_result = aligner_inst.align_chunks(chunks=chunks, audio_path=audio_path, engine=engine, fallback_to_ctc=fallback_to_ctc)`.
  - Notice: `ForcedAligner.align_chunks` already handles audio chunk slicing (Stage 5) and calls `reconcile_chunk_alignments` (Stage 6). If a mock returns a 2D list `list[list[WordToken]]`, call `reconcile_chunk_alignments(chunks, aligned_result, padded_coordinates=True)` defensively; if it returns `list[WordToken]`, use directly.
  - Result is `reconciled_words: list[WordToken]`.
- **Stage 7 (Artifact Export & Manifest)**:
  - Create output directory: `output_dir.mkdir(parents=True, exist_ok=True)`.
  - Compute metrics: `elapsed_seconds`, `rtf = elapsed_seconds / audio_duration`, `word_count`, `mean_word_confidence`, `speech_to_pause_ratio`.
  - Export:
    - `export_karaoke_vtt(reconciled_words)` -> write to `output_dir / "subtitles.vtt"`.
    - `export_jsonld(reconciled_words, audio_duration, media_urn)` -> write to `output_dir / "timeline.jsonld"`.
    - `export_raw_alignment(reconciled_words, audio_path, alignment_method=engine, metrics=...)` -> write to `output_dir / "alignment_raw.json"`.
    - `generate_manifest(input_audio_path=audio_path, output_dir=output_dir, words=reconciled_words, metrics=..., config=...)` -> write to `output_dir / "manifest.json"`.
  - Return the manifest dictionary.

### 2.4 Resource Cleanup & VRAM Lifecycle
- Observation: RTX 3050 Laptop GPU has a 4 GB limit; peak sequential budget is <= 1.85 GB.
- Deduction:
  - Transcriber unloading must happen immediately after ASR finishes and before forced alignment begins so Whisper and Wav2Vec2/MMS_FA do not co-occupy VRAM.
  - Use `try ... finally: transcriber.unload()` to guarantee cleanup even if transcription or normalization throws an error.
  - If `aligner` has an `unload()` method or creates a model instance, invoke cleanup in a `finally` block or context manager.

### 2.5 Offline CPU Mocking Strategy for `test_pipeline_speech.py`
- Observation: Tests must run offline on CPU in < 5 seconds without network calls and without downloading multi-gigabyte models.
- Deduction:
  - Synthetic WAV: Use `create_test_wav` (pure NumPy sine wave written to PCM16 WAV via stdlib `wave`).
  - Mock Transcriber: Pass a `MagicMock(spec=WhisperTranscriber)` returning pre-fabricated `ASRSegment`s and `WordToken`s. Check `mock_transcriber.unload.assert_called_once()`.
  - Mock Aligner: Pass a `MagicMock(spec=ForcedAligner)` whose `align_chunks` returns deterministic `WordToken`s.
  - Mock Silero-VAD: Monkeypatch `extract_vad_silences` in `pipeline.py` to return deterministic silences `[(0.0, 0.4), (2.0, 2.5)]` without loading `faster_whisper`.
  - With this setup, all tests run in < 0.5 seconds on pure CPU without PyTorch or external dependencies.

--------------------------------------------------------------------------------

## 3. Caveats

1. `ForcedAligner.align_chunks` vs separate Stage 5/6: In Increment 4, `align_chunks` was designed to slice chunk audio, call the backend, and reconcile the global timeline all inside `align_chunks`. In `run_speech_pipeline`, delegating directly to `aligner.align_chunks(...)` satisfies both stages while maintaining full backwards compatibility.
2. `faster-whisper` absence in base environment: The base test environment intentionally lacks `faster-whisper`. Any test invoking `run_speech_pipeline` with `transcript=None` MUST either provide a mock `transcriber` and mock/patch `extract_vad_silences` or test the failure mode when dependencies are absent.
3. Transcript without ASR: When a user provides `--transcript`, speech recognition is skipped. The pipeline slices the text tokens uniformly across the audio duration as seed segments for `partition_into_chunks`, which are then force-aligned by `align_chunks`.

--------------------------------------------------------------------------------

## 4. Conclusion

1. **Architecture Ready**: The existing modules (`audio.py`, `asr.py`, `chunker.py`, `aligner.py`) provide all lower-level primitives needed for the 7-stage speech pipeline.
2. **Key Additions Needed in `src/subtitle_workbench/`**:
   - `text_norm.py`: Add `normalize_transcript(transcript: str) -> list[TokenSpan]` wrapping `normalize_text_spans`.
   - `audio.py`: Add `get_duration(path: Path | str) -> float` helper.
   - `export.py`: Implement `format_vtt_timestamp`, `export_karaoke_vtt`, `export_jsonld`, `export_raw_alignment`, and `generate_manifest`.
   - `pipeline.py`: Implement `run_speech_pipeline(...)` with all 7 execution stages, strict VRAM `unload()` cleanup in `finally`, file overwrite protection, and manifest generation.
   - `cli.py`: Support `align-speech` and `align-dtw` subcommands alongside root flags.
   - `__init__.py`: Export new symbols.
3. **Comprehensive Test Suite Plan (`tests/test_pipeline_speech.py`)**:
   - `test_run_speech_pipeline_mocked_end_to_end`: Verifies all 7 stages, file contents on disk (`.vtt`, `.jsonld`, `alignment_raw.json`, `manifest.json`), and `unload()` call.
   - `test_run_speech_pipeline_with_explicit_transcript`: Verifies ASR bypass when transcript string or file is provided.
   - `test_run_speech_pipeline_file_overwrite_protection`: Rejects duplicate run when output directory already contains artifacts.
   - `test_run_speech_pipeline_output_overwrites_input`: Rejects collision when output path equals input WAV.
   - `test_run_speech_pipeline_missing_audio`: Verifies `FileNotFoundError`.
   - `test_run_speech_pipeline_corrupt_audio`: Verifies `AudioFormatError` / `ValueError`.
   - `test_run_speech_pipeline_vram_cleanup_on_error`: Verifies `unload()` is invoked even if transcription fails.
   - `test_cli_align_speech_success`: Verifies CLI exit code 0 and stderr diagnostics.
   - `test_cli_align_speech_validation_failure`: Verifies CLI exit code 2 on missing arguments or invalid inputs.

--------------------------------------------------------------------------------

## 5. Verification Method

To independently verify these observations and design conclusions:

1. **Verify Baseline Test Suite Execution**:
   ```pwsh
   uv run --locked pytest
   ```
   Expected: 446 passed, 1 skipped in ~4.37s.

2. **Verify Missing `normalize_transcript`**:
   ```pwsh
   git grep "normalize_transcript"
   ```
   Expected: Zero occurrences in `src/` (confirming it must be added).

3. **Verify Existing `ForcedAligner.align_chunks` Interface**:
   Inspect lines 54-87 and 175-181 in `src/subtitle_workbench/aligner.py` to confirm that `align_chunks` accepts `(chunks, audio_path, transcripts=None, engine="auto", fallback_to_ctc=True)` and returns globally reconciled `list[WordToken]`.

4. **Verify Existing VRAM Cleanup Pattern**:
   Inspect lines 334-350 in `src/subtitle_workbench/asr.py` to confirm `WhisperTranscriber.unload()` and `__enter__` / `__exit__`.

5. **Invalidation Conditions**:
   - If `ForcedAligner.align_chunks` did not reconcile chunk alignments internally, `reconcile_chunk_alignments` would have to be explicitly called in `pipeline.py`.
   - If `extract_vad_silences` had a pure-NumPy fallback, mocking it in tests would not be mandatory; however, line 408 in `asr.py` proves it requires `faster-whisper`, so mock/patching is strictly necessary for offline CPU tests.
