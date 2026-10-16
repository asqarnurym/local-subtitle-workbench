# Implementer Handoff Report: Increment 1 (Speech Models & Token-Span Text Normalizer)

**Branch:** `feature/increment-1-speech-models-and-norm`  
**Repository:** `c:\Users\nurym\Desktop\local-subtitle-workbench`  
**Author:** teamwork_preview_implementer_r0  
**Status:** Completed & Fully Verified

---

## 1. Executive Summary & Deliverables

Increment 1 implements the speech data contracts and the bidirectional word-span token normalizer with reversible subtitle cue projection.

### 1.1 Files Modified & Created
1. `src/subtitle_workbench/models.py`:
   - Added validation helpers: `validate_identifier` (ASCII letters, digits, underscore, hyphen, max length 128), `validate_text` (rejection of control characters and UTF-16 surrogates).
   - Added typed and defensively validated dataclasses:
     - `PhonemeCue`: `phoneme: str`, `start: float`, `end: float`, `confidence: float`. Enforces `0.0 <= start < end`, `0.0 <= confidence <= 1.0`, finite numbers, no control chars.
     - `WordToken`: `id: str`, `text: str`, `normalized: str`, `start: float`, `end: float`, `confidence: float`, `phonemes: list[PhonemeCue] = field(default_factory=list)`, `char_start: int | None = None`, `char_end: int | None = None`. Enforces identifier rules, text cleanliness, non-negative interval bounds, `char_start <= char_end`.
     - `ASRSegment`: `id: str`, `start: float`, `end: float`, `text: str`, `words: list[WordToken]`. Validates non-negative intervals, ASCII IDs, and strictly typed WordToken lists.
     - `AlignmentResult`: `words: list[WordToken]`, `phonemes: list[PhonemeCue]`, `alignment_method: str`, `path_cost: float`, `evaluated_cells: int`. Enforces non-negative path cost and evaluated cells count.
2. `src/subtitle_workbench/text_norm.py`:
   - `TokenSpan`: dataclass capturing `token: str`, `normalized: str`, `char_start: int`, `char_end: int`.
   - `normalize_text_spans(text: str) -> list[TokenSpan]`:
     - Contraction expansion (`"don't"` -> `"do"`, `"not"`; `"I'm"` -> `"i"`, `"am"`), supporting both ASCII `'` and curly `’`.
     - Pure standard library number-to-words engine (`parse_number_to_words`, `integer_to_words`) supporting cardinal numbers (0 to trillions), ordinals (`"21st"` -> `["twenty", "first"]`), decimals (`"3.14"` -> `["three", "point", "one", "four"]`), signed numbers (`"-5"` -> `["negative", "five"]`), and thousands commas (`"1,000"`).
     - Both expanded tokens map strictly to original character slice `original_text[span.char_start:span.char_end] == span.token`.
     - Hyphenated compound words (`"end-to-end"`) decomposed into sub-tokens with exact individual character offsets.
     - Academic abbreviations (`"API"`, `"CPU"`) normalized to lower case (`"api"`, `"cpu"`).
     - Punctuation stripping without desynchronizing character offsets.
   - `project_tokens_to_cues(tokens: list[WordToken], original_text: str, id_prefix: str = "c") -> list[Cue]`:
     - Reversibly projects normalized token timestamps back onto display subtitle cue structures (`Cue`), ready for WebVTT export.
     - Supports multi-cue texts partitioned by blank lines (`\n\s*\n`), preserves custom IDs if present, and provides sequential fallback if character spans are absent.
3. `src/subtitle_workbench/__init__.py`:
   - Exposed all newly added models and normalization functions while preserving `__version__ = "0.1.0"`.
4. `tests/test_speech_models.py`:
   - 110 parameterized tests verifying boundary conditions, type errors, negative intervals, NaN/inf/bool rejection, malformed identifiers, and control characters across all four speech models.
5. `tests/test_text_norm.py`:
   - 48 unit tests verifying contractions, numbers, ordinals, decimals, hyphenated compounds, acronyms, edge cases (empty strings, whitespace-only, punctuation-only), the `text[span.char_start:span.char_end] == span.token` invariant, and reverse cue projection into WebVTT.

---

## 2. Verification Record

### 2.1 Deep Verification (Executed Automated Tests)
1. **Pytest Test Suite:**
   - Command: `uv run --locked pytest`
   - Result: `230 passed in 2.55s`
   - Regressions on 72 pre-existing tests: 0
   - New unit tests passed: 158
2. **Ruff Linter:**
   - Command: `uv run --locked ruff check .`
   - Result: `All checks passed!`
3. **Ruff Formatter Check:**
   - Command: `uv run --locked ruff format --check .`
   - Result: `45 files already formatted`
4. **Isolated Wheel Build:**
   - Command: `uv run --locked python -m build --wheel --no-isolation`
   - Result: `Successfully built local_subtitle_workbench-0.1.0-py3-none-any.whl`
5. **Offline Smoke Test with Socket Guard:**
   - Command: `uv run --locked python scripts/smoke_wheel.py --wheel dist/...whl --output smoke_out`
   - Result: `network_guard: passed`, `max_absolute_error_ms: 18.4ms`, `0 network requests`.

### 2.2 Shallow Verification
- Visual inspection of `docs/ARCHITECTURE.md` to ensure formatted Python code snippets remain valid and aligned with specifications.

### 2.3 Unverified Aspects
- Live ASR execution using real GPU / faster-whisper or MFA Kaldi binaries (deferred by design to Increments 2 and 4 per SDLC roadmap).
- Non-English character sets (multilingual expansion is explicitly out-of-scope for Increment 1 English core).

---

## 3. Known Issues
Prefixes:
- `Fatal Functional Bug`: None.
- `Shallow Verification`: None.
- `Minor Robustness Risk`: Number parsing currently covers standard English formats (integers, thousands separators, decimals, and ordinals up to 10^12). Unconventional mixed alphanumerics (e.g. "3D", "4K") are normalized as words rather than spelled out as digits.

---

## 4. Commands Executed During Verification
```powershell
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked python -m build --wheel --no-isolation
uv run --locked python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output smoke_out
```
