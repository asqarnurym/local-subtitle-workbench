# Handoff Report: Reference Corpora Loader and Parser Investigation (Increment 6 R1)
**Agent:** explorer_inc6_1  
**Date:** 2026-10-26  
**Parent Orchestrator:** d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_inc6_1`  
**Handoff Type:** Hard (Task complete)  

---

## 1. Observation

1. **Git Branch & Repository Status:**
   - Command: `git status`
     - Output: `On branch feature/increment-5-exporters-and-pipeline`.
     - Changes not staged: `.agents/teamwork/BRIEFING.md`, `.agents/teamwork/ORIGINAL_REQUEST.md`.
     - Untracked files: `.agents/teamwork/explorer_inc6_1/`, `explorer_inc6_2/`, `explorer_inc6_3/`, `orchestrator_3/`.
   - Command: `git branch --list`
     - Output listed: `feature/increment-1-speech-models-and-norm`, `feature/increment-2-asr-and-vad`, `feature/increment-3-macro-dtw-chunking`, `feature/increment-4-forced-alignment`, `* feature/increment-5-exporters-and-pipeline`, `main`.
     - Branch `feature/increment-6-speech-benchmark` does NOT exist yet.
   - Command: `git log -n 1 --oneline`
     - Head commit: `2f38fa1 docs(methodology): ground metrics in Q1 literature, purge prototype archive, and document pipeline FMEA`.

2. **Existing Speech Data Models in `src/subtitle_workbench/models.py`:**
   - Lines 138-158:
     - `PhonemeCue`: `phoneme: str`, `start: float`, `end: float`, `confidence: float`.
     - Invariants: `phoneme` validated via `validate_text(..., allow_newlines=False)`; `start` and `end` validated via `finite_number`; requires `start >= 0.0` and `start < end` strictly; `confidence` requires `0.0 <= confidence <= 1.0`.
   - Lines 161-207:
     - `WordToken`: `id: str`, `text: str`, `normalized: str`, `start: float`, `end: float`, `confidence: float`, `phonemes: list[PhonemeCue] = field(default_factory=list)`, `char_start: int | None = None`, `char_end: int | None = None`.
     - Invariants: `id` validated via `validate_identifier` (`[a-zA-Z0-9_-]`, length <= 128); `text` and `normalized` non-empty strings without control characters; `0.0 <= start < end`; `confidence` in `[0.0, 1.0]`; `phonemes` must be `list[PhonemeCue]`; `char_start`/`char_end` must both be None or nonnegative integers with `char_end >= char_start`.

3. **Existing TextGrid Parser in `src/subtitle_workbench/mfa_wrapper.py`:**
   - Lines 24, 75-212:
     - `SILENCE_TOKENS = {"", "<sil>", "sil", "sp"}`.
     - `_parse_raw_intervals(content: str)` parses Praat long format and short format. Discovers tiers where `"word"` or `"phone"` is in tier name (case-insensitive).
   - Lines 215-319:
     - `parse_textgrid(textgrid_content: str, word_id_prefix: str | None = None) -> list[WordToken]`.
     - Filters silence intervals and durations < 0.001s.
     - Associates phonemes with words based on midpoint containment or >=50% overlap.
     - Enforces micro-phoneme minimum duration (0.001s) and clamps to word boundaries.
     - Enforces monotonicity between words (nudging overlaps <= 0.05s).

4. **Existing Test Suite Baseline:**
   - Command: `uv run --locked pytest -q`
     - Output: `637 passed, 1 skipped in 11.77s`.
   - Command: `uv run --locked ruff check .`
     - Output: `All checks passed!`.
   - Command: `uv run --locked ruff format --check .`
     - Output: `305 files already formatted`.

5. **Audio Validation Constraints in `src/subtitle_workbench/audio.py`:**
   - Lines 24-57: `validate_wav` requires uncompressed mono PCM16 at 16000 Hz, frame count > 0, chunked read integrity.
   - Lines 59-73: `load_wav` requires signal RMS >= `1e-4` (`np.sqrt(np.mean(samples * samples)) >= 1e-4`).

---

## 2. Logic Chain

1. **Branch Checkout Requirement:**
   - From Observation 1, the repository is on `feature/increment-5-exporters-and-pipeline` and `feature/increment-6-speech-benchmark` does not exist.
   - Therefore, the orchestrator or implementing agent must execute:
     `git checkout -b feature/increment-6-speech-benchmark`.

2. **TIMIT Parser Implementation:**
   - From Observation 2, `PhonemeCue` requires `phoneme: str`, `0.0 <= start < end`, and `0.0 <= confidence <= 1.0`.
   - TIMIT `.phn` files list `<sample_start> <sample_end> <phone>`. Dividing by 16000.0 yields seconds: $t = s / 16000.0$.
   - Filtering silence tokens `'h#'`, `'pau'`, `'epi'` directly aligns with the requirement and prevents invalid non-speech tokens in phonetic evaluation.
   - TIMIT `.wrd` files list `<sample_start> <sample_end> <word>`.
   - Mapping each entry to `WordToken` requires valid ASCII IDs (e.g. `word_0000`), `start = s_start / 16000.0`, `end = s_end / 16000.0`, and `confidence = 1.0`.
   - Midpoint containment association (`word.start <= phone_mid <= word.end`) can link `.phn` phonemes into `.wrd` `WordToken.phonemes`.

3. **Buckeye Corpus Parser Implementation:**
   - From Observation 3, `mfa_wrapper.parse_textgrid` already extracts `"word"` and `"phone"` tiers from Praat TextGrids, associates phonemes, and filters standard silence (`SILENCE_TOKENS`).
   - Therefore, `parse_buckeye_textgrid` can reuse `mfa_wrapper.parse_textgrid`, adding handling for file paths and Buckeye-specific non-speech artifact tokens (`{B_TRANS}`, `{E_TRANS}`, `<IVER>`, `<LAUGH>`, `<VOCNOISE>`, `<NOISE>`, `SIL`, `<SIL>`, `UNKNOWN`, `<EXCLUDE>`).

4. **Synthetic Benchmark Dataset Staging (`stage_synthetic_benchmark`):**
   - From Observation 5, synthetic audio must have RMS >= `1e-4` to pass `load_wav`.
   - By generating 10 synthetic utterances with modulated sine wave audio (PCM16 16kHz mono, amplitude 0.2, RMS ~0.10) and exact mathematical ground-truth boundaries (multiples of 25ms / 400 samples), both sample indices and decimal seconds are exact integers and rational numbers with zero roundoff error.
   - Generating paired `.phn`, `.wrd`, and `.TextGrid` files completely offline ensures 100% test reproducibility with zero network access and sub-second generation time.

5. **Module Placement:**
   - To make the loaders cleanly importable across both the package, test suites (`tests/test_benchmark.py`), and CLI scripts (`scripts/speech_benchmark.py`, `scripts/download_reference_corpora.py`), implementing core functions in `src/subtitle_workbench/corpora.py` and wrapping them in `scripts/download_reference_corpora.py` ensures clean imports without `sys.path` tampering.

---

## 3. Caveats

1. **LDC TIMIT Licensing:** Real TIMIT audio files are proprietary LDC assets and cannot be committed to Git. The benchmark runner must rely on local paths or offline synthetic data (`--offline-synthetic`).
2. **Buckeye Praat Quirks:** Some real Buckeye TextGrids may use non-standard tier names or empty intervals. `mfa_wrapper.parse_textgrid`'s case-insensitive tier discovery and interval validation safeguards against this.
3. **Floating Point Tolerances in Tests:** While synthetic boundaries use rational multiples of 16 kHz sample rates, comparisons with predictions should always use tolerances (e.g. `math.isclose` or tolerance collards like `tolerance_ms=20.0`).

---

## 4. Conclusion

Requirement R1 is fully analyzed and architecturally specified:
- Branch command identified: `git checkout -b feature/increment-6-speech-benchmark`.
- Existing models `PhonemeCue` and `WordToken` are directly compatible and ready for parser outputs.
- `mfa_wrapper.parse_textgrid` provides a tested foundation for Buckeye TextGrids.
- TIMIT `.phn` and `.wrd` formats require straightforward whitespace-delimited parsing with sample rate $16000$ and silence filtering (`h#`, `pau`, `epi`).
- `stage_synthetic_benchmark` can generate 10 offline synthetic utterances with exact ground-truth boundaries and valid PCM16 audio in < 0.2 seconds.
- Implementation should reside in `src/subtitle_workbench/corpora.py` with CLI interface in `scripts/download_reference_corpora.py`.

---

## 5. Verification Method

To verify these findings independently:
1. Check git branch status:
   ```powershell
   git status
   git branch --list
   ```
2. Inspect models and TextGrid parser:
   ```powershell
   uv run python -c "from subtitle_workbench.models import PhonemeCue, WordToken; from subtitle_workbench.mfa_wrapper import parse_textgrid; print('[OK] Imports successful')"
   ```
3. Run baseline test suite:
   ```powershell
   uv run --locked pytest -q
   ```
4. Verify linter and formatter:
   ```powershell
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
5. Review the comprehensive analysis report at:
   `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\explorer_inc6_1\analysis.md`

