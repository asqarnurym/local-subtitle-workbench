# Original User Request

## 2026-10-16T22:00:03Z

This is a single self-contained fix; keep it small and focused. Implement Increment 1 of the "Local Subtitle Alignment Workbench": speech data contracts and word-span token normalizer with reversible cue projection.

Working directory: `C:\Users\nurym\Desktop\local-subtitle-workbench`
Branch: `feature/increment-1-speech-models-and-norm`
Integrity mode: demo

## Context & Standards
- Target environment: Windows 11, Python 3.11/3.12, `uv`, `hatchling`, `pytest`, `ruff`.
- Author / Context: Askar Nurym (Master's Thesis AITU, OP 7M06105, supervisor Prof. T. Zhukabayeva).
- Ground rules: Follow `.agents/PROJECT_CONTEXT.md`, `.agents/RULES.md`, `docs/SDLC_PROCESS.md`, `docs/ARCHITECTURE.md`, and `docs/ANTI_FALSIFICATION.md`. Work strictly on branch `feature/increment-1-speech-models-and-norm` (do not switch to `main`).

## Requirements

### R1. Speech Data Contracts & Boundary Validation (`src/subtitle_workbench/models.py`)
Add and strictly type speech data classes with defensive input boundary validation:
- `PhonemeCue`: `phoneme: str`, `start: float`, `end: float`, `confidence: float`
- `WordToken`: `id: str`, `text: str`, `normalized: str`, `start: float`, `end: float`, `confidence: float`, `phonemes: list[PhonemeCue] = field(default_factory=list)`, `char_start: int | None = None`, `char_end: int | None = None`
- `ASRSegment`: `id: str`, `start: float`, `end: float`, `text: str`, `words: list[WordToken]`
- `AlignmentResult`: `words: list[WordToken]`, `phonemes: list[PhonemeCue]`, `alignment_method: str`, `path_cost: float`, `evaluated_cells: int`
- Validation logic: Reuse and enforce `finite_number` helper, strictly forbid `NaN`, `inf`, and `bool` values in numerical fields, enforce `0.0 <= start < end`, validate non-empty ASCII identifiers, and forbid control characters in textual fields.

### R2. Token-Span Text Normalization & Reverse Cue Projection (`src/subtitle_workbench/text_norm.py`)
Implement bidirectional token normalizer with character span tracking:
- `TokenSpan`: dataclass capturing `token: str`, `normalized: str`, `char_start: int`, `char_end: int`.
- `normalize_text_spans(text: str) -> list[TokenSpan]`:
  - Contraction expansion (`"don't"` -> `"do"`, `"not"`; `"I'm"` -> `"I"`, `"am"`).
  - Number-to-words expansion (`"21"` -> `["twenty", "one"]`), mapping both expanded tokens to original character span.
  - Hyphenated words (`"end-to-end"`), academic abbreviations (`"API"`, `"CPU"`).
  - Punctuation stripping and whitespace cleaning without desynchronizing character offsets.
  - Lowercasing for CMUDict / MFA phonetic dictionary compatibility.
- `project_tokens_to_cues(tokens: list[WordToken], original_text: str) -> list[Cue]`:
  - Project normalized token timestamps back onto display subtitle cue structures (`Cue`) for WebVTT export.

### R3. Infrastructure & Packaging Discipline
- Base package must remain lightweight: standard library + NumPy only (no heavy torch or faster-whisper dependencies in base package).
- Complete offline safety: no network calls during test execution or packaging.

### R4. Comprehensive Test Coverage (`tests/test_text_norm.py`, `tests/test_speech_models.py`)
- `tests/test_text_norm.py`: Test sentences with numbers, contractions, hyphenated words, acronyms; enforce invariant that `original_text[span.char_start:span.char_end]` accurately retrieves the original token; test edge cases (empty strings, multiple whitespace, boundary punctuation).
- `tests/test_speech_models.py`: Test boundary and negative cases for all new models (invalid intervals, negative times, NaN/inf, invalid types, malformed IDs).

## Acceptance Criteria

### Automated Verification
- [ ] 100% pass rate across all 72 existing tests plus all new unit tests (`uv run --locked pytest`)
- [ ] Zero ruff linter issues (`uv run --locked ruff check .`)
- [ ] Zero ruff formatting diffs (`uv run --locked ruff format --check .`)
- [ ] Clean wheel package build without isolation and without network access (`uv run --locked python -m build --wheel --no-isolation`)
- [ ] Clean git commit created on branch `feature/increment-1-speech-models-and-norm` with message:
  `feat(speech): implement speech data models and token-span text normalizer`
- [ ] Zero synthetic metrics, fabricated claims, or unverified assertions.

## 2026-10-20T03:38:21Z

This is a single self-contained fix; keep it small and focused.
Реализовать Инкремент 2 проекта «Local Subtitle Alignment Workbench»: модуль ASR (Faster-Whisper Large-v3 INT8) и детектор пауз Silero-VAD с детерминированным управлением памятью GPU (VRAM lifecycle) и соблюдением стандартов ECC (TDD Workflow, Error Handling, Verification Loop).

Working directory: C:\Users\nurym\Desktop\local-subtitle-workbench
Git branch: feature/increment-2-asr-and-vad
Integrity mode: demo

## Context & Hardware Bounds
- Работать строго в ветке feature/increment-2-asr-and-vad.
- База: уже реализованные и проверенные 261 тестом модели WordToken, PhonemeCue, ASRSegment в models.py и нормализатор text_norm.py.
- Аппаратные ограничения: NVIDIA GeForce RTX 3050 Laptop GPU (4 ГБ VRAM). Модель Faster-Whisper Large-v3 INT8 занимает ~1.85 ГБ VRAM.
- Обязательно строгое управление жизненным циклом памяти GPU (метод unload: удаление ссылки на модель, gc.collect(), torch.cuda.empty_cache()), исключающее утечки между вызовами.

## Requirements

### R1. Опциональные зависимости в pyproject.toml
- Добавить опциональную группу зависимостей speech в pyproject.toml:
  ```toml
  [project.optional-dependencies]
  speech = [
      "faster-whisper>=1.0.0",
      "torch>=2.2.0",
  ]
  ```
- Базовый прогон uv run --locked pytest обязан проходить офлайн на CPU без установленного torch и faster-whisper. Все импорты тяжелых библиотек должны быть изолированы/ленивыми, чтобы базовый дистрибутив оставался легковесным.

### R2. Модуль ASR и VAD (src/subtitle_workbench/asr.py)
- Иерархия исключений (согласно ECC Error Handling):
  - Базовый класс: ASRError(Exception).
  - Подклассы: AudioFormatError(ASRError), ASRInferenceError(ASRError), VRAMAllocationError(ASRError).
- Класс WhisperTranscriber:
  - Автовыбор устройства и квантизации: device="cuda" if torch.cuda.is_available() else "cpu", compute_type="int8_float16" для CUDA (или "int8" для CPU) — гарантирует соблюдение лимита памяти <= 1.85 ГБ.
  - Поддержка параметров Silero-VAD: vad_filter=True, min_silence_duration_ms=400.
  - Метод transcribe(audio_path: Path, language: str = "en") -> list[ASRSegment]:
    - Валидация входного WAV (моно PCM16 16000 Гц) через существующий audio.py.
    - Инференс Faster-Whisper с word_timestamps=True.
    - Приведение результатов к типизированным ASRSegment и WordToken из models.py.
    - Связывание отображаемого слова с нормализованной формой через normalize_text_spans из text_norm.py.
  - Метод unload() -> None:
    - Очистка ссылки на модель (del self._model или эквивалент), вызов gc.collect(), вызов torch.cuda.empty_cache() (при наличии CUDA).
- Функция извлечения пауз:
  - extract_vad_silences(audio_path: Path) -> list[tuple[float, float]] для получения интервалов тишины (используется для Macro-DTW в Инкременте 3).
- Экспорт публичного API:
  - Экспортировать WhisperTranscriber, extract_vad_silences, и классы ошибок в src/subtitle_workbench/__init__.py.

### R3. Комплекс модульных и контрактных тестов (tests/test_asr.py)
- Применять методологию TDD: тесты контрактов пишутся до реализации.
- Контрактные тесты: валидность структуры ASRSegment, упорядоченность WordToken (0 <= start < end), корректные положительные таймкоды.
- Тесты граничных условий и отказов: несуществующий аудиофайл, поврежденный WAV, неподдерживаемая частота дискретизации или количество каналов (AudioFormatError).
- Тесты жизненного цикла VRAM: проверка вызова unload() и освобождения ресурсов.
- Офлайн-изоляция для CI: реализация фикстурного dummy-бэкенда Faster-Whisper, позволяющего запускать полный набор тестов на CPU без скачивания весов нейросети.
- Опциональный интеграционный тест с реальной моделью (если faster-whisper установлен локально), защищенный pytest.mark.skipif.

### R4. Документирование отчёта по инкременту
- Создать файл отчёта docs/increments/INCREMENT_2_ASR_AND_VAD.md на основе docs/increments/TEMPLATE_INCREMENT_REPORT.md.
- Зафиксировать: цели, архитектурные решения по VAD и VRAM, инвентарь изменений, доказательства прохождения тестов (261 + новые тесты), вывод линтера/форматтера, статус коммита.

## Acceptance Criteria

### Verification & Quality Gates
- [ ] Все существующие 261 тест + новые тесты ASR проходят на 100%:
  uv run --locked pytest
- [ ] Линтер проходит без единого замечания:
  uv run --locked ruff check .
- [ ] Форматирование кода полностью соответствует правилам:
  uv run --locked ruff format --check .
- [ ] Сборка wheel-пакета проходит успешно:
  uv run --locked python -m build --wheel --no-isolation
- [ ] Создан коммит в ветке feature/increment-2-asr-and-vad с точным сообщением:
  git commit -m "feat(asr): implement faster-whisper transcriber and vad silence extractor with vram lifecycle"
- [ ] Оформлен отчёт docs/increments/INCREMENT_2_ASR_AND_VAD.md.


## 2026-10-20T14:46:16Z

Implement Increment 3 for the "Local Subtitle Alignment Workbench" project: Bounded Chunker (chunk duration L <= 30.0s), Contextual Overlap Padding (0.5s), and Global Monotonic Alignment Reconciler to eliminate cumulative timestamp drift on long educational recordings (10–60 minutes) while strictly maintaining linear memory complexity.

Working directory: `C:\Users\nurym\Desktop\local-subtitle-workbench`
Git branch: `feature/increment-3-macro-dtw-chunking`
Integrity mode: development

## Requirements

### R1. Macro-Chunking Data Models & Contracts (`src/subtitle_workbench/models.py`)
- Implement immutable dataclass `AudioChunk` with fields: `id: str`, `index: int`, `start: float`, `end: float`, `padded_start: float`, `padded_end: float`, `text: str`, `words: list[WordToken]`.
- Implement immutable dataclass `ChunkConfig` with configurable thresholds: `max_chunk_duration: float = 30.0`, `min_chunk_duration: float = 1.0`, `overlap_padding: float = 0.5`, `min_silence_duration: float = 0.4`.
- Validate all numerical fields are finite and non-negative, satisfying strict invariants: `0.0 <= padded_start <= start < end <= padded_end`. Ensure identifiers are valid ASCII non-empty strings and words are valid `WordToken` instances.
- Export `AudioChunk` and `ChunkConfig` in `src/subtitle_workbench/__init__.py`.

### R2. Macro-Segmentation & Monotonic Alignment Reconciler (`src/subtitle_workbench/chunker.py`)
- Define typed exceptions `ChunkingError` and `MonotonicityError` with clear diagnostic context.
- Implement `partition_into_chunks(segments: list[ASRSegment], silences: list[tuple[float, float]], total_duration: float, config: ChunkConfig | None = None) -> list[AudioChunk]`:
  - Partition continuous audio stream into sequential chunks strictly bounded by `end - start <= max_chunk_duration` (30.0s).
  - Prioritize split points on natural pauses from VAD (`silences` with pause duration >= `min_silence_duration`), then ASR sentence segment boundaries.
  - Fallback: for speech segments longer than 30.0s without silence pauses, partition along word boundaries with the lowest acoustic/pause interval.
  - Calculate symmetric overlap padding (`overlap_padding = 0.5s`), clamped strictly within `[0.0, total_duration]`: `padded_start = max(0.0, start - padding)`, `padded_end = min(total_duration, end + padding)`.
- Implement `reconcile_chunk_alignments(chunks: list[AudioChunk], chunk_aligned_words: list[list[WordToken]]) -> list[WordToken]`:
  - Translate local chunk timestamps into document global timeline: `t_global = chunk.start + t_local`.
  - Discard word tokens located inside overlap padding seams to eliminate boundary duplication.
  - Guarantee strict global monotonicity (`word[i+1].start >= word[i].end` or onset order); raise `MonotonicityError` if chronology is corrupted.
  - Safeguard against zero-duration words and division-by-zero errors.
- Export chunker symbols in `src/subtitle_workbench/__init__.py`.

### R3. Comprehensive Test Suite (`tests/test_chunker.py`)
- Zero mocks on pure chunking and alignment reconciliation business logic.
- Verify `partition_into_chunks`:
  - Strict `<= 30.0s` duration limit on synthetic segment sequences (10–60 minutes).
  - Natural anchor selection preference using VAD silences.
  - Padding clamping at temporal boundaries (`t = 0.0` has `padded_start == 0.0`, `t = total_duration` has `padded_end == total_duration`).
  - Fallback chunking on long continuous speech lacking pauses.
- Verify `reconcile_chunk_alignments`:
  - Correct coordinate transformation from local chunk time to global timeline.
  - Seamless token deduplication at overlap borders.
  - Strict monotonicity verification and error handling (`MonotonicityError`).

### R4. Increment 3 SDLC Audit Report (`docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md`)
- Complete report based on `docs/increments/TEMPLATE_INCREMENT_REPORT.md`.
- Document anchor selection algorithm, overlap padding design rationale, test metrics, verification logs, and architectural trade-offs.

## Acceptance Criteria

### Automated Verification Gates
- [ ] All 314 existing tests continue to pass without regression: `uv run --locked pytest`
- [ ] All new tests in `tests/test_chunker.py` pass with 100% success rate.
- [ ] Zero ruff lint errors: `uv run --locked ruff check .`
- [ ] Zero ruff formatting issues: `uv run --locked ruff format --check .`
- [ ] Offline wheel build completes successfully: `uv run --locked python -m build --wheel --no-isolation`
- [ ] Git commit created on branch `feature/increment-3-macro-dtw-chunking` with message: `feat(chunker): implement bounded chunk partitioner and monotonic alignment reconciler`
- [ ] Audit document `docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md` created with complete execution evidence.


## 2026-10-26T00:58:19Z

Implement Increment 5 of the "Local Subtitle Alignment Workbench" project: standardized accessibility exporters (W3C WebVTT Karaoke, schema.org JSON-LD, Raw Alignment Dump, SHA-256 Manifest) and an end-to-end speech alignment pipeline with CLI integration.

Working directory: C:\Users\nurym\Desktop\local-subtitle-workbench
Integrity mode: development

## Environment and Constraints

- Repository: `C:\Users\nurym\Desktop\local-subtitle-workbench`
- Target Branch: `feature/increment-5-exporters-and-pipeline` (branched from `feature/increment-4-forced-alignment`)
- Hardware Constraints: AMD Ryzen 9 5900HX, NVIDIA RTX 3050 Laptop GPU (4 GB VRAM, peak sequential budget <= 1.85 GB), Windows 11.
- Unit and integration tests must execute offline on CPU in < 5 seconds without network calls and without requiring external model weights download (use mocks/stubs for inference runners).
- Zero-Emoji Discipline: strictly no emojis or graphical Unicode icons in code, comments, docstrings, logs, git commits, or reports. Use clean ASCII formatting only (`[+]`, `[-]`, `[*]`, `[OK]`, `[FAIL]`, `->`, `|`).

## Requirements

### R1. Standardized Accessibility Exporters (`src/subtitle_workbench/export.py`)
- Implement `format_vtt_timestamp(seconds: float) -> str`: formats seconds to `HH:MM:SS.mmm` with validation for nonnegative finite numbers.
- Implement `export_karaoke_vtt(words: list[WordToken], max_line_words: int = 8, max_line_chars: int = 42, max_pause_break: float = 1.0) -> str`: generates valid W3C WebVTT documents with cue-level inline karaoke word tags (`<c.word><timestamp>text</c>`), segmenting cues by word count limit, character count limit, and pause breaks. Handle empty input gracefully (`WEBVTT\n\n`) and ensure monotonic timestamps.
- Implement `export_jsonld(words: list[WordToken], audio_duration: float, media_urn: str, language: str = "en") -> dict`: generates semantic schema.org JSON-LD (`VideoObject` with `Clip` parts) matching W3C WCAG 2.1 Media Accessibility Guidelines and ISO 8601 duration `PT...S`.
- Implement `export_raw_alignment(words: list[WordToken], audio_path: Path | str, alignment_method: str, metrics: dict | None = None) -> dict`: exports hierarchical alignment structure (words and nested phonemes with timing and confidence) and aggregate summary metrics (mean word/phoneme confidence, speech-to-pause ratio).
- Implement `generate_manifest(input_audio_path: Path, output_dir: Path, words: list[WordToken], metrics: dict, config: dict | None = None) -> dict`: generates cryptographic provenance audit log `manifest.json` with SHA-256 hashes of input WAV and all generated outputs (`subtitles.vtt`, `timeline.jsonld`, `alignment_raw.json`), incorporating `code_provenance()`.

### R2. End-to-End Speech Alignment Orchestrator (`src/subtitle_workbench/pipeline.py`)
- Implement `run_speech_pipeline(audio_path, output_dir, transcript=None, engine="auto", vad_silence_min_sec=0.4, max_chunk_sec=30.0, chunk_padding_sec=0.5, fallback_to_ctc=True, transcriber=None, aligner=None) -> dict`.
- Pipeline Execution Stages:
  1. Audio Validation: verify file existence and PCM16 WAV format via `audio.validate_wav`.
  2. VAD & ASR: if transcript not supplied, extract silences via `extract_vad_silences` and transcribe via `WhisperTranscriber`, followed by VRAM cleanup.
  3. Normalization: apply `text_norm.normalize_transcript` preserving word mappings.
  4. Macro-chunking: partition into chunks via `chunker.partition_into_chunks` (<= 30s limit, 0.5s padding).
  5. Forced Alignment: slice chunk audio via `audio.slice_wav` and align via `ForcedAligner.align_chunks`.
  6. Global Reconciliation: stitch chunk alignments via `chunker.reconcile_chunk_alignments`.
  7. Artifact Export: create output directory and write `subtitles.vtt`, `timeline.jsonld`, `alignment_raw.json`, and `manifest.json`.
- Return execution manifest dictionary with runtime metrics.

### R3. CLI Interface Extension (`src/subtitle_workbench/cli.py`)
- Support subcommands via `argparse.ArgumentParser`:
  - `align-speech <audio_wav> -o <output_dir> [--engine auto|mfa|ctc] [--transcript <text_or_path>]`
  - Backward compatibility: preserve existing DTW alignment under `align-dtw <ref_wav> <target_wav> <cues_json> -o <output_dir>` as well as direct root flags `--reference`, `--target`, `--cues`, `--output`.
- Return exit code 0 on success, exit code 2 on validation/contract errors with descriptive error messages to stderr.

### R4. Automated Unit & Integration Tests
- Extend `tests/test_export.py`: verify karaoke VTT tag syntax, line splitting rules, JSON-LD schema compliance, raw alignment structure, and SHA-256 manifest verification.
- Create `tests/test_pipeline_speech.py`: end-to-end pipeline test on synthetic WAV with mock transcriber and mock aligner, output file integrity checks, error handling tests for missing files and output overwrite protection, and CLI subprocess execution test.

### R5. Increment Report Documentation (`docs/increments/INCREMENT_5_EXPORTERS_AND_PIPELINE.md`)
- Complete Increment 5 SDLC report based on `docs/increments/TEMPLATE_INCREMENT_REPORT.md`, documenting architectural decisions, file inventory, quality gate execution logs, and boundary condition coverage.

## Acceptance Criteria

### Automated Verification Gates
- [ ] 100% test pass rate across all existing 446 tests and new Increment 5 tests: `uv run --locked pytest`
- [ ] Zero ruff lint errors: `uv run --locked ruff check .`
- [ ] Zero ruff formatting errors: `uv run --locked ruff format --check .`
- [ ] Package wheel builds without isolation: `uv run --locked python -m build --wheel --no-isolation`
- [ ] Offline installed-wheel smoke test succeeds: `uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out`

### Git & SDLC Deliverables
- [ ] Clean working tree on branch `feature/increment-5-exporters-and-pipeline`.
- [ ] Atomic git commits following Conventional Commits specification:
  - `feat(export): implement WebVTT karaoke, schema.org JSON-LD, raw alignment, and manifest exporters`
  - `feat(pipeline): wire end-to-end speech alignment pipeline and CLI subcommands`
  - `docs(sdlc): formalize Increment 5 verification report and audit logs`
- [ ] Completed increment documentation at `docs/increments/INCREMENT_5_EXPORTERS_AND_PIPELINE.md`.


## 2026-10-26T03:14:07Z

# Teamwork Project Prompt -- Increment 6 Implementation

Implement Increment 6 for the "Local Subtitle Alignment Workbench" project: Automated Empirical Benchmark Suite, Statistical Analysis (Clustered Bootstrap, Paired Wilcoxon), and publication LaTeX table generation for Paper 2 in "Scientific Journal of Astana IT University".

Working directory: C:\Users\nurym\Desktop\local-subtitle-workbench
Integrity mode: development

## Scientific Mission and Constraints
- Git branch: Create and checkout `feature/increment-6-speech-benchmark` from `feature/increment-5-exporters-and-pipeline`.
- Objective: Provide empirical proof of the hybrid alignment method (Whisper + Bounded DTW + Montreal Forced Aligner) against Whisper baseline and CTC Trellis, targeting <= 20 ms human acoustic noise threshold on TIMIT Core Test and <= 50 ms imperceptibility threshold (ITU-R BT.1359-1 / EBU R37).
- Corpora: TIMIT Core Test (NIST 192 sentences, 24 speakers) and Buckeye Speech Corpus. Legacy 24-video archive is strictly excluded.
- Hardware constraints: AMD Ryzen 9 5900HX, NVIDIA RTX 3050 Laptop GPU (4 GB VRAM, sequential peak <= 1.85 GB), Windows 11.
- Zero-Emoji rule: No emojis or graphical Unicode icons anywhere in code, comments, docstrings, logs, git commits, or reports. Pure ASCII ([+], [-], [*], [OK], [FAIL], ->, |).

## Requirements

### R1. Reference Corpora Loader and Parser (`scripts/download_reference_corpora.py`)
- Parse TIMIT `.phn` files (`parse_timit_phn`) to `list[PhonemeCue]`, mapping samples to seconds ($t = \text{sample} / 16000.0$) and filtering silence markers (`h#`, `pau`, `epi`).
- Parse TIMIT `.wrd` files (`parse_timit_wrd`) to `list[WordToken]`.
- Parse Buckeye Speech Corpus Praat TextGrids (`parse_buckeye_textgrid`) using `mfa_wrapper.parse_textgrid`.
- Provide `stage_synthetic_benchmark(target_dir: Path) -> Path` generating an offline synthetic dataset (10 utterances with exact mathematical ground-truth boundaries) for deterministic unit testing without external downloads.

### R2. Alignment Metrics and Statistical Analysis Module (`src/subtitle_workbench/metrics.py`)
- Implement frozen dataclass `AlignmentEvaluationResult` capturing word and phone MAE, MedAE, RMSE, Acc@20ms, Acc@50ms, Acc@100ms, RTF, peak VRAM, and 95% bootstrap confidence intervals.
- Implement `evaluate_alignment_boundaries(pred_tokens, ref_tokens, tolerance_ms=20.0)` for token matching and metrics computation.
- Implement `clustered_bootstrap_ci(errors, clusters, num_resamples=2000, alpha=0.05, seed=42)` for speaker/utterance cluster-robust 95% confidence intervals.
- Implement `paired_wilcoxon_test(errors_baseline, errors_proposed)` computing W-statistic, p-value, and Cliff's Delta effect size.
- Ensure strict division-by-zero protection and typed exceptions (`BenchmarkError`, `CorpusFormatError`, `MetricComputationError`).

### R3. Speech Benchmark Suite Runner (`scripts/speech_benchmark.py`)
- CLI runner supporting `--corpus timit --data-dir <path> --output-dir <path> [--offline-synthetic]`.
- Perform three-way ablation:
  * Mode 1 (Baseline): Whisper Large-v3 INT8 internal timestamps (`word_timestamps=True`).
  * Mode 2 (CTC Trellis): Whisper ASR + MMS_FA forced alignment.
  * Mode 3 (Proposed Hybrid): Whisper ASR + Bounded DTW + Montreal Forced Aligner.
- Record Real-Time Factor (RTF), peak VRAM, and host RAM.
- Output structured report `reports/benchmark/benchmark_results.json` and cryptographic `manifest.json`.

### R4. Publication LaTeX Table Generator (`scripts/generate_paper_tables.py`)
- Ingest `reports/benchmark/benchmark_results.json`.
- Generate production-quality `booktabs` LaTeX tables:
  * Table 1: Alignment Accuracy comparison on TIMIT Core Test (Word/Phone MAE, Acc@20ms, Acc@50ms, Acc@100ms, 95% CI).
  * Table 2: Computational Performance (RTF, peak VRAM, peak RAM on RTX 3050 Laptop GPU).
  * Table 3: Statistical Significance (Wilcoxon W, p-value, Cliff's Delta).
- Save tables to `docs/paper/table_alignment_accuracy.tex` and `docs/paper/table_computational_performance.tex`.

### R5. Unit Test Suite (`tests/test_benchmark.py`)
- Comprehensive tests for TIMIT `.phn` and `.wrd` parsers on synthetic data.
- Oracle boundary tests for MAE, MedAE, Acc@20ms, Acc@50ms with fixed offsets (+15 ms, +25 ms, +60 ms).
- Clustered bootstrap reproducibility and coverage tests.
- Paired Wilcoxon hypothesis rejection tests.
- LaTeX table syntax validation tests.
- Execution requirement: 100% offline on CPU in < 5 seconds.

### R6. SDLC Increment Report (`docs/increments/INCREMENT_6_EMPIRICAL_BENCHMARK.md`)
- Formalize increment report following `docs/increments/TEMPLATE_INCREMENT_REPORT.md`.
- Document benchmark methodology, statistical equations, test counts, execution logs, and LaTeX table snippets.

## Acceptance Criteria

### Test Suite and Code Quality
- [ ] All existing 637 tests + all new benchmark tests pass: `uv run --locked pytest`
- [ ] Linter passes with 0 warnings: `uv run --locked ruff check .`
- [ ] Formatter passes: `uv run --locked ruff format --check .`
- [ ] Offline benchmark run succeeds: `uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/benchmark_demo`
- [ ] Package wheel build and smoke verification succeed:
      `uv run --locked python -m build --wheel --no-isolation`
      `uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out`
- [ ] Git commit history on branch `feature/increment-6-speech-benchmark` contains atomic commits:
      - `feat(benchmark): implement reference corpora loaders and boundary evaluation metrics`
      - `feat(benchmark): implement clustered bootstrap, paired Wilcoxon tests, and benchmark runner`
      - `feat(paper): implement LaTeX table generator for Publication 2`
      - `docs(sdlc): formalize Increment 6 verification report and audit logs`
- [ ] Formal increment report committed at `docs/increments/INCREMENT_6_EMPIRICAL_BENCHMARK.md`.
