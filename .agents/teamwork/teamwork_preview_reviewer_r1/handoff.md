# Reviewer Report: Increment 1 (Speech Models & Token-Span Text Normalizer)

**Reviewer:** teamwork_preview_reviewer_r1  
**Working Directory:** `c:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\teamwork_preview_reviewer_r1`  
**Repository:** `c:\Users\nurym\Desktop\local-subtitle-workbench`  
**Branch:** `feature/increment-1-speech-models-and-norm`  
**Status:** Completed & Adversarially Hardened

---

> [!WARNING] **Skepticism Disclaimer**
> Confidence is moderate-high for standard English subtitle and speech workflows; 247 real automated tests pass, but live neural ASR/acoustic alignment execution remains deferred to Increments 2 and 4.

---

## 1. What the prior attempt got wrong

### Issue 1 (Fatal Functional Bug: Multi-Line Subtitle First-Line Truncation)
- **Input:** `text = "Hello\nworld"` (or subtitles where line 1 is a single regular word like `"Welcome\nto our show"`, `"Yes\nI agree"`).
- **Expected:** `project_tokens_to_cues` preserves the first line as subtitle text, producing `Cue(id="c1", start=..., end=..., text="Hello\nworld")`.
- **Actual:** `Cue(id="Hello", start=..., end=..., text="world")`. The first line `"Hello"` was stripped from the subtitle text and incorrectly assigned as the cue ID.
- **Root cause:** The condition `if len(lines) > 1 and lines[0].strip().isascii() and all(c.isalnum() or c in "_-" for c in lines[0].strip())` matched any single standard English word. Replaced with `_extract_cue_id_and_text` requiring explicit cue ID syntax (`cue-*`, `id-*`, `c<digits>`, or numeric integer line).

### Issue 2 (Fatal Functional Bug on Windows: CRLF Line Endings Breaking Cue Validation)
- **Input:** Subtitle text with CRLF line endings (`\r\n`), e.g., `"First line.\r\nSecond line."`.
- **Expected:** `project_tokens_to_cues` normalizes line endings to clean `\n`, allowing `Cue` objects to pass `validate_cues` and WebVTT export.
- **Actual:** `cue.text` retained embedded `\r`. Calling `validate_cues` failed with `ValueError: cue text must be plain Unicode without control/blank lines` because `ord(char) < 32 and char != '\n'` rejects `\r`.
- **Root cause:** Raw slice `original_text[b_start:b_end]` was stripped without normalizing newlines (`\r\n` -> `\n`).

### Issue 3 (Input Boundary / Spec Compliance Bug: ASCII DEL and C1 Controls Permitted)
- **Input:** Model fields or text containing DEL (`\x7f`) or C1 control characters (`0x80` to `0x9F`), e.g., `WordToken(text="hello\x7f", ...)`, `PhonemeCue(phoneme="DH\x7f", ...)`, `normalize_text_spans("hello\x7fworld")`.
- **Expected:** Validation strictly rejects DEL and C1 control characters per R1 ("forbid control characters in textual fields").
- **Actual:** `validate_text` and `normalize_text_spans` only checked `ord(char) < 32`, allowing DEL (127) and C1 controls to pass through.
- **Root cause:** Incomplete control character check. Expanded to `(ord(char) < 32 and (not allow_newlines or char not in "\t\n\r")) or ord(char) == 127 or (128 <= ord(char) <= 159)`.

### Issue 4 (Dictionary Incompatibility Bug: Academic Degrees Retaining Internal Periods)
- **Input:** Academic abbreviations such as `"Ph.D."`, `"M.Sc."`, `"B.Sc."`.
- **Expected:** Normalized for CMUDict/MFA phonetic dictionary compatibility (R2) by stripping internal dots to `"phd"`, `"msc"`, `"bsc"`.
- **Actual:** Normalized to `"ph.d"` and `"m.sc"`, which do not exist in CMUDict or MFA phonetic dictionaries.
- **Root cause:** Regex `r"^([a-z]\.)+[a-z]?$"` strictly required 1 letter before each period, failing on multi-letter segments like `ph.` or `.sc`. Updated to `r"^[a-z]+(\.[a-z]+)+$"`.

### Issue 5 (Dictionary Incompatibility Bug: Curly Apostrophes in Non-Contractions)
- **Input:** Non-contraction words with curly apostrophes, e.g., `"John’s"`.
- **Expected:** `TokenSpan.normalized` maps curly apostrophes `’` to ASCII `'` (`"john's"`) for CMUDict/MFA dictionary compatibility while `TokenSpan.token` preserves verbatim `"John’s"`.
- **Actual:** `_process_word` only replaced `’` for contraction lookup in `clean_key`. For all other words, `norm_word` retained Unicode `’`, causing CMUDict/MFA lookups to fail.
- **Root cause:** Missing `.replace("’", "'").replace("‘", "'")` on `norm_word`.

### Issue 6 (Defensive Robustness Risk: Duplicate IDs and Unchecked Prefix in Cue Projection)
- **Input:** Subtitle blocks with duplicate custom IDs (e.g. repeated `cue-A`) or invalid `id_prefix` (e.g. `id_prefix="bad id!"`).
- **Expected:** `id_prefix` is defensively validated, and duplicate cue IDs are automatically deduplicated with index suffixes so cues always satisfy `validate_cues` uniqueness rules.
- **Actual:** `id_prefix` was unchecked, and duplicate IDs resulted in colliding cue IDs that failed validation.
- **Root cause:** Missing input validation on `id_prefix` and missing collision tracking set.

---

## 2. What I changed

1. `src/subtitle_workbench/models.py`:
   - Updated `validate_text` to strictly reject DEL (`\x7f`, ASCII 127) and C1 control characters (`0x80` to `0x9F`), both with and without `allow_newlines`.
2. `src/subtitle_workbench/text_norm.py`:
   - Updated `_process_word` to normalize curly apostrophes (`’`, `‘`) to ASCII `'` in `norm_word` for CMUDict/MFA compatibility.
   - Broadened acronym period stripping from `r"^([a-z]\.)+[a-z]?$"` to `r"^[a-z]+(\.[a-z]+)+$"` to handle academic degrees (`Ph.D.` -> `phd`, `M.Sc.` -> `msc`).
   - Updated `normalize_text_spans` to reject DEL and C1 control characters.
   - Introduced `_extract_cue_id_and_text` with precise pattern matching (`^(?:cue|id)[-_]`, `^c\d+$`, `^\d+$`) and newline normalization (`splitlines()` joining on `\n`).
   - Updated `project_tokens_to_cues` with defensive `id_prefix`, surrogate, and control character validation, cue ID deduplication (`_allocate_id`), and consistent character span checks (`all(t.char_start is not None for t in tokens)`).
3. `tests/test_speech_models.py`:
   - Added parameterized tests asserting rejection of DEL (`\x7f`) and C1 (`\x80`) control characters across `PhonemeCue`, `WordToken`, `ASRSegment`, `AlignmentResult`, and `validate_text`.
4. `tests/test_text_norm.py`:
   - Added 7 new unit tests (17 total assertions) verifying:
     - Multi-line subtitle cue projection without ID truncation (`Hello\nworld`, `Welcome\nto our presentation!`).
     - Windows CRLF newline normalization and validation against `validate_cues`.
     - Automatic deduplication of duplicate custom IDs.
     - Input validation on `id_prefix`, surrogate characters, and control characters in `project_tokens_to_cues`.
     - Normalization of academic abbreviations and degrees (`Ph.D.`, `M.Sc.`, `U.S.A.`, `e.g.`).
     - Normalization of curly apostrophes in possessives (`John’s`, `Mary‘s`).
     - Rejection of DEL and C1 control characters in `normalize_text_spans`.

---

## 3. Verification Record

- **Deep Verification (ran actual tests):**
  - `uv run --locked pytest`: **247 passed in 2.55s** (72 original + 110 speech model tests + 65 text norm tests).
  - `uv run --locked ruff check .`: **All checks passed!**
  - `uv run --locked ruff format --check .`: **47 files already formatted.**
  - `uv run --locked python -m build --wheel --no-isolation`: **Successfully built `local_subtitle_workbench-0.1.0-py3-none-any.whl`**.
  - `uv run --locked python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output smoke_out`: **Passed offline smoke test (`network_guard: passed`, `0 network requests`, `max_absolute_error_ms: 18.4ms`)**.
- **Shallow Verification (manual only):**
  - Inspected `ARCHITECTURE.md` sections 5.1 and 5.2 to ensure model and text norm contracts align with methodology docs.
- **Unverified aspects:**
  - Neural ASR model inference via faster-whisper (deferred by SDLC design to Increment 2).
  - MFA Kaldi acoustic model alignment (deferred by SDLC design to Increment 4).
  - Non-English character sets (multilingual expansion is explicitly out-of-scope for Increment 1 English core).

---

## 4. Known Issues

- `Fatal Functional Bug`: None remaining.
- `Shallow Verification`: None.
- `Minor Robustness Risk`: Number parsing covers cardinal numbers up to $10^{12}$, ordinals (`1st` through `1000th`), decimals, and negative numbers. Mixed alphanumeric strings without hyphens (e.g. `"3D"`, `"4K"`) are lowercased as words rather than spelled out as digit words.

---

## 5. Remaining risk & next step

- **Remaining risk:** Live acoustic alignment against messy audio with background noise will require CTC/HMM alignment engines (scheduled for Increments 2 and 4). Increment 1 contracts and normalizers are verified and robust.
- **Next step:** Review round 1 is complete. Increment 1 implementation satisfies all R1-R4 requirements and automated verification criteria. Proceed to orchestrator evaluation or increment sign-off.
