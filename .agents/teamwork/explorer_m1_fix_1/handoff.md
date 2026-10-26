# Handoff Report: TIMIT Parser Defect Analysis & Fix Strategy

- **Agent**: `explorer_m1_fix_1`
- **Working Directory**: `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_m1_fix_1`
- **Target Files**: `src/subtitle_workbench/corpora.py`, `tests/test_benchmark.py`
- **Parent Orchestrator**: `d7780ee7-0d12-43b1-8cad-0dd6f3550ad6`
- **Date**: 2026-10-26
- **Handoff Type**: Hard
- **Discipline**: Strictly pure ASCII ([+], [-], [*], [OK], [FAIL], ->, |)

---

## 1. Observation

1. **Vulnerability in `parse_timit_phn` and `parse_timit_wrd`:**
   - In `src/subtitle_workbench/corpora.py`, lines 63-68:
     ```python
     parts = stripped.split()
     if len(parts) < 3:
         raise CorpusFormatError(
             f"Malformed TIMIT .phn line {line_idx} in {path.name}: expected 3 tokens, got {len(parts)}"
         )
     ```
   - In `src/subtitle_workbench/corpora.py`, lines 140-145:
     ```python
     parts = stripped.split()
     if len(parts) < 3:
         raise CorpusFormatError(
             f"Malformed TIMIT .wrd line {line_idx} in {path.name}: expected 3 tokens, got {len(parts)}"
         )
     ```

2. **Empirical Defect Reproduction:**
   - Command 1:
     ```powershell
     uv run python -c "from pathlib import Path; from subtitle_workbench.corpora import parse_timit_phn; p = Path('test_extra.phn'); p.write_text('0 1600 sh extra\n'); print('PHN returned:', parse_timit_phn(p)); p.unlink()"
     ```
     Observed output:
     `PHN returned: [PhonemeCue(phoneme='sh', start=0.0, end=0.1, confidence=1.0)]`
     Result: Extra column `extra` was silently dropped without error.

   - Command 2:
     ```powershell
     uv run python -c "from pathlib import Path; from subtitle_workbench.corpora import parse_timit_wrd; p = Path('test_extra.wrd'); p.write_text('0 1600 she pronoun extra\n'); print('WRD returned:', parse_timit_wrd(p)); p.unlink()"
     ```
     Observed output:
     `WRD returned: [WordToken(id='w_0000', text='she', normalized='she', start=0.0, end=0.1, confidence=1.0, phonemes=[], char_start=0, char_end=3)]`
     Result: Extra columns were silently dropped without error.

3. **Blank Lines Guard Evaluation:**
   - In `src/subtitle_workbench/corpora.py`, lines 60-62 and lines 136-138:
     ```python
     stripped = line.strip()
     if not stripped:
         continue
     ```
   - Empirical verification:
     ```powershell
     uv run python -c "from pathlib import Path; from subtitle_workbench.corpora import parse_timit_phn, parse_timit_wrd; p = Path('test_blanks.phn'); p.write_text('\n\n0 1600 sh\n   \n1600 3200 iy\n\n'); print('Blanks cues:', len(parse_timit_phn(p))); p.unlink()"
     ```
     Observed output: `Blanks cues: 2`.
     Result: Blank and whitespace-only lines are skipped before token splitting.

4. **Existing Test Suite Baseline:**
   - Command: `uv run --locked pytest tests/test_benchmark.py`
   - Output: `16 passed in 0.73s`.

---

## 2. Logic Chain

1. From Observation 1, `parse_timit_phn` and `parse_timit_wrd` use `if len(parts) < 3:` to validate the token count per line.
2. From Observation 2, when `len(parts) > 3` (e.g. 4 or 5 tokens), `len(parts) < 3` evaluates to `False`. The parsers extract `parts[2]` as the phone or word label and silently discard `parts[3:]`.
3. The error message explicitly formatted in both functions states `expected 3 tokens, got {len(parts)}`, confirming that exactly 3 tokens is the architectural contract.
4. From Observation 3, blank lines and whitespace-only lines are pruned by `if not stripped: continue` prior to `stripped.split()`. Thus, tightening the token check from `len(parts) < 3` to `len(parts) != 3` cannot falsely reject blank lines.
5. In standard NIST TIMIT dataset files, comment syntax (`#` or `;`) does not exist; `#` is part of the phone token set (e.g. `h#`). Malformed files containing comment markers or inline trailing comments will either fail `len(parts) != 3` or `int(parts[0])`, properly surfacing formatting corruption.
6. Therefore, substituting `len(parts) != 3` for `len(parts) < 3` in both locations fully resolves the defect reported by `challenger_m1_1` without regressing valid inputs.

---

## 3. Caveats

- Standard TIMIT files are ASCII-encoded without headers or comments; the parser assumes UTF-8 / ASCII compatibility via `read_text(encoding="utf-8", errors="replace")`.
- If an upstream pipeline intentionally produced custom 4-column TIMIT variants, those must be preprocessed or normalized, as NIST TIMIT ground truth strictly mandates 3 columns.
- No source files have been modified in this turn in compliance with the read-only explorer constraint.

---

## 4. Conclusion

The defect reported by `challenger_m1_1` is fully verified and reproducible.
The fix is surgical and ready for implementation by `worker_m1_1`:
1. In `src/subtitle_workbench/corpora.py`:
   - Line 64: change `if len(parts) < 3:` to `if len(parts) != 3:`.
   - Line 141: change `if len(parts) < 3:` to `if len(parts) != 3:`.
2. In `tests/test_benchmark.py`:
   - Add negative unit test assertions for lines with >3 tokens in `test_timit_phn_parser_malformed_and_monotonicity` and `test_timit_wrd_parser_malformed_and_monotonicity`.
   - Add dedicated test `test_timit_parsers_preserve_blank_lines` verifying blank/whitespace line handling.
3. Machine-applicable patch prepared at:
   `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_m1_fix_1\fix_timit_token_validation.patch`.

---

## 5. Verification Method

To verify the proposed fix after application:

1. **Apply patch or make edits**:
   Verify `git diff` matches `fix_timit_token_validation.patch`.

2. **Run Benchmark Tests**:
   ```powershell
   uv run --locked pytest tests/test_benchmark.py -v
   ```
   Expected: All tests pass (including new >3 tokens and blank lines tests).

3. **Verify Full Test Suite**:
   ```powershell
   uv run --locked pytest
   ```
   Expected: 100% pass rate.

4. **Verify Linter and Formatter**:
   ```powershell
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   Expected: 0 warnings, 0 format diffs.

5. **Verify Extra Columns Negative Test in CLI**:
   ```powershell
   uv run python -c "from pathlib import Path; from subtitle_workbench.corpora import parse_timit_phn; p = Path('test_extra.phn'); p.write_text('0 1600 sh extra\n'); parse_timit_phn(p)"
   ```
   Expected: Raises `CorpusFormatError: Malformed TIMIT .phn line 1 in test_extra.phn: expected 3 tokens, got 4`.

Invalidation condition:
- Any valid TIMIT file or synthetic benchmark utterance raises `CorpusFormatError`.
