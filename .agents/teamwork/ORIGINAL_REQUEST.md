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
