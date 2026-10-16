# Reviewer Report: Increment 1 (Speech Models & Token-Span Text Normalizer) — Round 2

**Reviewer:** teamwork_preview_reviewer_r2  
**Working Directory:** `c:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\teamwork_preview_reviewer_r2`  
**Repository:** `c:\Users\nurym\Desktop\local-subtitle-workbench`  
**Branch:** `feature/increment-1-speech-models-and-norm`  
**Status:** Completed & Adversarially Hardened

---

> [!WARNING] **Skepticism Disclaimer**
> Confidence is very high for Increment 1 scope (speech data contracts, token normalization, reverse cue projection, and subtitle validation); 256 real automated unit and regression tests pass without synthetic mocks, though live neural ASR inference and MFA Kaldi acoustic models are deferred to Increments 2 and 4 by project SDLC design.

---

## 1. What the prior attempt got wrong

### Issue 1 (Dictionary Incompatibility / Subtitle Failure: Unicode Ellipsis `…` and Typographical Symbols Retained in Normalized Words)
- **Input:** Subtitle text containing horizontal ellipsis `…` (U+2026), e.g., `"Wait… what?"` or `"…Wait"`, or typographical quotes/symbols (`„`, `‚`, `‹`, `›`, `¿`, `¡`, `♪`).
- **Expected:** Punctuation is stripped from word boundaries per R2 ("Punctuation stripping and whitespace cleaning without desynchronizing character offsets. Lowercasing for CMUDict / MFA phonetic dictionary compatibility."). `normalized` produces clean `"wait"`, and character spans map verbatim to the original slice (`original_text[span.char_start:span.char_end] == span.token`).
- **Actual:** `PUNCT_LEFT` and `PUNCT_RIGHT` omitted `…` and Unicode symbols. For `"Hello world…"`, `TokenSpan(token="world…", normalized="world…", char_start=6, char_end=12)` was produced. The normalized word retained `…`, which does NOT exist in CMUDict or MFA phonetic dictionaries and causes dictionary lookup failure.
- **Root cause:** Static set omitted Unicode `P*` and `S*` categories. Added `_is_boundary_punct(c)` using `c in PUNCT_LEFT or unicodedata.category(c).startswith(("P", "S"))`.

### Issue 2 (Functional Number Parsing Bug: Mathematical Unicode Minus `−` Stripped or Unparsed)
- **Input:** Subtitle text with mathematical Unicode minus, e.g. `"−5"`, `"−42"`, or `"−3.14"`.
- **Expected:** Negative sign preserved and parsed to words (`["negative", "five"]`, `["negative", "forty", "two"]`).
- **Actual:** `text[left] == "-"` in `normalize_text_spans` only checked ASCII `-`, treating Unicode minus `−` as generic punctuation and stripping it to positive `"5"`, losing the negative sign completely.
- **Root cause:** Missing support for `\u2212` in boundary punctuation checks, hyphen regexes, and `parse_number_to_words`.

### Issue 3 (Currency Inconsistency: Non-Dollar Currencies Like `€`, `£`, `¥` Failing Number Expansion)
- **Input:** `"€50"`, `"£25"`, `"¥1000"`.
- **Expected:** Currency prefix stripped from number boundary, expanding number to words (`["fifty"]`).
- **Actual:** `$` was in `PUNCT_LEFT` but `€`, `£`, `¥` were not, resulting in unparsed tokens `token="€50", normalized="€50"` instead of number word expansion.
- **Root cause:** Missing currency symbols in boundary punctuation table.

### Issue 4 (Spec Compliance & Defensive Validation Bug: `TokenSpan` Accepted Control Characters, Surrogates, and Blank Whitespace)
- **Input:** `TokenSpan(token="bad\x00", ...)`, `TokenSpan(token="bad\x7f", ...)`, `TokenSpan(token="bad\x80", ...)`, `TokenSpan(token="bad\ud800", ...)`, or `TokenSpan(token="   ", ...)`.
- **Expected:** Defensive validation rejects control characters, surrogates, and whitespace-only text per R1 ("forbid control characters in textual fields") and R2.
- **Actual:** `TokenSpan.__post_init__` only checked `not self.token`, allowing control characters, surrogate code points, and pure whitespace to pass silently.
- **Root cause:** `TokenSpan` did not call `validate_text(self.token, "token", allow_newlines=False)` and `validate_text(self.normalized, "normalized", allow_newlines=False)`.

### Issue 5 (Phonetic Dictionary Incompatibility: Loanword Diacritics/Accents in English Subtitles)
- **Input:** Words like `"café"`, `"naïve"`, `"façade"`, `"résumé"`.
- **Expected:** `TokenSpan.token` preserves original text slice verbatim, but `TokenSpan.normalized` strips diacritics (`"cafe"`, `"naive"`, `"facade"`, `"resume"`) because CMUDict/MFA phonetic dictionaries only contain unaccented ASCII letters.
- **Actual:** `norm_word` retained accented characters, causing out-of-vocabulary failures in phonetic dictionary lookups.
- **Root cause:** Missing NFKD combining character removal in `_process_word`.

### Issue 6 (Defensive Robustness: Cue Overlap and Overlong ID Hazards in `project_tokens_to_cues`)
- **Input:** Out-of-order/overlapping speech token intervals across cue blocks, or cue blocks with ID line > 128 characters.
- **Expected:** Cues emitted are monotonically non-overlapping (satisfying `validate_cues`), and overlong IDs fallback cleanly.
- **Actual:** Overlapping token intervals created overlapping cues that caused `validate_cues` to reject the generated subtitle file with `cues must be ordered and non-overlapping`. Overlong candidate IDs caused `validate_cues` to fail with ID length error.
- **Root cause:** Missing monotonicity clamping (`if cues and cue_start < cues[-1].end: cue_start = cues[-1].end`) and missing candidate ID length check in `_extract_cue_id_and_text`.

---

## 2. What I changed

1. `src/subtitle_workbench/text_norm.py`:
   - Imported `unicodedata` and `validate_text`.
   - Added missing standard spoken contractions to `CONTRACTIONS`: `"it'd"`, `"who'd"`, `"what'd"`, `"where'd"`, `"how'd"`, `"why'd"`, `"who'll"`, `"what'll"`, `"where'll"`, `"when'll"`, `"how'll"`, `"who've"`, `"what've"`.
   - Expanded `PUNCT_LEFT` and `PUNCT_RIGHT` to include `…`, `„`, `‚`, `‹`, `›`, `¿`, `¡`, `€`, `£`, `¥`, `₹`, `₽`, `₩`, `\u2212`.
   - Implemented `_is_boundary_punct(c: str) -> bool` using `c in PUNCT_LEFT or unicodedata.category(c).startswith(("P", "S"))`.
   - Updated `parse_number_to_words` to normalize Unicode minus `\u2212` to `-`.
   - Hardened `TokenSpan.__post_init__` to validate `token` and `normalized` via `validate_text(..., allow_newlines=False)`, strictly forbidding control characters, surrogates, and whitespace-only text.
   - Updated `_process_word` to strip combining diacritics via NFKD on `norm_word` for CMUDict/MFA dictionary compatibility while keeping verbatim `token`.
   - Updated `normalize_text_spans` to strip boundary punctuation using `_is_boundary_punct` while preserving leading minus (ASCII and Unicode `\u2212`) on negative numbers, and expanded hyphen regex to handle `\u2212`.
   - Updated `_extract_cue_id_and_text` to verify `len(first) <= 128`.
   - Updated `project_tokens_to_cues` to enforce monotonic non-overlapping cue boundaries (`cue_start = cues[-1].end` when overlapping) and cap candidate ID base to 120 chars to guarantee allocated IDs never exceed 128 chars.
2. `tests/test_text_norm.py`:
   - Added 8 new adversarial test functions:
     - `test_token_span_defensive_control_and_surrogates`
     - `test_normalize_unicode_ellipsis_and_symbols`
     - `test_normalize_unicode_minus_and_currency`
     - `test_normalize_typographical_quotes`
     - `test_normalize_loanword_diacritics_cmudict_compatibility`
     - `test_normalize_expanded_contractions`
     - `test_project_tokens_to_cues_overlapping_mitigation`
     - `test_project_tokens_to_cues_overlong_id_fallback`
3. `tests/test_speech_models.py`:
   - Added `test_speech_models_zero_and_extreme_boundaries` verifying zero boundaries (`start=0.0`, `confidence=0.0`, `confidence=1.0`, `path_cost=0.0`, `evaluated_cells=0`), empty collections (`words=[]`, `phonemes=[]`), and multiline text.

---

## 3. Verification Record

- **Deep Verification (ran actual tests):**
  - `uv run --locked pytest`: **256 passed in 2.58s** (72 original + 111 speech model tests + 73 text norm tests).
  - `uv run --locked ruff check .`: **All checks passed!**
  - `uv run --locked ruff format --check .`: **49 files already formatted.**
  - `uv run --locked python -m build --wheel --no-isolation`: **Successfully built `local_subtitle_workbench-0.1.0-py3-none-any.whl`**.
  - `uv run --locked python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output smoke_out`: **Passed offline smoke test (`network_guard: passed`, `0 network requests`, `max_absolute_error_ms: 18.4ms`)**.
- **Shallow Verification (manual only):**
  - Verified `__all__` in `src/subtitle_workbench/__init__.py` contains all 6 models and 2 normalizer functions.
  - Inspected `ARCHITECTURE.md` section 5.1 and 5.2 to ensure model and normalizer contracts match specifications.
- **Unverified aspects:**
  - Live neural ASR inference via faster-whisper (deferred by SDLC design to Increment 2).
  - MFA Kaldi acoustic model alignment (deferred by SDLC design to Increment 4).
  - Multilingual character sets (explicitly out of scope for Increment 1 English core).

---

## 4. Known Issues

- `Fatal Functional Bug`: None remaining.
- `Shallow Verification`: None.
- `Minor Robustness Risk`: Mixed alphanumeric strings without hyphens (e.g. `"3D"`, `"4K"`) are lowercased as words rather than spelled out as digit words (deferred to future multilingual/technical text expansion).

---

## 5. Remaining risk & next step

- **Remaining risk:** Live acoustic alignment against noisy audio will require CTC/HMM alignment engines (scheduled for Increments 2 and 4). Increment 1 contracts, token normalizers, and reverse cue projectors are fully verified, defensively hardened, and 100% covered by 256 automated tests.
- **Next step:** Review round 2 is complete. Proceed to clean git commit amend or commit creation and handoff to orchestrator.
