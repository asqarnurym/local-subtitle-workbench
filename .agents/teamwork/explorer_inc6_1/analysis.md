# Technical Investigation & Architecture Analysis: Increment 6 Requirement R1
**Reference Corpora Loader and Parser (`scripts/download_reference_corpora.py`)**
**Author:** explorer_inc6_1  
**Date:** 2026-10-26  
**Parent Orchestrator:** d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  

---

## 1. Executive Summary

This report delivers a comprehensive technical survey and architectural design for Requirement R1 of Increment 6 («Reference Corpora Loader and Parser»). The investigation analyzes the existing git branch state, core data models (`PhonemeCue`, `WordToken`), TextGrid parser mechanisms in `mfa_wrapper.py`, the official file format specifications for TIMIT (`.phn`, `.wrd`) and Buckeye Praat TextGrids, and formulates an offline, mathematically exact synthetic benchmark generator (`stage_synthetic_benchmark`).

All findings are backed by verbatim file line numbers and tool verification.

---

## 2. Git Branch Status & Workspace State

### 2.1 Branch Identification
- **Current active branch:** `feature/increment-5-exporters-and-pipeline`
- **Existing local branches:**
  - `feature/increment-1-speech-models-and-norm`
  - `feature/increment-2-asr-and-vad`
  - `feature/increment-3-macro-dtw-chunking`
  - `feature/increment-4-forced-alignment`
  - `feature/increment-5-exporters-and-pipeline`
  - `main`
- **Branch `feature/increment-6-speech-benchmark`:** NOT yet created.

### 2.2 Required Branch Transition Command
To create and switch to the target branch from `feature/increment-5-exporters-and-pipeline`:
```powershell
git checkout -b feature/increment-6-speech-benchmark
```

### 2.3 Working Tree Status
- Head commit on `feature/increment-5-exporters-and-pipeline`:
  `2f38fa1 docs(methodology): ground metrics in Q1 literature, purge prototype archive, and document pipeline FMEA`
- Status: Source files under `src/`, `tests/`, and `scripts/` are clean. Untracked metadata files exist only within `.agents/teamwork/`.
- Baseline test suite verification: 637 passed, 1 skipped in 11.77s (`uv run --locked pytest -q`). Zero linter warnings (`uv run --locked ruff check .`), 305 files formatted.

---

## 3. Existing Data Models and Boundary Validation Contracts

### 3.1 Model Location
All primary speech contracts reside in `src/subtitle_workbench/models.py`.

### 3.2 `PhonemeCue` Contract Analysis
- **Definition:** `src/subtitle_workbench/models.py:138-158`
  ```python
  @dataclass(frozen=True)
  class PhonemeCue:
      phoneme: str
      start: float
      end: float
      confidence: float
  ```
- **Validation Constraints:**
  1. `phoneme`: Validated via `validate_text(phoneme, "phoneme", allow_newlines=False)` (`models.py:33-51`). Must be non-empty, string type (not bool), trimmed length > 0, length <= 4000, no surrogate characters (`0xD800` to `0xDFFF`), and no control characters (`ord(char) < 32 or ord(char) == 127 or 128 <= ord(char) <= 159`).
  2. `start`: Must be a finite number (`finite_number`, `models.py:7-16`), not bool, not NaN, not Inf. Enforces `start >= 0.0`.
  3. `end`: Must be a finite number. Enforces `start < end` strictly (`models.py:150-151`). Zero-duration or negative-duration phonemes are strictly forbidden and raise `ValueError`.
  4. `confidence`: Must be a finite number in the range `[0.0, 1.0]` (`models.py:152-154`).

### 3.3 `WordToken` Contract Analysis
- **Definition:** `src/subtitle_workbench/models.py:161-207`
  ```python
  @dataclass(frozen=True)
  class WordToken:
      id: str
      text: str
      normalized: str
      start: float
      end: float
      confidence: float
      phonemes: list[PhonemeCue] = field(default_factory=list)
      char_start: int | None = None
      char_end: int | None = None
  ```
- **Validation Constraints:**
  1. `id`: Validated via `validate_identifier(id, "id")` (`models.py:19-30`). Must be a non-empty ASCII string <= 128 characters consisting solely of alphanumeric characters, underscores, or hyphens (`[a-zA-Z0-9_-]`).
  2. `text` and `normalized`: Validated via `validate_text(..., allow_newlines=False)`. Must be non-empty without control characters.
  3. `start` and `end`: Finite numbers satisfying `0.0 <= start < end`.
  4. `confidence`: Finite number in `[0.0, 1.0]`.
  5. `phonemes`: Must be a `list` where every item is an instance of `PhonemeCue` (`models.py:185-188`).
  6. `char_start` and `char_end`: Must both be `None` or both be nonnegative integers satisfying `char_end >= char_start` (`models.py:189-203`).

### 3.4 Key Invariants for Reference Corpora Loaders
- For reference ground-truth data (TIMIT, Buckeye, Synthetic), ground truth confidence is `1.0`.
- All timestamps must satisfy `0.0 <= start < end`.
- Generated word identifiers must adhere to ASCII identifier syntax (e.g. `f"w_{idx:04d}"` or `f"{prefix}_{idx:04d}"`).
- Words must contain only speech tokens; silence intervals must never be converted into `WordToken` instances.

---

## 4. Existing TextGrid Parsing Logic in `mfa_wrapper.py`

### 4.1 Parser Architecture
`src/subtitle_workbench/mfa_wrapper.py` implements a pure-Python parser for Praat TextGrid files without external C-extensions or GUI dependencies:
- **Interval extraction:** `_parse_raw_intervals(content: str)` (`mfa_wrapper.py:75-212`):
  - Detects format: Praat Long Format (`item [1]:`, `xmin =`, `intervals:`) vs Praat Short Format (`<exists>`, token stream).
  - Identifies tiers:
    - Tier name containing `"word"` (case-insensitive) -> words tier.
    - Tier name containing `"phone"` (case-insensitive) -> phones tier.
  - Extracts tuples: `(xmin: float, xmax: float, text: str)`.
  - Discards intervals with duration `< 0.001` (1 ms) or `xmax <= xmin`.
- **Public API:** `parse_textgrid(textgrid_content: str, word_id_prefix: str | None = None) -> list[WordToken]` (`mfa_wrapper.py:215-319`):
  - Silence filtering: Excludes intervals whose stripped lower-case text is in `SILENCE_TOKENS = {"", "<sil>", "sil", "sp"}` (`mfa_wrapper.py:24, 229, 234`).
  - Containment association: Associates phones with words if phone midpoint `(p_s + p_e) / 2.0` lies within `[w_s, w_e]` or if overlap exceeds 50% of phone duration (`mfa_wrapper.py:248-254`).
  - Clamping: Clamps phone boundaries to word boundaries and enforces minimum 1 ms phone duration.
  - Monotonicity nudging: Resolves boundary overlaps `<= 0.05s` between consecutive words by adjusting preceding word end timestamp (`mfa_wrapper.py:286-318`).

### 4.2 Reusability for Buckeye Corpus
The existing `mfa_wrapper.parse_textgrid` function already handles:
1. Long format and short format Praat TextGrids.
2. Word and phone tier discovery via case-insensitive substring matching.
3. Silence token filtering (`""`, `"<sil>"`, `"sil"`, `"sp"`).
4. Phone-to-word containment association.
5. Boundary clamping and monotonicity enforcement.

---

## 5. Reference Corpora Formats & Specifications

### 5.1 TIMIT Acoustic-Phonetic Corpus
- **Reference Standard:** DARPA TIMIT (NIST Speech Disc 1-1.1, LDC93S1).
- **Sampling Rate:** Strictly 16,000 Hz (16 kHz mono PCM16).
- **Time Conversion Equation:**
  $$t_{\text{seconds}} = \frac{\text{sample\_index}}{16000.0}$$
  Note: Because $16000 = 2^7 \times 5^3$, sample indices divide cleanly in IEEE-754 binary floating-point representation.
- **Phonetic Transcription File (`.phn`):**
  - Syntax: `<sample_start> <sample_end> <phoneme>` (whitespace separated, one entry per line).
  - Example:
    ```
    0 3050 h#
    3050 4550 sh
    4550 5723 iy
    5723 9200 hv
    9200 9940 ae
    9940 10600 d
    48250 52320 h#
    ```
  - Silence Markers to Filter Out:
    - `h#`: Beginning and end-of-sentence silence intervals.
    - `pau`: Pause / inter-phrase silence.
    - `epi`: Epenthetic acoustic silence.
    - Filter rule: Skip line if `phoneme.lower().strip() in {"h#", "pau", "epi", ""}`.
  - Speech Phoneme Conversion:
    Each non-silence phone entry maps to:
    `PhonemeCue(phoneme=phoneme, start=sample_start / 16000.0, end=sample_end / 16000.0, confidence=1.0)`.
- **Word Alignment File (`.wrd`):**
  - Syntax: `<sample_start> <sample_end> <word>` (whitespace separated, one entry per line).
  - Example:
    ```
    3050 5723 she
    5723 10600 had
    10600 13160 your
    13160 18880 dark
    18880 23640 suit
    ```
  - Word Conversion:
    Each word entry maps to:
    `WordToken(id=f"{word_id_prefix}_{idx:04d}", text=word, normalized=word.lower(), start=sample_start / 16000.0, end=sample_end / 16000.0, confidence=1.0, phonemes=associated_phones)`.
  - Containment association: Phoneme cues parsed from the corresponding `.phn` file can be associated to their parent words using temporal midpoint containment: `w_start <= (p_start + p_end) / 2.0 <= w_end`.

### 5.2 Buckeye Speech Corpus
- **Reference Standard:** Ohio State University Buckeye Corpus (Pitt et al., 2005).
- **Format:** Praat TextGrid files containing:
  - IntervalTier named `"words"` (or `"word"`).
  - IntervalTier named `"phones"` (or `"phone"`).
- **Buckeye Non-Speech & Artifact Markers:**
  Buckeye annotations contain conversational and acoustic noise markers:
  - `{B_TRANS}`, `{E_TRANS}`: Transcription window boundaries.
  - `<IVER>`, `IVER`: Interviewer speech.
  - `<LAUGH>`, `LAUGH`: Laughter episodes.
  - `<VOCNOISE>`, `VOCNOISE`: Vocal non-speech sounds (coughs, throat clears).
  - `<NOISE>`, `NOISE`: Ambient background noise.
  - `SIL`, `<SIL>`: Acoustic silence intervals.
  - `<EXCLUDE>`, `EXCLUDE`, `UNKNOWN`: Unintelligible segments.
- **Parser Integration:**
  `parse_buckeye_textgrid(path_or_content: Path | str, word_id_prefix: str = "word") -> list[WordToken]`:
  1. Reads file if path is supplied, else accepts raw string.
  2. Pre-filters or treats non-speech Buckeye markers as silence.
  3. Ingests via `mfa_wrapper.parse_textgrid`.
  4. Returns validated list of `WordToken` instances with nested `PhonemeCue` objects.

---

## 6. Architecture & Design of `stage_synthetic_benchmark`

### 6.1 Purpose & Constraints
- Provides an offline, deterministic synthetic reference dataset for unit testing, CI pipelines, and benchmark validation without external downloads or network access.
- Generates 10 distinct synthetic utterances with exact mathematical ground-truth word and phoneme boundaries.
- Emits uncompressed PCM16 16 kHz mono WAV files that satisfy both `audio.validate_wav` and `audio.load_wav` (audible non-silent signal with RMS > $10^{-4}$).
- Emits paired TIMIT (`.phn`, `.wrd`) and Buckeye Praat (`.TextGrid`) annotation files.

### 6.2 Utterance Corpus Definition (10 Utterances)
Each utterance is structured with an initial silence (`h#`, 0.20s), spoken words with explicit phoneme breakdown, inter-word pauses (`pau`, 0.05s-0.10s), and trailing silence (`h#`, 0.20s).

| ID | Transcript | Word Count | Phone Count | Total Duration (s) | Total Samples (at 16 kHz) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `synth_01` | she had your dark suit | 5 | 16 | 2.50 | 40,000 |
| `synth_02` | water was wet and deep | 5 | 15 | 2.40 | 38,400 |
| `synth_03` | clear speech improves subtitle accuracy | 5 | 24 | 3.20 | 51,200 |
| `synth_04` | acoustic models require precise boundaries | 5 | 25 | 3.50 | 56,000 |
| `synth_05` | local alignment workbench benchmark suite | 5 | 23 | 3.30 | 52,800 |
| `synth_06` | ten synthetic audio signals generated | 5 | 21 | 3.00 | 48,000 |
| `synth_07` | the quick brown fox jumps | 5 | 17 | 2.60 | 41,600 |
| `synth_08` | high quality forced alignment pipeline | 5 | 22 | 3.10 | 49,600 |
| `synth_09` | statistical significance requires paired tests | 5 | 26 | 3.60 | 57,600 |
| `synth_10` | empirical evaluation confirms timing accuracy | 5 | 25 | 3.40 | 54,400 |

### 6.3 Mathematical Exactness of Boundaries
To eliminate all floating-point roundoff issues between sample counts and seconds:
- All temporal intervals are chosen as integer multiples of 25 ms ($0.025 \text{ s} = 400 \text{ samples}$), 50 ms ($0.050 \text{ s} = 800 \text{ samples}$), or 100 ms ($0.100 \text{ s} = 1600 \text{ samples}$).
- Every sample boundary is an exact integer:
  $$\text{sample} = \text{round}(t \times 16000)$$
  $$\frac{\text{sample}}{16000.0} \equiv t \quad (\text{zero residual error})$$

### 6.4 Synthetic Signal Generation
To ensure compatibility with `load_wav` (which raises `ValueError` if signal RMS < $10^{-4}$):
- Generate active audio frames using a low-amplitude sine tone with smooth Hanning windowing:
  $$s(t) = A \cdot \sin(2\pi f t) \cdot w(t)$$
  where $A = 0.2$ (approx $-14 \text{ dBFS}$), $f \in [300, 1000] \text{ Hz}$.
- Silence intervals (`h#`, `pau`) are rendered as true acoustic silence ($s(t) = 0$).
- Total signal RMS across the utterance is $\approx 0.08$ to $0.12$, safely above the $10^{-4}$ noise threshold and well below clipping.

### 6.5 Output Directory Structure
`stage_synthetic_benchmark(target_dir: Path) -> Path` generates:
```
<target_dir>/
  manifest.json               # Cryptographic hashes, metadata, transcript directory
  synth_01/
    audio.wav                 # PCM16 16kHz mono WAV
    audio.phn                 # TIMIT .phn format
    audio.wrd                 # TIMIT .wrd format
    audio.TextGrid            # Buckeye/Praat TextGrid format
    transcript.txt            # Plain text reference transcript
  synth_02/
    ...
  synth_10/
    ...
```
Or flat file structure with canonical naming:
```
<target_dir>/
  synth_01.wav
  synth_01.phn
  synth_01.wrd
  synth_01.TextGrid
  synth_01.txt
  ...
  manifest.json
```
Both flat and subfolder naming can be supported transparently by globbing `*.phn`, `*.wrd`, and `*.TextGrid`.

---

## 7. Architectural Placement & Export Strategy

### 7.1 Separation of Concerns: Core Library vs CLI Script
- **Package Module (`src/subtitle_workbench/corpora.py`):**
  Houses pure business logic:
  - `parse_timit_phn(path_or_content: Path | str, sample_rate: int = 16000) -> list[PhonemeCue]`
  - `parse_timit_wrd(path_or_content: Path | str, phonemes: list[PhonemeCue] | None = None, sample_rate: int = 16000, word_id_prefix: str = "word") -> list[WordToken]`
  - `parse_buckeye_textgrid(path_or_content: Path | str, word_id_prefix: str = "word") -> list[WordToken]`
  - `stage_synthetic_benchmark(target_dir: Path) -> Path`
  - `associate_phonemes_with_words(words: list[WordToken], phonemes: list[PhonemeCue]) -> list[WordToken]`
  - Exported in `src/subtitle_workbench/__init__.py` for seamless import in `tests/test_benchmark.py` and `scripts/speech_benchmark.py`.
- **CLI Script (`scripts/download_reference_corpora.py`):**
  Provides command-line interface for human operators and automated benchmark staging:
  - Supports `--corpus {timit,buckeye,synthetic,all}`.
  - Supports `--target-dir PATH` (defaults to `data/corpora/`).
  - Implements `--offline-synthetic` to trigger `stage_synthetic_benchmark`.
  - Re-exports the loader functions so scripts and tests can import from either `subtitle_workbench.corpora` or `scripts.download_reference_corpora`.

---

## 8. Summary Table of Specifications

| Parameter | TIMIT (`.phn`, `.wrd`) | Buckeye (`.TextGrid`) | Synthetic Benchmark |
| :--- | :--- | :--- | :--- |
| **Audio Format** | PCM16 16 kHz Mono WAV | PCM16 16 kHz Mono WAV | PCM16 16 kHz Mono WAV |
| **Time Base** | Sample count ($t = s / 16000$) | Seconds (floating point) | Exact samples & seconds |
| **Word Representation** | `.wrd` (sample start, end, word) | Praat `"words"` tier | Both `.wrd` and TextGrid |
| **Phone Representation** | `.phn` (sample start, end, phone) | Praat `"phones"` tier | Both `.phn` and TextGrid |
| **Silence Handling** | Filter `h#`, `pau`, `epi`, `""` | Filter `sil`, `sp`, `<sil>`, non-speech | Filter `h#`, `pau` |
| **Ground Truth Confidence** | `1.0` | `1.0` | `1.0` |
| **Network Access Needed** | No (local file parser) | No (local file parser) | Zero (strictly offline generator) |

