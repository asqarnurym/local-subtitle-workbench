# Reviewer Report: Increment 1 (Speech Models & Token-Span Text Normalizer) — Round 3

**Reviewer:** teamwork_preview_reviewer_r3  
**Working Directory:** `c:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\teamwork_preview_reviewer_r3`  
**Repository:** `c:\Users\nurym\Desktop\local-subtitle-workbench`  
**Branch:** `feature/increment-1-speech-models-and-norm`  
**Status:** Completed & Adversarially Hardened

---

> [!WARNING] **Skepticism Disclaimer**
> Confidence is very high for Increment 1 scope (speech data contracts, token normalization, reverse cue projection, and subtitle validation); 261 real automated unit and regression tests pass without synthetic mocks, though live neural ASR inference and MFA Kaldi acoustic models are deferred to Increments 2 and 4 by project SDLC design.

---

## 1. What the prior attempt got wrong

### Issue 1 (Monotonicity & Invariant Violation: Enclosed or Inverted Token Intervals Across Cue Blocks)
- **Input:** Subtitle blocks with tokens where block 2's speech tokens start before block 1's end time, and end before or at block 1's end time, e.g.:
  `text = "First block.\n\nSecond block."`
  `tokens = [WordToken("w1", "First", "first", 0.0, 1.5, ...), WordToken("w2", "block", "block", 0.5, 1.5, ...), WordToken("w3", "Second", "second", 0.5, 1.2, ...), WordToken("w4", "block", "block", 0.8, 1.2, ...)]`
- **Expected:** Generated cues are strictly ordered and non-overlapping (`cues[1].start >= cues[0].end` and `cues[1].end > cues[1].start`), satisfying `validate_cues` and WebVTT requirements.
- **Actual:** `if cues and cue_start < cues[-1].end and cue_end > cues[-1].end:` only clamped `cue_start` when `cue_end > cues[-1].end`. When `cue_end <= cues[-1].end`, `cue_start` was NOT clamped at all. Block 2 was emitted with `start=0.5, end=1.2`, completely overlapping Block 1 (`[0.0, 1.5]`), causing `validate_cues` to fail with `ValueError: cues must be ordered and non-overlapping`.
- **Root cause:** The condition `and cue_end > cues[-1].end` left enclosed and inverted token sequences un-clamped. Furthermore, when `cue_start` is clamped to `cues[-1].end`, `cue_end` must be guaranteed to exceed `cue_start` while preserving original speech duration (`cue_end = round(cue_start + max(token_dur, 0.001), 3)`).

### Issue 2 (WebVTT Serializer Crash: Sub-Millisecond Token Duration Collapse)
- **Input:** Subtitle text where tokens have sub-millisecond durations (e.g. `start=0.0, end=0.0004` or clamped boundary where `end - start < 0.001`).
- **Expected:** Every cue emitted by `project_tokens_to_cues` has a distinct millisecond duration (`milliseconds(cue.end) > milliseconds(cue.start)`) so it serializes cleanly to WebVTT without crashing.
- **Actual:** `export.webvtt(cues)` crashed with `ValueError: cue collapses after millisecond rounding` because `milliseconds(cue.end) <= milliseconds(cue.start)`.
- **Root cause:** `project_tokens_to_cues` did not verify `milliseconds(cue_end) > milliseconds(cue_start)`.

### Issue 3 (Cue Validation Failure: Horizontal Tab Characters in Subtitle Text)
- **Input:** `original_text = "Hello\tworld"` with valid tokens.
- **Expected:** `project_tokens_to_cues` produces valid subtitle text (tabs normalized to spaces) so downstream validation passes.
- **Actual:** Emitted `Cue.text` contained raw `\t`. Calling `validate_cues` on the resulting cues raised `ValueError: cue text must be plain Unicode without control/blank lines` because `validate_cues` specifically forbids `ord(c) < 32 and c != "\n"`.
- **Root cause:** `_extract_cue_id_and_text` did not normalize horizontal tabs to spaces before creating cue text.

### Issue 4 (Redundant WebVTT Timing Lines: Timing Headers Retained in Cue Text)
- **Input:** `original_text` formatted with WebVTT/SRT timing lines, e.g.:
  `"c1\n00:00:01.000 --> 00:00:02.000\nHello world"`
- **Expected:** The timing line `-->` is recognized and replaced by the newly projected token timestamps; `Cue.text` should be `"Hello world"`.
- **Actual:** `cue_text` retained `"00:00:01.000 --> 00:00:02.000\nHello world"`. When exported to WebVTT via `webvtt(cues)`, duplicate timing lines were generated.
- **Root cause:** `_extract_cue_id_and_text` did not filter out timing lines matching `^\d{1,2}:[0-9:.,]+\s*-->\s*[0-9:.,]+`.

---

## 2. What I changed

1. `src/subtitle_workbench/text_norm.py`:
   - Imported `milliseconds` from `.export`.
   - Added `_adjust_cue_timing(cue_start, cue_end, token_dur, prev_end)` helper function:
     - Enforces monotonicity: `if prev_end is not None and cue_start < prev_end: cue_start = prev_end`.
     - Preserves duration: `if cue_end <= cue_start: cue_end = round(cue_start + max(token_dur, 0.001), 3)`.
     - Prevents millisecond collapse: `while milliseconds(cue_end) <= milliseconds(cue_start): cue_end = round(cue_end + 0.001, 3)`.
   - Updated `_extract_cue_id_and_text`:
     - Normalizes tabs to spaces: `cleaned_block = raw_block.replace("\t", " ")`.
     - Filters out WebVTT/SRT timestamp timing lines matching `^\d{1,2}:[0-9:.,]+\s*-->\s*[0-9:.,]+`.
   - Updated `project_tokens_to_cues`:
     - Applies `_adjust_cue_timing` consistently across char-span, single-block, and multi-block fallback paths.
2. `tests/test_text_norm.py`:
   - Added 5 new adversarial unit tests:
     - `test_project_tokens_to_cues_enclosed_overlap_monotonicity`: verifies enclosed/inverted token intervals are monotonically ordered and validate against `validate_cues` and `webvtt`.
     - `test_project_tokens_to_cues_fallback_enclosed_overlap`: verifies fallback path without char spans also maintains strict monotonicity on enclosed intervals.
     - `test_project_tokens_to_cues_submillisecond_collapse_prevention`: verifies sub-millisecond durations do not crash WebVTT export.
     - `test_project_tokens_to_cues_tab_character_normalization`: verifies tabs are sanitized to spaces and pass `validate_cues`.
     - `test_project_tokens_to_cues_webvtt_timestamp_line_filtering`: verifies existing timing lines are stripped and do not create duplicate WebVTT headers.
3. `.agents/teamwork/teamwork_preview_swe_1/open_issues_ledger.md`:
   - Recorded resolution of extreme token-to-cue duration limits and cue generation edge cases.

---

## 3. Verification Record

- **Deep Verification (ran actual tests):**
  - `uv run --locked pytest`: **261 passed in 3.81s** (72 original + 111 speech model tests + 78 text norm tests).
  - `uv run --locked ruff check .`: **All checks passed!**
  - `uv run --locked ruff format --check .`: **51 files already formatted.**
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

- **Remaining risk:** Live acoustic alignment against noisy audio will require CTC/HMM alignment engines (scheduled for Increments 2 and 4). Increment 1 contracts, token normalizers, and reverse cue projectors are fully verified, defensively hardened, and 100% covered by 261 automated tests.
- **Next step:** Review round 3 is complete. Proceed to clean git commit amend or commit creation and handoff to orchestrator.
