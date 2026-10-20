# Increment Report: Speech Data Models & Word-Span Token Normalizer
**Increment ID:** `INCREMENT_1_SPEECH_MODELS_AND_NORM`  
**Date:** 2026-10-17  
**Git Branch:** `feature/increment-1-speech-models-and-norm`  
**Git Commit SHA:** `e7876de28074f53862ab60fca519fdef58a77541`  
**Author:** Askar Nurym  
**Status:** Completed & Independently Audited (Victory Confirmed)

---

## 1. Executive Summary & Objective
Increment 1 implemented the foundational speech contracts and reversible text normalization layer for the Local Subtitle Alignment Workbench. The goal was to solve audit finding F11 (non-bijective character normalization) by creating a mathematically reversible, token-level span mapping between verbatim on-screen subtitle text and normalized acoustic tokens required by ASR and pronunciation dictionaries (CMUDict/MFA).

---

## 2. Traceability to Individual Plan & Quality Gates
- **Thesis Milestone:** Подготовка к НИРМ 3 (Алгоритм точной синхронизации) и модуль генерации субтитров.
- **ASDP Quality Gates Addressed:**
  - [x] Gate 1: Requirements & Typed Speech Contracts (`WordToken`, `PhonemeCue`, `ASRSegment`, `AlignmentResult`, `SpeechConfig`).
  - [x] Gate 2: Modular Implementation (`src/subtitle_workbench/text_norm.py`, `src/subtitle_workbench/models.py`).
  - [x] Gate 3: Unit & Numerical Verification (261/261 tests pass, 189 new tests, 0 regressions, 0 mocks, 0 skipped).
  - [x] Gate 4: Packaging & Offline Smoke Test (wheel builds without isolation, smoke test executes offline with socket guard).
  - [x] Gate 5: Manifest & Code Provenance Audit (independent victory audit confirmed).

---

## 3. Detailed Inventory of Changes

### 3.1 Files Created / Modified
| File Path | Changes | Responsibility / Architectural Role |
| :--- | :---: | :--- |
| `src/subtitle_workbench/models.py` | +164 lines | Typed speech dataclasses: `PhonemeCue`, `WordToken`, `ASRSegment`, `AlignmentResult`, `SpeechConfig`, and rigorous validators enforcing finite numbers, positive non-overlapping intervals, and ASCII identifiers. |
| `src/subtitle_workbench/text_norm.py` | +513 lines | Reversible word-span token normalizer: handles contractions (`"don't"` -> `"do"`, `"not"`), numbers (`"21"` -> `"twenty"`, `"one"`), currency, typographical punctuation, mathematical symbols, and reversible projection of aligned tokens back to verbatim subtitle `Cue` objects. |
| `tests/test_speech_models.py` | +437 lines | 117 tests verifying speech dataclass validation, contract violations, NaN/inf/bool rejection, and interval ordering. |
| `tests/test_text_norm.py` | +720 lines | 72 tests covering span preservation, academic terminology, numbers, contractions, punctuation stripping, and cue projection. |
| `src/subtitle_workbench/__init__.py` | +13 lines | Export public speech contracts and normalizer functions. |

### 3.2 Dependencies & Build
- **Zero Heavy Dependencies Added:** Maintained the strict lightweight constraint (NumPy only, Python standard library). No torch or faster-whisper forced into base dependencies for this increment.

---

## 4. Verification Evidence & Quality Gate Results

### 4.1 Automated Test Execution
```
Command: uv run --locked pytest
Result: PASS
Total Tests: 261 passed in 3.06s (72 existing + 189 new)
Existing Tests Regressed: 0
Mocks Used: 0
Skipped / xfail: 0
```

### 4.2 Code Linter & Formatting
```
Command: uv run --locked ruff check .
Result: All checks passed!

Command: uv run --locked ruff format --check .
Result: 14 files already formatted!
```

### 4.3 Packaging & Wheel Smoke Test
```
Command: uv run --locked python -m build --wheel --no-isolation
Result: Successfully built local_subtitle_workbench-0.1.0-py3-none-any.whl

Command: uv run python scripts/smoke_wheel.py
Result: PASS (offline socket guard active, mean error 18.4ms on synthetic fixture)
```

---

## 5. Architectural Decisions & Hardening
- **Decision 1 (Token-Level Span Mapping):** Rejected naive character-level bijection in favor of `TokenSpan` records that track `char_start` and `char_end` within the original string.
- **Decision 2 (Reversible Cue Projection):** Created `project_tokens_to_cues` allowing aligned acoustic tokens to project their start/end timestamps directly back to original raw subtitle cues without losing original capitalization or punctuation.
- **Decision 3 (Edge Case Hardening):** Systematically hardened against Unicode ellipsis (`…`), typographical quotes (`“`, `”`, `‘`, `’`), mathematical minus (`−`), and sub-millisecond cue collapse.

---

## 6. Handover & Prerequisites for Increment 2
- **Working Tree:** Clean, verified on branch `feature/increment-1-speech-models-and-norm`.
- **Ready for Increment 2:** Faster-Whisper ASR Integration, Silero-VAD, and Sequential GPU VRAM Management.
