# Adversarial Challenge Report: Increment 6 Milestone 1

**Agent**: challenger_m1_1  
**Target**: `src/subtitle_workbench/corpora.py` and `scripts/download_reference_corpora.py`  
**Parent Orchestrator**: d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Date**: 2026-10-26  
**Handoff Type**: Hard  
**Verdict**: REQUEST_CHANGES  

---

## 1. Observation

1. **TIMIT Line Token Count Validation Bug in `src/subtitle_workbench/corpora.py`:**
   - In `parse_timit_phn` (lines 63-68):
     ```python
     parts = stripped.split()
     if len(parts) < 3:
         raise CorpusFormatError(
             f"Malformed TIMIT .phn line {line_idx} in {path.name}: expected 3 tokens, got {len(parts)}"
         )
     ```
   - In `parse_timit_wrd` (lines 140-145):
     ```python
     parts = stripped.split()
     if len(parts) < 3:
         raise CorpusFormatError(
             f"Malformed TIMIT .wrd line {line_idx} in {path.name}: expected 3 tokens, got {len(parts)}"
         )
     ```
   - Empirical test execution with 4-token line `0 1600 sh extra\n`:
     Command:
     ```python
     p.write_text("0 1600 sh extra\n")
     parse_timit_phn(p)
     ```
     Result: Returned `[PhonemeCue(phoneme='sh', start=0.0, end=0.1, confidence=1.0)]` without raising `CorpusFormatError`. Extra column `extra` was silently dropped.
   - Empirical test execution on `parse_timit_wrd` with line `0 1600 she pronoun extra\n`:
     Command:
     ```python
     w.write_text("0 1600 she pronoun extra\n")
     parse_timit_wrd(w)
     ```
     Result: Returned `[WordToken(id='w_0000', text='she', normalized='she', start=0.0, end=0.1, confidence=1.0, phonemes=[], char_start=0, char_end=3)]` without raising `CorpusFormatError`. Extra columns were silently dropped.

2. **Malformed TIMIT Inputs Correctly Rejected:**
   - Negative start sample (`-100 1600 sh`): Raised `CorpusFormatError: Negative start sample -100 on line 1`.
   - Inverted/equal boundaries (`1600 1600 sh`, `2000 1000 sh`): Raised `CorpusFormatError: Non-positive interval [...]`.
   - Non-monotonic timestamps (`0 1600 sh\n1200 3200 iy`): Raised `CorpusFormatError: Non-monotonic timestamp on line 2: start 1200 < previous end 1600`.
   - Inverted lines (`3200 4800 sh\n1600 3200 iy`): Raised `CorpusFormatError: Non-monotonic timestamp on line 2: start 1600 < previous end 4800`.
   - Non-integer / float strings (`0.5 1600 sh`, `0 1600.5 sh`, `nan 1600 sh`, `inf 1600 sh`, `1e4 2e4 sh`): Raised `CorpusFormatError: Non-integer sample boundary on line 1`.
   - Missing columns (`1600`, `0 1600`): Raised `CorpusFormatError: Malformed TIMIT .phn line 1: expected 3 tokens, got 1` (or 2).
   - Non-positive sample rate (`sample_rate <= 0`): Raised `CorpusFormatError: sample_rate must be positive`.

3. **Buckeye TextGrid Edge Cases:**
   - Empty tiers (`size = 0`): Correctly returned `[]`.
   - Empty intervals (`intervals: size = 0` in `words` tier): Correctly returned `[]`.
   - Missing words tier (`phones` tier only): Correctly returned `[]`.
   - All 10 Buckeye non-speech tokens (`{B_TRANS}`, `{E_TRANS}`, `<IVER>`, `<LAUGH>`, `<VOCNOISE>`, `<NOISE>`, `SIL`, `<SIL>`, `UNKNOWN`, `<EXCLUDE>`): Case-insensitively filtered out across both word tier and phone tier.
   - Phones with mixed non-speech tokens inside a word: Successfully stripped non-speech tokens (`<NOISE>`) while retaining legitimate phonetic segments (`t`, `eh`, `s`).

4. **Synthetic Benchmark Staging (`stage_synthetic_benchmark`):**
   - Staged 10 utterances (`spk01_utt01` through `spk03_utt04`) into isolated temporary directory.
   - Verified all 10 `.wav` files are valid uncompressed mono PCM16 at 16000 Hz passing `validate_wav` and `load_wav`.
   - Verified audio RMS energy is in range [0.12, 0.15], strictly exceeding the minimum threshold ($RMS \ge 10^{-4}$).
   - Verified exact mathematical duration correspondence across `.wav`, `.phn`, `.wrd`, and `.TextGrid`:
     * Total audio samples matched file durations ($t = \text{samples} / 16000.0$).
     * Word boundaries matched phone sequences ($w_{start} == p_{first, start}$, $w_{end} == p_{last, end}$).
     * Word counts (28 total across 10 utterances) and phone counts (79 total) matched ground truth specifications.

5. **Reference Corpora CLI Script (`scripts/download_reference_corpora.py`):**
   - Executed `--corpus timit` with absent directory: Output clean guidance message pointing to LDC license (LDC93S1) and exited with status 0.
   - Executed `--corpus buckeye` with absent directory: Output clean download link pointing to Ohio State repository and exited with status 0.
   - Executed with invalid corpus name (`--corpus invalid_name`): Rejected with standard argparse exit code 2.
   - Executed `--offline-synthetic`: Generated all 10 utterances cleanly with status 0.

---

## 2. Logic Chain

1. From Observation 1, the task requirements specifically state:
   *"1. Test malformed TIMIT .phn and .wrd files (negative timestamps, non-monotonic times, extra/missing columns, invalid floats). Verify CorpusFormatError is raised defensively."*
2. In `src/subtitle_workbench/corpora.py`, lines 64 and 141 perform the check `if len(parts) < 3:`.
3. When an input file contains extra columns (e.g. `len(parts) > 3`), `len(parts) < 3` evaluates to `False`. The code proceeds to assign `phone = parts[2]` or `word_text = parts[2]`, silently discarding all subsequent tokens on the line.
4. The error message on line 67 specifically states:
   `f"expected 3 tokens, got {len(parts)}"`,
   confirming the architectural intent was to enforce exactly 3 tokens per line.
5. Therefore, the implementation permits malformed lines with superfluous columns to pass undetected without raising `CorpusFormatError`.
6. From Observations 2, 3, 4, and 5, all other aspects of TIMIT parsing, Buckeye TextGrid processing, synthetic audio generation, duration-boundary correspondence, and CLI staging are functionally sound and mathematically exact.
7. However, because the extra-columns vulnerability represents a direct divergence from Task Requirement 1, the verdict must be `REQUEST_CHANGES` to address this defect before milestone approval.

---

## 3. Challenge Summary

**Overall risk assessment**: MEDIUM

### Challenges

#### [Medium] Challenge 1: Unchecked Superfluous Tokens in TIMIT Files
- **Assumption challenged**: That checking `len(parts) < 3` is sufficient to validate the 3-column TIMIT contract.
- **Attack scenario**: A corrupted TIMIT file or an aligned table with 4+ columns (e.g., sample start, sample end, phone label, confidence score/stress marker) is ingested by `parse_timit_phn` or `parse_timit_wrd`. Instead of rejecting the invalid format defensively, the parser silently ignores the extra columns, potentially masking schema mismatches.
- **Blast radius**: Low-to-medium; TIMIT files with non-standard column structures or malformed annotations will be parsed silently without diagnostic feedback.
- **Mitigation**: Update the condition in both `parse_timit_phn` (line 64) and `parse_timit_wrd` (line 141) from `if len(parts) < 3:` to `if len(parts) != 3:`. Add corresponding unit test assertions in `tests/test_benchmark.py`.

---

## 4. Stress Test Results

| Test Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| TIMIT .phn extra columns (`0 1600 sh extra`) | Raise `CorpusFormatError` | Returned `[PhonemeCue(...)]` silently | [FAIL] |
| TIMIT .wrd extra columns (`0 1600 she pronoun`) | Raise `CorpusFormatError` | Returned `[WordToken(...)]` silently | [FAIL] |
| TIMIT .phn missing columns (`0 1600`) | Raise `CorpusFormatError` | Raised `CorpusFormatError` | [PASS] |
| TIMIT .wrd missing columns (`1600`) | Raise `CorpusFormatError` | Raised `CorpusFormatError` | [PASS] |
| TIMIT non-integer float (`0.5 1600 sh`) | Raise `CorpusFormatError` | Raised `CorpusFormatError` | [PASS] |
| TIMIT non-integer NaN (`nan 1600 sh`) | Raise `CorpusFormatError` | Raised `CorpusFormatError` | [PASS] |
| TIMIT non-integer Inf (`inf 1600 sh`) | Raise `CorpusFormatError` | Raised `CorpusFormatError` | [PASS] |
| TIMIT negative start sample (`-100 1600 sh`) | Raise `CorpusFormatError` | Raised `CorpusFormatError` | [PASS] |
| TIMIT inverted boundaries (`2000 1000 sh`) | Raise `CorpusFormatError` | Raised `CorpusFormatError` | [PASS] |
| TIMIT non-monotonic timestamps (`0 1600\n1200 3200`) | Raise `CorpusFormatError` | Raised `CorpusFormatError` | [PASS] |
| Buckeye empty tiers (`size = 0`) | Return `[]` | Returned `[]` | [PASS] |
| Buckeye empty intervals (`intervals: size = 0`) | Return `[]` | Returned `[]` | [PASS] |
| Buckeye phones-only tier | Return `[]` | Returned `[]` | [PASS] |
| Buckeye 10 non-speech tokens filtering | Strip all non-speech tokens | All 10 filtered cleanly | [PASS] |
| Buckeye mixed non-speech phone filtering | Strip `<NOISE>` from phone tier | Kept valid phones (`t`, `eh`, `s`) | [PASS] |
| Synthetic 10 WAVs format & RMS | Valid mono PCM16 16kHz, RMS >= 1e-4 | Passed validate_wav, RMS ~0.14 | [PASS] |
| Synthetic boundary-duration match | Exact match across .wav, .phn, .wrd, .TextGrid | 100% exact match | [PASS] |
| CLI `--corpus timit` missing path | Print LDC message, exit 0 | Clean message, exit code 0 | [PASS] |
| CLI `--corpus buckeye` missing path | Print OSU message, exit 0 | Clean message, exit code 0 | [PASS] |
| CLI invalid corpus argument | Argparse error, exit code 2 | Exit code 2 with usage | [PASS] |

---

## 5. Caveats

1. Real TIMIT and Buckeye corpora require separate external licensed files (LDC93S1 and OSU archive); this evaluation relied on synthetic and unit-level stress testing.
2. Character encoding was tested with UTF-8. TIMIT files in legacy environments may occasionally use ASCII or ISO-8859-1; `read_text(encoding="utf-8", errors="replace")` handles non-UTF-8 characters gracefully by replacement.

---

## 6. Conclusion

**Verdict: REQUEST_CHANGES**

Required changes for `worker_m1_1`:
1. In `src/subtitle_workbench/corpora.py`, update `parse_timit_phn`:
   Change line 64 from `if len(parts) < 3:` to `if len(parts) != 3:`.
2. In `src/subtitle_workbench/corpora.py`, update `parse_timit_wrd`:
   Change line 141 from `if len(parts) < 3:` to `if len(parts) != 3:`.
3. In `tests/test_benchmark.py`:
   Add test cases verifying that lines with 4 or more tokens raise `CorpusFormatError` in both `test_timit_phn_parser_malformed_and_monotonicity` and `test_timit_wrd_parser_malformed_and_monotonicity`.

Once these changes are applied and verified, the corpora module will fully satisfy all defensive boundary requirements.

---

## 7. Verification Method

To independently verify the failure and proposed fix:

1. **Reproduce Extra Columns Failure:**
   ```powershell
   uv run python -c "from pathlib import Path; from subtitle_workbench.corpora import parse_timit_phn, parse_timit_wrd; p = Path('test_extra.phn'); p.write_text('0 1600 sh extra\n'); print('PHN returned:', parse_timit_phn(p)); p.unlink()"
   ```
   Observed outcome: `[PhonemeCue(phoneme='sh', start=0.0, end=0.1, confidence=1.0)]` (defect confirmed).

2. **Run Full Test Suite:**
   ```powershell
   uv run --locked pytest tests/test_benchmark.py -v
   uv run --locked pytest
   ```

3. **Verify Linter and Formatter:**
   ```powershell
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```

Invalidation Conditions:
- `parse_timit_phn` or `parse_timit_wrd` raises `CorpusFormatError` on a 4-token line without modifying `corpora.py`.
