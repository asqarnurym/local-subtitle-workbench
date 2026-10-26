# Review & Challenge Report: Milestone 1 Iteration 2 Remediation Audit

**Agent**: reviewer_m1_iter2_1  
**Roles**: reviewer, critic  
**Parent Orchestrator**: d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Target Commit**: `daefa6a` (`feat(benchmark): implement reference corpora loaders and boundary evaluation metrics`)  
**Working Directory**: `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\reviewer_m1_iter2_1`  
**Verdict**: APPROVE  
**Discipline**: Pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |)  

---

## 1. Observation

1. **Inspection of `src/subtitle_workbench/corpora.py`:**
   - Lines 58-69 (`parse_timit_phn`):
     ```python
     lines = content.splitlines()
     for line_idx, line in enumerate(lines, start=1):
         stripped = line.strip()
         if not stripped:
             continue
         parts = stripped.split()
         if len(parts) != 3:
             raise CorpusFormatError(
                 f"Malformed TIMIT .phn line {line_idx} in {path.name}: "
                 f"expected 3 tokens, got {len(parts)}"
             )
     ```
   - Lines 133-145 (`parse_timit_wrd`):
     ```python
     lines = content.splitlines()
     w_idx = 0
     for line_idx, line in enumerate(lines, start=1):
         stripped = line.strip()
         if not stripped:
             continue
         parts = stripped.split()
         if len(parts) != 3:
             raise CorpusFormatError(
                 f"Malformed TIMIT .wrd line {line_idx} in {path.name}: "
                 f"expected 3 tokens, got {len(parts)}"
             )
     ```
   - Both parsers now enforce `len(parts) != 3`, properly rejecting both `< 3` tokens and `> 3` tokens with `CorpusFormatError`.
   - Empty and whitespace-only lines are checked via `if not stripped: continue` prior to token splitting, safely ignoring blank lines without triggering false-positive syntax errors.

2. **Inspection of `tests/test_benchmark.py`:**
   - Lines 75-87:
     ```python
     # Malformed line (fewer than 3 tokens)
     bad_line_file = tmp_path / "bad_line.phn"
     bad_line_file.write_text("0 1600\n", encoding="utf-8")
     with pytest.raises(CorpusFormatError, match="Malformed TIMIT .phn.*expected 3 tokens, got 2"):
         parse_timit_phn(bad_line_file)

     # Malformed line (more than 3 tokens)
     extra_tokens_file = tmp_path / "extra_tokens.phn"
     extra_tokens_file.write_text("0 1600 sh extra\n", encoding="utf-8")
     with pytest.raises(CorpusFormatError, match="Malformed TIMIT .phn.*expected 3 tokens, got 4"):
         parse_timit_phn(extra_tokens_file)
     ```
   - Lines 142-154:
     ```python
     bad_file = tmp_path / "bad.wrd"
     bad_file.write_text("1600 she\n", encoding="utf-8")
     with pytest.raises(CorpusFormatError, match="Malformed TIMIT .wrd.*expected 3 tokens, got 2"):
         parse_timit_wrd(bad_file)

     # Malformed line (more than 3 tokens)
     extra_file = tmp_path / "extra.wrd"
     extra_file.write_text("0 1600 she pronoun extra\n", encoding="utf-8")
     with pytest.raises(CorpusFormatError, match="Malformed TIMIT .wrd.*expected 3 tokens, got 5"):
         parse_timit_wrd(extra_file)
     ```
   - Lines 161-172:
     ```python
     def test_timit_parsers_preserve_blank_lines(tmp_path: Path) -> None:
         """Verify TIMIT parsers skip empty and whitespace-only lines without error."""
         phn_file = tmp_path / "blanks.phn"
         phn_file.write_text("\n\n0 1600 sh\n   \n1600 3200 iy\n\n", encoding="utf-8")
         cues = parse_timit_phn(phn_file)
         assert len(cues) == 2

         wrd_file = tmp_path / "blanks.wrd"
         wrd_file.write_text("\n\n0 1600 she\n  \t \n1600 3200 had\n\n", encoding="utf-8")
         words = parse_timit_wrd(wrd_file)
         assert len(words) == 2
     ```

3. **Independent Automated Tool Verification:**
   - `uv run --locked pytest tests/test_benchmark.py`:
     Result: `19 passed in 0.75s` (Exit code 0).
   - `uv run --locked ruff check .`:
     Result: `All checks passed!` (Exit code 0).
   - `uv run --locked ruff format --check .`:
     Result: `361 files already formatted` (Exit code 0).
   - `uv run --locked pytest tests/test_metrics_stress.py`:
     Result: `10 passed in 2.25s` (Exit code 0).
   - `uv run --locked pytest`:
     Result: `666 passed, 1 skipped in 16.25s` (Exit code 0).

4. **Adversarial Stress Testing:**
   Executed programmatic boundary tests on `parse_timit_phn` and `parse_timit_wrd`:
   - 1-token line (`"0\n"`): rejected with `CorpusFormatError: expected 3 tokens, got 1`.
   - 4-token line in `.phn` (`"0 1600 sh extra\n"`): rejected with `CorpusFormatError: expected 3 tokens, got 4`.
   - 4-token line in `.wrd` (`"0 1600 word extra\n"`): rejected with `CorpusFormatError: expected 3 tokens, got 4`.
   - Complex whitespace and tabs (`"\n   \n\t  \n0 1600 sh\n\n1600 3200 iy\n  \n"`): successfully parsed into exactly 2 valid cues/tokens without exception.

5. **Integrity Violation Audit:**
   - Hardcoded outputs check: None found in `corpora.py` or `metrics.py`. Calculations are dynamic and mathematically grounded.
   - Facade or dummy implementations: None. All parsers build real instances of `PhonemeCue` and `WordToken` with boundary verification.
   - Test shortcuts or external cheating: All tests execute locally offline in < 1s without network access.
   - Attestation integrity: Verification outputs independently reproduced and confirmed.

---

## 2. Logic Chain

1. In Observation 1, replacing `len(parts) < 3` with `len(parts) != 3` ensures that any TIMIT line containing anything other than exactly 3 whitespace-delimited tokens raises `CorpusFormatError`. This prevents silent dropping of trailing tokens when input files are corrupted or formatted unexpectedly.
2. In Observation 1 and 4, the initial check `stripped = line.strip(); if not stripped: continue` ensures that trailing or inter-line whitespace does not reach token counting, guaranteeing robust parsing of real-world text files that often include trailing blank lines.
3. In Observation 2, `tests/test_benchmark.py` includes explicit tests asserting both `< 3` tokens (2 tokens) and `> 3` tokens (4 and 5 tokens), as well as a dedicated blank/whitespace line test `test_timit_parsers_preserve_blank_lines`.
4. In Observation 3, all mandatory verification gates passed cleanly: unit tests (19/19), stress tests (10/10), full regression suite (666 passed, 1 skipped), and static checks (ruff check and ruff format).
5. In Observation 5, no integrity violations exist. The implementation is correct, defensive, and adheres to project engineering standards.

---

## 3. Caveats

1. The TIMIT parser assumes standard whitespace splitting (`str.split()`) which normalizes tabs and spaces. This is standard for TIMIT `.phn` and `.wrd` distribution files.
2. The benchmark tests run on synthesized offline utterances generated by `stage_synthetic_benchmark`, ensuring full offline reproducibility without downloading restricted corpora.

---

## 4. Conclusion

The remediation in commit `daefa6a` completely and accurately fixes the line validation defect in `corpora.py` and establishes comprehensive unit and stress tests in `test_benchmark.py`. All verification gates pass with 100% compliance.

**Final Verdict**: APPROVE

---

## 5. Verification Method

To independently reproduce this verification:

1. **Verify git commit and working tree state:**
   ```powershell
   git log -n 1 --stat daefa6a
   git status
   ```

2. **Run targeted benchmark tests:**
   ```powershell
   uv run --locked pytest tests/test_benchmark.py -v
   ```
   *Expected*: 19 passed in < 1.0s.

3. **Run linter and formatter:**
   ```powershell
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   *Expected*: All checks passed, 361 files already formatted.

4. **Run stress tests:**
   ```powershell
   uv run --locked pytest tests/test_metrics_stress.py -v
   ```
   *Expected*: 10 passed in < 3.0s.

5. **Run full regression test suite:**
   ```powershell
   uv run --locked pytest
   ```
   *Expected*: 666 passed, 1 skipped.

### Invalidation Conditions
- Any line with != 3 tokens parsed without raising `CorpusFormatError`.
- Any blank or whitespace line causing a parsing failure.
- Any test failure in `tests/test_benchmark.py` or `tests/test_metrics_stress.py`.
