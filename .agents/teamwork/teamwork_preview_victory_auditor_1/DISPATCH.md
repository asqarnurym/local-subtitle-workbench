## 2026-10-16T22:58:25Z

You are teamwork_preview_victory_auditor_1.
Your working directory is: c:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\teamwork_preview_victory_auditor_1
Repository root: c:\Users\nurym\Desktop\local-subtitle-workbench
Branch: feature/increment-1-speech-models-and-norm

<original_task>
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
</original_task>

Conduct an independent 3-phase post-victory audit (timeline & commit verification, anti-cheating / anti-falsification detection, and independent test execution). Deliver your formal audit report and structured verdict (CONFIRMED / REJECTED) to `c:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\teamwork_preview_victory_auditor_1\handoff.md` and message the orchestrator.
