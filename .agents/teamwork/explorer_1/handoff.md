# Handoff Report: Speech Data Models & Boundary Validation (Increment 3 / R1)

**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench`  
**Agent:** `explorer_1`  
**Recipient:** `0fa70c77-af14-4918-bbd6-040d951e6665` (parent / orchestrator)  
**Date:** 2026-10-20  
**Handoff Type:** Hard (Task complete)  

---

## 1. Observation

1. **`src/subtitle_workbench/models.py` Architecture & Helpers:**
   - Lines 7–16: `finite_number(value: object, name: str) -> float` strictly enforces `not isinstance(value, bool)` and `isinstance(value, Real)`, catches `OverflowError`/`TypeError`/`ValueError`, and enforces `-float("inf") < number < float("inf")` (rejecting `inf`, `-inf`, and `NaN`).
   - Lines 19–30: `validate_identifier(identifier: object, name: str = "id") -> str` enforces non-empty ASCII string `char.isascii() and (char.isalnum() or char in "_-")`, non-bool, and length $\le 128$.
   - Lines 33–51: `validate_text(text: object, name: str = "text", allow_newlines: bool = True) -> str` enforces non-empty stripped text, max length 4000, rejects surrogates (`0xD800 <= ord <= 0xDFFF`), and forbids C0/C1 control characters.
   - Lines 54–81: `Config` uses `@dataclass(frozen=True)` and validates parameter bounds in `__post_init__`.
   - Lines 83–89: `Cue` uses `@dataclass(frozen=True)` with fields `(id, start, end, text)`. Note: There is **no separate `WebVTTDocument` dataclass** in the codebase; WebVTT files are modeled as `list[Cue]`, validated by `validate_cues(data, duration) -> list[Cue]`, and serialized via `export.webvtt(cues: list[Cue]) -> str`.
   - Lines 137–158: `PhonemeCue` uses `@dataclass(frozen=True)` and mutates attributes in `__post_init__` via `object.__setattr__(self, "attribute", value)` to coerce validated floats.
   - Lines 160–207: `WordToken` uses `@dataclass(frozen=True)`, validates `id`, `text`, `normalized`, `0.0 <= start < end`, `0.0 <= confidence <= 1.0`, and `phonemes: list[PhonemeCue]`.
   - Lines 209–232: `ASRSegment` uses `@dataclass(frozen=True)`, validates `id`, `0.0 <= start < end`, `text` (with `allow_newlines=True`), and `words: list[WordToken]`.
   - Lines 234–262: `AlignmentResult` uses `@dataclass(frozen=True)` with `words`, `phonemes`, `alignment_method`, `path_cost`, and `evaluated_cells`.

2. **Package Exports (`src/subtitle_workbench/__init__.py`):**
   - Lines 1–31: Exports 16 symbols in `__all__`, strictly alphabetized (`ASRError` through `project_tokens_to_cues`). `AudioChunk` and `ChunkConfig` are not yet exported.

3. **Packaging & Dependencies (`pyproject.toml`):**
   - Lines 10–13: Requires Python `">=3.11,<3.13"`, base dependency is only `numpy>=2.1,<3`. `models.py` has zero non-standard dependencies.
   - Lines 27–36: Wheel build target `src/subtitle_workbench`; ruff line-length 100, lint rules `["E", "F", "I", "B", "UP"]`.

4. **Existing Test Suite Baseline:**
   - Tool command `uv run --locked pytest` completed in 3.34s with 314 passed, 1 skipped (`faster-whisper is not installed` integration test).
   - Tool command `uv run --locked ruff check .` passed with zero errors.
   - Tool command `uv run --locked python -m build --wheel --no-isolation` succeeded cleanly generating `local_subtitle_workbench-0.1.0-py3-none-any.whl`.

---

## 2. Logic Chain

1. **Model Immutability & Safety (from Obs 1):**
   - Because `Config`, `Cue`, `PhonemeCue`, `WordToken`, and `ASRSegment` are all `@dataclass(frozen=True)`, `AudioChunk` and `ChunkConfig` must also be decorated with `@dataclass(frozen=True)` to preserve project-wide immutability.
   - Because `@dataclass(frozen=True)` forbids attribute assignments in `__post_init__`, attribute normalization and float coercion must use `object.__setattr__(self, field_name, value)`.

2. **Invariant Decomposition for `AudioChunk` (from Obs 1 & R1 Requirements):**
   - Requirement R1 specifies invariant: `0.0 <= padded_start <= start < end <= padded_end`.
   - In Python, checking this atomically in one inequality chain makes diagnostic failure messages ambiguous. Decomposing it into 4 sequential checks (`padded_start < 0.0`, `padded_start > start`, `start >= end`, `end > padded_end`) yields exact, actionable error messages.
   - Using `finite_number` on each timestamp ensures non-finite numbers (`NaN`, `inf`, `-inf`) and `bool` values are rejected before relational comparisons occur.

3. **Validation of `ChunkConfig` (from Obs 1 & R1 Requirements):**
   - Configurable thresholds with defaults: `max_chunk_duration: float = 30.0`, `min_chunk_duration: float = 1.0`, `overlap_padding: float = 0.5`, `min_silence_duration: float = 0.4`.
   - Applying `finite_number` ensures type correctness and rejects `bool`/`NaN`/`inf`.
   - Relational invariants: `min_chunk_duration > 0.0`, `max_chunk_duration >= min_chunk_duration`, `overlap_padding >= 0.0`, and `min_silence_duration > 0.0` guarantee physical validity for the chunker.

4. **Export Cleanliness (from Obs 2):**
   - Adding `AudioChunk` and `ChunkConfig` to `models.py` and updating `__init__.py` while preserving alphabetical order in `__all__` satisfies Ruff `I` and `F` lint rules.

---

## 3. Caveats

1. **Read-only Investigation**: In accordance with the Explorer mandate, no files in `src/` or `tests/` were modified. Implementation will occur in Phase 1.
2. **`WebVTTDocument` Model**: As noted in Observation 1, `WebVTTDocument` was referenced in the prompt, but the actual repository implementation represents WebVTT as `list[Cue]` serialized by `export.webvtt(cues)`. No new document class is required for R1.
3. **Word Alignment Boundaries within Chunks**: `AudioChunk` validates that `words` is a list of `WordToken` instances, but does not constrain whether word timestamps are strictly within `[start, end]`, because initial chunk partitioning occurs before local word alignment or transcription. Monotonicity and boundary deduplication are explicitly delegated to `reconcile_chunk_alignments` in R2.

---

## 4. Conclusion

The specification and validation design for Requirement R1 (`AudioChunk` and `ChunkConfig`) are fully defined and ready for immediate implementation in Phase 1:
- `AudioChunk`: `@dataclass(frozen=True)` with fields `id` (ASCII string), `index` (non-negative int), `start`, `end`, `padded_start`, `padded_end` (floats satisfying $0.0 \le \text{padded\_start} \le \text{start} < \text{end} \le \text{padded\_end}$), `text` (non-empty Unicode, max 4000 chars, no control chars), and `words: list[WordToken] = field(default_factory=list)`.
- `ChunkConfig`: `@dataclass(frozen=True)` with defaults `max_chunk_duration=30.0`, `min_chunk_duration=1.0`, `overlap_padding=0.5`, `min_silence_duration=0.4`, strictly checking finiteness and positive/non-negative thresholds.
- Full details, proposed code snippets, and comprehensive test matrices are recorded in:  
  `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_1\report.md`.

---

## 5. Verification Method

To verify the findings and validate any subsequent implementation:

1. **Verify Baseline State:**
   ```powershell
   cd C:\Users\nurym\Desktop\local-subtitle-workbench
   uv run --locked pytest
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   uv run --locked python -m build --wheel --no-isolation
   ```
2. **Inspect Technical Report:**
   Read `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_1\report.md` for the line-by-line model definitions, invariant proofs, and test matrices.
3. **Post-Implementation Verification (for Implementer / Sentinel):**
   - Ensure `AudioChunk` and `ChunkConfig` can be imported from `subtitle_workbench`.
   - Ensure all negative test cases (`NaN`, `inf`, `bool`, `padded_start > start`, `start == end`, negative index, control chars in text) raise `ValueError`.
   - Ensure all 314 baseline tests continue to pass with 0 regressions.
