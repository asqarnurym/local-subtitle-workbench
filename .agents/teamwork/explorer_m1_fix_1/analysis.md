# Defect Analysis and Fix Strategy: TIMIT Token Count Validation

- **Target Files**: `src/subtitle_workbench/corpora.py`, `tests/test_benchmark.py`
- **Defect Origin**: Adversarial challenge report by `challenger_m1_1` (`REQUEST_CHANGES`)
- **Author**: `explorer_m1_fix_1`
- **Date**: 2026-10-26
- **Discipline**: Strictly pure ASCII ([+], [-], [*], [OK], [FAIL], ->, |)

---

## 1. Executive Summary

During adversarial testing of Increment 6 Milestone 1 by `challenger_m1_1`, a vulnerability was uncovered in `parse_timit_phn` and `parse_timit_wrd` in `src/subtitle_workbench/corpora.py`. Specifically, lines containing more than 3 whitespace-separated tokens (e.g. `0 1600 sh extra` or `0 1600 she pronoun extra`) were silently accepted, with trailing columns discarded rather than raising `CorpusFormatError`.

This analysis provides the rigorous rationale, code diffs, regression test additions, and verification methodology to safely transition the condition from `len(parts) < 3` to `len(parts) != 3`, confirming that comments, blank lines, and legitimate tabular inputs are unaffected.

---

## 2. Problem Context and Defect Analysis

### 2.1 Code Review: `corpora.py` Lines 63-68 and 140-145

In `parse_timit_phn` (lines 63-68):
```python
parts = stripped.split()
if len(parts) < 3:
    raise CorpusFormatError(
        f"Malformed TIMIT .phn line {line_idx} in {path.name}: expected 3 tokens, got {len(parts)}"
    )
```

In `parse_timit_wrd` (lines 140-145):
```python
parts = stripped.split()
if len(parts) < 3:
    raise CorpusFormatError(
        f"Malformed TIMIT .wrd line {line_idx} in {path.name}: expected 3 tokens, got {len(parts)}"
    )
```

### 2.2 Root Cause

Both functions split each non-empty line using `stripped.split()`.
When an input line contains 4 or more tokens:
1. `len(parts) < 3` evaluates to `False`.
2. Execution proceeds to:
   - `phone = parts[2]` (in `parse_timit_phn`), or
   - `word_text = parts[2]` (in `parse_timit_wrd`).
3. Tokens from index 3 onward (`parts[3:]`) are discarded without notification or error.

### 2.3 Rationale for Strict Validation (`len(parts) != 3`)

1. **TIMIT Standard Specification (NIST Speech Disc 1-1.1)**:
   - TIMIT phonetic (`.phn`) files define exact 3-field records: `<start_sample> <end_sample> <phone_symbol>`.
   - TIMIT word (`.wrd`) files define exact 3-field records: `<start_sample> <end_sample> <word_text>`.
   - The diagnostic error string itself explicitly states: `expected 3 tokens, got {len(parts)}`, proving the intended invariant was strict cardinality = 3.
2. **Defensive Boundary Validation**:
   - Ingesting a 4-column file (such as Praat interval dumps `<start> <end> <label> <comment>` or aligned tables with extra metadata) should fail early rather than silently dropping information.
   - Requirement R1 explicitly mandated: "Test malformed TIMIT .phn and .wrd files (negative timestamps, non-monotonic times, extra/missing columns, invalid floats). Verify CorpusFormatError is raised defensively."
3. **Safety of `!= 3`**:
   - Since `stripped` is guaranteed non-empty by the preceding guard, `len(parts)` is always >= 1.
   - `len(parts) != 3` covers both under-length (`len(parts) in (1, 2)`) and over-length (`len(parts) >= 4`), rejecting any structural deviations.

---

## 3. Preservation of Comments and Blank Lines

### 3.1 Blank Lines Behavior

In both `parse_timit_phn` and `parse_timit_wrd`:
```python
lines = content.splitlines()
for line_idx, line in enumerate(lines, start=1):
    stripped = line.strip()
    if not stripped:
        continue
```
- Empty lines (`""`) or lines consisting solely of whitespace characters (`"   "`, `"\t"`, `"\r"`) evaluate `not stripped` to `True`.
- They trigger `continue` before line splitting occurs.
- Therefore, blank lines at the beginning, end, or intermediate positions of the file remain completely safe and are unaffected by changing `< 3` to `!= 3`.

### 3.2 Comments Behavior

- Standard TIMIT files do NOT contain comment lines (`#` or `;`).
- Notice that in TIMIT, `#` is an essential phone identifier: `h#` designates sentence beginning and ending acoustic silence.
- If a malformed file includes comment lines:
  * Single-word comment (`#` or `;`): `len(parts) == 1 != 3` -> raises `CorpusFormatError`.
  * Two-word comment (`# comment`): `len(parts) == 2 != 3` -> raises `CorpusFormatError`.
  * Three-word comment (`# foo bar`): `int(parts[0])` fails on `#` with `ValueError` -> raises `CorpusFormatError: Non-integer sample boundary`.
  * Multi-word comment (`# this is a comment`): `len(parts) == 5 != 3` -> raises `CorpusFormatError`.
  * Inline comment appended to a valid line (`0 1600 sh # silence comment`): previously silently dropped the comment; now raises `CorpusFormatError: expected 3 tokens, got 5`.
- This behavior strictly enforces NIST TIMIT dataset compliance and prevents corrupt annotations from entering the speech benchmark pipeline.

---

## 4. Concrete Implementation Plan

### 4.1 Production Code (`src/subtitle_workbench/corpora.py`)

Two surgical 1-character replacements:

```python
# src/subtitle_workbench/corpora.py, line 64
<<<<
        if len(parts) < 3:
====
        if len(parts) != 3:
>>>>
```

```python
# src/subtitle_workbench/corpora.py, line 141
<<<<
        if len(parts) < 3:
====
        if len(parts) != 3:
>>>>
```

### 4.2 Test Suite Additions (`tests/test_benchmark.py`)

1. In `test_timit_phn_parser_malformed_and_monotonicity`:
   Add negative test for lines with 4 tokens:
   ```python
   # Malformed line (more than 3 tokens / extra columns)
   extra_tokens_file = tmp_path / "extra_tokens.phn"
   extra_tokens_file.write_text("0 1600 sh extra\n", encoding="utf-8")
   with pytest.raises(CorpusFormatError, match="expected 3 tokens, got 4"):
       parse_timit_phn(extra_tokens_file)
   ```

2. In `test_timit_wrd_parser_malformed_and_monotonicity`:
   Add negative test for lines with 4 tokens:
   ```python
   # Malformed line (more than 3 tokens / extra columns)
   extra_tokens_wrd = tmp_path / "extra_tokens.wrd"
   extra_tokens_wrd.write_text("1600 6400 she pronoun\n", encoding="utf-8")
   with pytest.raises(CorpusFormatError, match="expected 3 tokens, got 4"):
       parse_timit_wrd(extra_tokens_wrd)
   ```

3. Add new dedicated test `test_timit_parsers_preserve_blank_lines`:
   ```python
   def test_timit_parsers_preserve_blank_lines(tmp_path: Path) -> None:
       """Verify TIMIT parsers safely ignore blank and whitespace-only lines."""
       phn_file = tmp_path / "blank_lines.phn"
       phn_file.write_text("\n\n0 1600 sh\n   \n1600 3200 iy\n\n", encoding="utf-8")
       cues = parse_timit_phn(phn_file)
       assert len(cues) == 2
       assert cues[0].phoneme == "sh"
       assert cues[1].phoneme == "iy"

       wrd_file = tmp_path / "blank_lines.wrd"
       wrd_file.write_text("\n\n0 1600 she\n   \n1600 3200 had\n\n", encoding="utf-8")
       words = parse_timit_wrd(wrd_file)
       assert len(words) == 2
       assert words[0].text == "she"
       assert words[1].text == "had"
   ```

---

## 5. Artifact Reference

A complete, machine-applicable patch has been prepared at:
`C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_m1_fix_1\fix_timit_token_validation.patch`

---

## 6. Verification and Regression Defense

To verify the implementation once applied by `worker_m1_1`:
1. Execute unit tests:
   `uv run --locked pytest tests/test_benchmark.py -v`
2. Execute full repository test suite:
   `uv run --locked pytest`
3. Run linters:
   `uv run --locked ruff check .`
   `uv run --locked ruff format --check .`
4. Confirm reproduction commands now raise `CorpusFormatError`.
