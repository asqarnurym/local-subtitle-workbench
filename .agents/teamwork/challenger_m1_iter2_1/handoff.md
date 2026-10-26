# Adversarial Verification Report: Increment 6 Milestone 1 Iteration 2

**Agent**: challenger_m1_iter2_1  
**Target**: `src/subtitle_workbench/corpora.py` (`parse_timit_phn`, `parse_timit_wrd`)  
**Parent Orchestrator**: d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Working Directory**: `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\challenger_m1_iter2_1`  
**Target Branch**: `feature/increment-6-speech-benchmark`  
**Date**: 2026-10-26  
**Handoff Type**: Hard  
**Verdict**: APPROVE  
**Discipline**: Pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |)  

---

## 1. Observation

1. **Source Code Implementation in `src/subtitle_workbench/corpora.py`:**
   - In `parse_timit_phn` (lines 60-68):
     ```python
     stripped = line.strip()
     if not stripped:
         continue
     parts = stripped.split()
     if len(parts) != 3:
         raise CorpusFormatError(
             f"Malformed TIMIT .phn line {line_idx} in {path.name}: expected 3 tokens, got {len(parts)}"
         )
     ```
   - In `parse_timit_wrd` (lines 136-144):
     ```python
     stripped = line.strip()
     if not stripped:
         continue
     parts = stripped.split()
     if len(parts) != 3:
         raise CorpusFormatError(
             f"Malformed TIMIT .wrd line {line_idx} in {path.name}: expected 3 tokens, got {len(parts)}"
         )
     ```

2. **Empirical Stress-Testing of Column Counts:**
   - Executed dynamic test harness against `parse_timit_phn` and `parse_timit_wrd`:
     * 1-column lines (`"1600\n"`, `"sh\n"`, `"she\n"`):
       Result: Raised `CorpusFormatError` with verbatim message `expected 3 tokens, got 1`.
     * 2-column lines (`"0 1600\n"`, `"1600 sh\n"`, `"1600 she\n"`):
       Result: Raised `CorpusFormatError` with verbatim message `expected 3 tokens, got 2`.
     * 4-column lines (`"0 1600 sh extra\n"`, `"  0   1600   sh   extra  \n"`, `"0\t1600\tsh\textra\n"`, `"0 1600 she pronoun\n"`):
       Result: Raised `CorpusFormatError` with verbatim message `expected 3 tokens, got 4`.
     * 5-column lines (`"0 1600 sh extra col5\n"`, `"0 1600 she pronoun col5\n"`):
       Result: Raised `CorpusFormatError` with verbatim message `expected 3 tokens, got 5`.
     * 10-column lines (`"0 1600 sh c4 c5 c6 c7 c8 c9 c10\n"`, `"0 1600 she c4 c5 c6 c7 c8 c9 c10\n"`):
       Result: Raised `CorpusFormatError` with verbatim message `expected 3 tokens, got 10`.
     * 100-column lines:
       Result: Raised `CorpusFormatError` with verbatim message `expected 3 tokens, got 100`.

3. **Empirical Stress-Testing of Whitespace and Boundary Conditions:**
   - Empty files (`""`):
     Result: Returned empty list `[]` without error for both PHN and WRD parsers.
   - Whitespace-only files (`"   \n\n\t\t\r\n   \r\n"`):
     Result: Returned empty list `[]` without error for both PHN and WRD parsers.
   - Valid lines with leading/trailing spaces, tabs, and mixed blank lines with CRLF:
     Result: Correctly parsed all tokens, normalized timestamps, and skipped blank lines cleanly.
   - Files with missing trailing newline (`"   0    1600    sh   "`):
     Result: Correctly parsed without truncation or offset errors.
   - Multi-line files with error on line 2 (middle):
     Result: Raised `CorpusFormatError: Malformed TIMIT .phn line 2 in mid_bad.phn: expected 3 tokens, got 4`. Verbatim line number correctly identifies offending record.
   - Silence marker lines with extra/missing columns (`0 1600 h# extra`, `0 1600`):
     Result: Token validation occurs before silence marker filtering (`phone.lower() in TIMIT_SILENCE_TOKENS` at line 95), strictly rejecting malformed silence rows.

4. **Test Suite and Code Quality Verification:**
   - Benchmark test execution:
     `uv run --locked pytest tests/test_benchmark.py -v` -> 19 passed in 0.92s.
   - Metrics stress test execution:
     `uv run --locked pytest tests/test_metrics_stress.py -v` -> 10 passed in 2.31s.
   - Full regression test execution:
     `uv run --locked pytest` -> 666 passed, 1 skipped in 15.30s.
   - Linter execution:
     `uv run --locked ruff check .` -> `All checks passed!`.
   - Formatter execution:
     `uv run --locked ruff format --check .` -> `361 files already formatted`.
   - ASCII character inspection:
     `[OK] src/subtitle_workbench/corpora.py: pure ASCII`
     `[OK] src/subtitle_workbench/metrics.py: pure ASCII`
     `[OK] tests/test_benchmark.py: pure ASCII`
     `[OK] tests/test_metrics_stress.py: pure ASCII`
     `[OK] scripts/download_reference_corpora.py: pure ASCII`
     `[OK] src/subtitle_workbench/__init__.py: pure ASCII`

---

## 2. Logic Chain

1. From Observation 1, the defect flagged in Iteration 1 (`len(parts) < 3`) has been modified to `len(parts) != 3` in both `parse_timit_phn` (line 64) and `parse_timit_wrd` (line 140).
2. From Observation 2, lines with fewer than 3 columns (1, 2 columns) and lines with more than 3 columns (4, 5, 10, 100 columns) are strictly rejected with `CorpusFormatError`. The error message correctly reflects the exact token count observed.
3. From Observation 3, the stripping order (`stripped = line.strip(); if not stripped: continue; parts = stripped.split()`) ensures that leading and trailing whitespace, empty lines, Windows CRLF line endings, and whitespace-only files are handled gracefully without false-positive format errors.
4. From Observation 3, token count validation occurs prior to silence filtering or text normalization, preventing malformed silence or non-speech records from bypassing column structure enforcement.
5. From Observation 4, all existing 666 unit and integration tests continue to pass with 0 regressions, and the codebase satisfies all formatting, linting, and pure ASCII constraints.
6. Therefore, the column validation fix is robust, complete, and resilient against adversarial inputs.

---

## 3. Challenge Summary

**Overall risk assessment**: LOW

### Challenges

#### Challenge 1: Column Count Boundary Validation
- **Assumption challenged**: Whether `len(parts) != 3` completely eliminates under- and over-specified column vulnerabilities across varied whitespace and tab patterns.
- **Attack scenario**: Inject lines with 1, 2, 4, 5, 10, 100 columns containing mixed spaces and tabs (`\t`), CRLF endings, and trailing whitespace.
- **Result**: [PASS] All malformed variations raised `CorpusFormatError` with precise line numbers and column counts.

#### Challenge 2: Empty File and Whitespace Resilience
- **Assumption challenged**: Whether tightening column checks inadvertently breaks empty files, blank lines, or lines without trailing newlines.
- **Attack scenario**: Ingest files containing empty string, whitespace only, blank line sandwiches, and files without trailing newlines.
- **Result**: [PASS] Empty and whitespace files return `[]`; valid lines surrounded by blank lines parse accurately.

---

## 4. Stress Test Results

| Test Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| TIMIT PHN 1-column line (`1600\n`) | Raise `CorpusFormatError` (got 1) | Raised `CorpusFormatError` | [PASS] |
| TIMIT PHN 1-column line (`sh\n`) | Raise `CorpusFormatError` (got 1) | Raised `CorpusFormatError` | [PASS] |
| TIMIT PHN 2-column line (`0 1600\n`) | Raise `CorpusFormatError` (got 2) | Raised `CorpusFormatError` | [PASS] |
| TIMIT PHN 2-column line (`1600 sh\n`) | Raise `CorpusFormatError` (got 2) | Raised `CorpusFormatError` | [PASS] |
| TIMIT PHN 4-column line (`0 1600 sh extra\n`) | Raise `CorpusFormatError` (got 4) | Raised `CorpusFormatError` | [PASS] |
| TIMIT PHN 4-column with spaces (`  0   1600   sh   extra  \n`) | Raise `CorpusFormatError` (got 4) | Raised `CorpusFormatError` | [PASS] |
| TIMIT PHN 4-column with tabs (`0\t1600\tsh\textra\n`) | Raise `CorpusFormatError` (got 4) | Raised `CorpusFormatError` | [PASS] |
| TIMIT PHN 5-column line (`0 1600 sh extra col5\n`) | Raise `CorpusFormatError` (got 5) | Raised `CorpusFormatError` | [PASS] |
| TIMIT PHN 10-column line (`0 1600 sh c4..c10\n`) | Raise `CorpusFormatError` (got 10) | Raised `CorpusFormatError` | [PASS] |
| TIMIT PHN 100-column line | Raise `CorpusFormatError` (got 100) | Raised `CorpusFormatError` | [PASS] |
| TIMIT WRD 1-column line (`1600\n`) | Raise `CorpusFormatError` (got 1) | Raised `CorpusFormatError` | [PASS] |
| TIMIT WRD 1-column line (`she\n`) | Raise `CorpusFormatError` (got 1) | Raised `CorpusFormatError` | [PASS] |
| TIMIT WRD 2-column line (`0 1600\n`) | Raise `CorpusFormatError` (got 2) | Raised `CorpusFormatError` | [PASS] |
| TIMIT WRD 2-column line (`1600 she\n`) | Raise `CorpusFormatError` (got 2) | Raised `CorpusFormatError` | [PASS] |
| TIMIT WRD 4-column line (`0 1600 she pronoun\n`) | Raise `CorpusFormatError` (got 4) | Raised `CorpusFormatError` | [PASS] |
| TIMIT WRD 4-column with spaces (`  0   1600   she   pronoun  \n`) | Raise `CorpusFormatError` (got 4) | Raised `CorpusFormatError` | [PASS] |
| TIMIT WRD 4-column with tabs (`0\t1600\tshe\tpronoun\n`) | Raise `CorpusFormatError` (got 4) | Raised `CorpusFormatError` | [PASS] |
| TIMIT WRD 5-column line (`0 1600 she pronoun col5\n`) | Raise `CorpusFormatError` (got 5) | Raised `CorpusFormatError` | [PASS] |
| TIMIT WRD 10-column line (`0 1600 she c4..c10\n`) | Raise `CorpusFormatError` (got 10) | Raised `CorpusFormatError` | [PASS] |
| TIMIT WRD 100-column line | Raise `CorpusFormatError` (got 100) | Raised `CorpusFormatError` | [PASS] |
| TIMIT PHN empty file (`""`) | Return `[]` | Returned `[]` | [PASS] |
| TIMIT WRD empty file (`""`) | Return `[]` | Returned `[]` | [PASS] |
| TIMIT PHN whitespace-only file (`"  \n\t\r\n"`) | Return `[]` | Returned `[]` | [PASS] |
| TIMIT WRD whitespace-only file (`"  \n\t\r\n"`) | Return `[]` | Returned `[]` | [PASS] |
| TIMIT PHN leading/trailing whitespace & CRLF | Correctly parse cues | Parsed 2 cues cleanly | [PASS] |
| TIMIT WRD leading/trailing whitespace & CRLF | Correctly parse words | Parsed 2 words cleanly | [PASS] |
| TIMIT PHN middle error (line 2, 4 tokens) | Raise `CorpusFormatError` with line 2 | Reported line 2, got 4 | [PASS] |
| TIMIT WRD middle error (line 2, 4 tokens) | Raise `CorpusFormatError` with line 2 | Reported line 2, got 4 | [PASS] |
| TIMIT PHN silence token with 4 columns | Reject before filtering | Raised `CorpusFormatError` | [PASS] |
| TIMIT PHN silence token with 2 columns | Reject before filtering | Raised `CorpusFormatError` | [PASS] |
| TIMIT PHN no trailing newline + spaces | Parse 1 cue cleanly | Parsed 1 cue cleanly | [PASS] |
| TIMIT WRD no trailing newline + spaces | Parse 1 word cleanly | Parsed 1 word cleanly | [PASS] |

---

## 5. Caveats

1. Real TIMIT files in binary LDC distributions may carry SPHERE headers in `.wav` audio files; `parse_timit_phn` and `parse_timit_wrd` operate strictly on text annotation files (`.phn`, `.wrd`).
2. Text normalization for words in `parse_timit_wrd` delegates to `normalize_text_spans` from `src/subtitle_workbench/text_norm.py`.

---

## 6. Conclusion

**Verdict: APPROVE**

The token validation fix in `src/subtitle_workbench/corpora.py` has been empirically stress-tested across 32 adversarial test scenarios. All boundary conditions, malformed column configurations, whitespace anomalies, and silence rows are defensively validated with zero regressions in the 666-test regression suite.

---

## 7. Verification Method

To independently verify:

1. **Run full adversarial test harness:**
   ```powershell
   uv run python -c "
   import tempfile
   from pathlib import Path
   from subtitle_workbench.corpora import parse_timit_phn, parse_timit_wrd
   from subtitle_workbench.metrics import CorpusFormatError

   with tempfile.TemporaryDirectory() as tmpdir:
       p = Path(tmpdir) / 'test.phn'
       for text in ['1600\n', '0 1600\n', '0 1600 sh extra\n', '0 1600 sh c4 c5 c6 c7 c8 c9 c10\n']:
           p.write_text(text, encoding='utf-8')
           try:
               parse_timit_phn(p)
               assert False, f'Failed to reject: {text}'
           except CorpusFormatError:
               pass
       print('[OK] All column rejections verified.')
   "
   ```

2. **Run project test gates:**
   ```powershell
   uv run --locked pytest tests/test_benchmark.py -v
   uv run --locked pytest tests/test_metrics_stress.py -v
   uv run --locked pytest
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```

### Invalidation Conditions
- Any line in `.phn` or `.wrd` with $N \ne 3$ columns being parsed without raising `CorpusFormatError`.
- Any regression in `pytest` test suite.
