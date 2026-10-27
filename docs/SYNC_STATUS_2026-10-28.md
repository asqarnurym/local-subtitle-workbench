# Статус синхронизации: ноутбук ↔ облако, 2026-10-28

Режим: только чтение. Код, документы, git-индекс и файлы данных не менялись. Коммитов и пушей не было. Единственный записанный файл — этот отчёт. Ветка: `fix/benchmark-integrity`.

## 1. Облако ↔ ноутбук (md5 ключевых файлов)

Доступа к `~/lsw` с ноутбука нет, поэтому сравнить с облаком в этой сессии нельзя. Ниже только локальные md5. Колонка «облако» не заполнена: значения пользователь не передавал, и сравнение не выполнялось.

| Файл | md5 (ноутбук) | облако |
|---|---|---|
| src/subtitle_workbench/anchoring.py | 87345ffa7bd00f12f0e580a304b413f7 | не проверено |
| src/subtitle_workbench/aligner.py | 72096d4d4a611a76bc6b3fb9c53bb88e | не проверено |
| src/subtitle_workbench/mfa_wrapper.py | 558548fa775e4912c9b4a845d24313ef | не проверено |
| src/subtitle_workbench/buckeye.py | 9a5acba540d8ef25762254c7e234fe5e | не проверено |
| scripts/speech_benchmark.py | 38d23a669bf2756d77d38d7b25b9cebc | не проверено |
| docs/RUNBOOK.md | 282f54ff79bb77ab529ce1b731104378 | не проверено |
| docs/IMPROVEMENT_PLAN.md | c5a1bbe7dce9cfef1839855892949ae0 | не проверено |
| pyproject.toml | 8a0d00bb5e4296fb69d054b80b04f7aa | не проверено |

Не проверено:
- Полное сравнение дерева (его не было и здесь).
- Файлы проекта «AIML Article» в облаке: `docs/improvement-plan.md` и `docs/validation-audit-2026-10-27.md`. Они могут устареть относительно `docs/RUNBOOK.md` и `docs/IMPROVEMENT_PLAN.md`. Ни один из них не открывался.

## 2. Состояние git

Текущая ветка: `fix/benchmark-integrity`. Последние коммиты:

```
c7656b1 feat(aligner): enforce strict MFA engine execution, eliminate silent CTC fallback, and benchmark 3-mode ablation with native MFA
4329863 docs(benchmark): record empirical benchmark metrics and publication tables for LibriSpeech and L2-ARCTIC
b11ddf2 feat(benchmark): support pairwise Wilcoxon and table generation for CTC vs Whisper
```

`git status --short`: 76 записей. Группировка:

**Код (`src/`)**, изменён: aligner, api, asr, chunker, cli, corpora, metrics, mfa_wrapper, pipeline.
**Код, новый (не отслеживается):** `src/subtitle_workbench/anchoring.py`, `buckeye.py`, `phone_sets.py`.

**Скрипты (`scripts/`)**, изменены: download_open_benchmark_data.py, download_reference_corpora.py, generate_paper_tables.py, speech_benchmark.py.
**Скрипты, удалены:** compile_manuscript_docx.py, real_run_smoke.py.

**Тесты (`tests/`)**, изменены: test_aligner, test_api, test_asr, test_benchmark, test_challenger_m2_1, test_challenger_m2_2, test_metrics_stress, test_mfa_wrapper, test_pipeline_speech.
**Тесты, удалён:** test_challenger_m2_iter2.py.
**Тесты, новые:** conftest.py, test_anchoring.py, test_reference_corpora.py.

**Документы, изменены:** .agents/PROJECT_CONTEXT.md, .agents/RULES.md, README.md, docs/ANALOGS_BACKLOG.md, ANTI_FALSIFICATION.md, ARCHITECTURE.md, CLAIM_LEDGER.csv, CORPORA_TAXONOMY.md, LITERATURE_EVIDENCE_BASE.md, PROTOTYPE_CROSS_ANALYSIS_AND_IDEAS.md, RESEARCH_STRATEGY.md, SCIENTIFIC_JUSTIFICATION_AND_METRICS_TAXONOMY.md, SDLC_PROCESS.md, VALIDATION.md.
**Документы, новые:** docs/IMPROVEMENT_PLAN.md, docs/RUNBOOK.md.
**Документы, удалены:** docs/RUNBOOK_REAL_BENCHMARK.md; весь `docs/increments/` (9 файлов); `docs/paper/archive/` (8 файлов, включая .docx и .tex статьи 2); таблицы `docs/paper/*.tex`, `docs/paper/tables_l2arctic/`, `docs/paper/tables_librispeech/` (по 3 файла в каждой).

**Конфигурация:** pyproject.toml (изменён), uv.lock (изменён). `uv lock --check` проходит (см. раздел 3).

**Удаления, которые выглядят намеренными, но требуют подтверждения:** весь `docs/increments/` и `docs/paper/` с архивом статьи 2 удалены из рабочей копии. Если это не решение, а побочный эффект, их надо вернуть до коммита (`git restore`). Удалять ничего не нужно.

**Случайное / не в git:** `data/` и `reports/` перечислены в `.gitignore` (строки 16–17) и в `git status` не попадают. `reports/` на диске не существует. `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`, `dist/` также игнорируются. В `git status --ignored` найден `.agents/teamwork/explorer_4/__pycache__/`. Что лежит в `dist/`, не проверялось.

**Рекомендации:**
- Закоммитить отдельными коммитами (предложение, решение за пользователем):
  1. код + тесты + lock/pyproject (фаза 1, E1–E11), одним коммитом или по модулям;
  2. документы: новые RUNBOOK.md и IMPROVEMENT_PLAN.md, правки остальных;
  3. удаления (`docs/increments/`, `docs/paper/`, `real_run_smoke.py`, `compile_manuscript_docx.py`, `test_challenger_m2_iter2.py`), только после подтверждения.
- В `.gitignore` ничего добавлять не обязательно: `data/`, `reports/`, кеши и `.venv` уже игнорируются. Если `.agents/teamwork/` должен быть временным, его стоит добавить, но это не проверялось.
- Важно: RUNBOOK §4, пункт 3, требует `code.git_worktree_dirty = false` перед использованием чисел. При 76 незакоммиченных изменениях ни один бенчмарк-прогон нельзя использовать в статье. Коммит нужен до первого реального прогона.

## 3. Проверенные факты

Все команды выполнены в корне репозитория.

**3.1. Согласованность pyproject.toml и uv.lock**
```
uv lock --check
Resolved 83 packages in 1ms
exit=0
```
Extra `speech` (pyproject.toml, строки 16–24) содержит `nvidia-cublas-cu12>=12.4` и `nvidia-cudnn-cu12>=9.1,<10` (условие `sys_platform == 'win32' or sys_platform == 'linux'`). Оба есть.

**3.2. GPU**

Команда из задания:
```
uv run python -c "from subtitle_workbench.asr import whisper_cuda_available; print(whisper_cuda_available())"
False
exit=0
```
Примечание: перед запуском `uv run` переустановил локальный пакет (`Uninstalled 1 package`, `Installed 1 package`). Это побочный эффект uv, на результат не влияет.

Вывод `nvidia-smi` (сокращённо, полностью см. команду):
```
NVIDIA-SMI 617.42   Driver 617.42   CUDA UMD 13.4
GPU 0: NVIDIA GeForce RTX 3050 ...  WDDM   Memory 336MiB / 4096MiB   GPU-Util 0%
```
Драйвер и GPU видны. `whisper_cuda_available()` при этом возвращает `False`. Причина не установлена: не проверялось, видит ли CTranslate2 cuBLAS/cuDNN DLL. Это блокер для B0/B2 (бенчмарк по умолчанию требует `--device cuda`). RUNBOOK §1.1 ожидает `True`.

**3.3. MFA**
```
conda env list   -> /usr/bin/bash: line 1: conda: command not found
which mfa        -> no mfa in (...)
mfa version      -> mfa: command not found   (exit=127)
```
MFA в этой сессии не установлен и не найден. Не устанавливался (по правилам задания).

**3.4. Данные Buckeye**
- `data/corpora/buckeye/staging_stats.json`: `"tracks": 255`, `"speakers": 40`, `"clips": 25038`, `"runs": 51139`, `"too_short": 26101`, `"too_long": 0`. Ожидание 25038 совпадает.
- Число `*.TextGrid`: 25038. Число `*.wav`: 25038. Совпадает.
- В `data/corpora/buckeye/` есть подкаталог `_unpacked/` (не проверялся). Исходные архивы в `C:\Users\nurym\Downloads\BuckeyeCorpus` не открывались.

**3.5. Загрузчик на 3 клипах (без записи в reports/, без Whisper и MFA)**

Функция `parse_buckeye_textgrid` находится в `src/subtitle_workbench/corpora.py` (не в `buckeye.py`). Запуск по первым трём TextGrid:
```
s0101a_0000.TextGrid words= 9  first= 'lived' 0.0–0.2231
s0101a_0001.TextGrid words= 10 first= 'um'    0.0–0.3173
s0101a_0002.TextGrid words= 4  first= 'um'    0.25–0.5504
```
Фонемы тоже читаются (например, `l, ah, v, d` для «lived»). Все три файла распознаны.

**3.6. ruff**
```
uv run ruff check .
All checks passed!
```

**3.7. pytest (без маркера model)**
- Первый прогон: `3 failed, 716 passed` в 40.5 с. Упавшие: `test_cli_download_reference_corpora_offline`, `test_speech_benchmark_cli_offline_synthetic`, `test_speech_benchmark_cli_help_and_options`. Ошибка: `CalledProcessError` на `scripts/speech_benchmark.py --help`.
- Изолированно `tests/test_benchmark.py`: `45 passed`.
- Повторный полный прогон: `719 passed` в 39.9 с.
- Вывод: тесты нестабильны при полном прогоне (причина не найдена). Прямой запуск `speech_benchmark.py --help` возвращает код 0. Надо поймать повтор до статьи.
- Число в документах (717 passed, 1 skipped) не совпадает с текущим прогоном (719 passed). Маркеры и набор тестов могли измениться; не выяснялось.

## 4. Не проверено

- Сравнение с облаком по md5 (см. раздел 1).
- Файлы «AIML Article» в облаке.
- `mfa version` и установка MFA (MFA нет).
- Реальные прогоны Whisper и MFA (по заданию не запускались). Ни одного числа для статьи нет.
- Причина `whisper_cuda_available() = False` при видимом GPU.
- Причина нестабильности трёх тестов в полном прогоне.
- Полный `pytest` с маркерами моделей (запускался только `-m "not model"`).
- Содержимое `dist/`, `data/corpora/buckeye/_unpacked/`, `.agents/teamwork/`.
- Прохождение Buckeye-клипов через сам бенчмарк (`load_buckeye_utterances`) не проверялось, только парсер TextGrid.

## 5. Расхождения документов с фактами

1. **IMPROVEMENT_PLAN.md, §1 (Фаза 1):** заголовок «ВЫПОЛНЕНО (27.10.2026, кроме проверки на GPU)». По факту GPU-проверка провалена (`False`). E1 в таблице помечен «проверить на ноутбуке». Заголовок стоит переписать: «код выполнен, GPU не подтверждён».
2. **IMPROVEMENT_PLAN.md, §1:** «717 passed, 1 skipped» в ожиданиях пользователя; текущий полный прогон даёт `719 passed`, а первый прогон `716 passed, 3 failed`. Число для статьи не фиксировать, пока тесты нестабильны.
3. **RUNBOOK.md, §4, пункт 3** (`git_worktree_dirty = false`) не выполнимо при 76 незакоммиченных файлах. Документ этого не отмечает.
4. **RUNBOOK.md, §1.1:** ожидаемое значение `True`; факт `False`. Раздел описывает, что делать, но не отмечает, что сейчас не работает.
5. **IMPROVEMENT_PLAN.md, §2.1:** TIMIT-sample описан как «скачивается скриптом»; по заданию он не скачан. Расхождения между текстом и состоянием нет, это просто не выполнено.
6. **IMPROVEMENT_PLAN.md, §1 (E9):** в тексте «загрузчик Buckeye: нативный `.words/.phones` → клипы», в то время как `speech_benchmark.py` читает TextGrid через `parse_buckeye_textgrid`. Оба формата есть в клипах (`.TextGrid` и `.txt`), противоречия по сути нет, но стоит уточнить, что источник для бенчмарка — TextGrid.
7. **Облачные файлы «AIML Article»** (`docs/improvement-plan.md`, `docs/validation-audit-2026-10-27.md`): не проверялись, могут отставать от RUNBOOK и IMPROVEMENT_PLAN.

## 6. Следующие шаги

| # | Шаг | Владелец | Условие «готово» |
|---|---|---|---|
| 1 | Удаления `docs/increments/`, `docs/paper/`, `real_run_smoke.py`, `compile_manuscript_docx.py`, `test_challenger_m2_iter2.py` | пользователь | **Выполнено 2026-10-28: пользователь подтвердил, что удаления намеренные.** Можно включать в коммит |
| 2 | Выбрать ветку и состав первого коммита (см. раздел 7) | пользователь | Ветка и список коммитов согласованы |
| 3 | Закоммитить код, тесты, lock/pyproject, документы (после шага 1–2) | по команде пользователя | `git status` чистый; `git_worktree_dirty = false` |
| 4 | Найти причину `whisper_cuda_available() = False` (DLL cuBLAS/cuDNN, регистрация путей) | разработчик | Команда из §3.2 печатает `True` |
| 5 | Установить MFA в conda-окружении | пользователь (установка только с подтверждения) | `mfa version` выводит версию |
| 6 | Найти причину нестабильности трёх тестов в полном прогоне | разработчик | Полный `pytest -m "not model"` стабильно зелёный, 3 раза подряд |
| 7 | Сверить облако и ноутбук по md5 (передать значения облака или открыть `~/lsw`) | пользователь | Колонка «облако» в разделе 1 заполнена |
| 8 | Обновить IMPROVEMENT_PLAN §1 (заголовок и E1) и RUNBOOK §4 (пункт 3) по факту | разработчик | Статусы соответствуют разделу 3 |
| 9 | Решить по TIMIT (NLTK 160 или LDC93S1) и скачать выбранный | пользователь | Файлы в `nltk_data` или решение о покупке |
| 10 | Пилот: 10 высказываний, затем 160 (только после подтверждения пользователя) | пользователь подтверждает и запускает | Критерии пилота из раздела 7 выполнены |
| 11 | Прогон Buckeye-клипов через `load_buckeye_utterances` без моделей (проверка загрузчика, без записи в reports/) | разработчик | Число загруженных высказываний соответствует ожиданию |

## 7. Открытые решения пользователя

а) **Размер выборки Buckeye.** Предложено: 10 клипов на диктора (≈400 при 40 дикторах), фиксированный seed. Нужен ответ: принимаем?

б) **TIMIT.** Вариант 1: NLTK-сэмпл (160 высказываний, бесплатно). Вариант 2: полный LDC93S1 (платно, проверить подписку AITU). Нужен выбор.

в) **Критерии пилота.** Предложено: доля провалов меньше 5%, покрытие не ниже 90%. Нужно подтвердить или изменить.

г) **Ветка и состав первого коммита.** Текущая ветка `fix/benchmark-integrity`. Варианты: (1) коммитить в неё; (2) новая ветка для фазы 1. Состав: один коммит или три (код+тесты+lock, документы, удаления). Нужен выбор.
