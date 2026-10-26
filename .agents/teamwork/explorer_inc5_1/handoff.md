# Handoff Report: Increment 5 - Standardized Accessibility Exporters (Requirement R1)

## 1. Observation

### 1.1 Git Branch and History
- Direct observation from `git status`:
  - Active branch: `feature/increment-5-exporters-and-pipeline`.
  - Staging area: clean for source code. Only untracked agent metadata in `.agents/teamwork/`.
- Direct observation from `git log -n 5 --oneline`:
  - Commit `261f508`: `docs(sdlc): formalize Increment 4 verification report and audit logs`
  - Commit `3f891d7`: `feat(alignment): implement MFA batch staging adapter and CTC trellis fallback aligner`
  - Commit `efce2a8`: `docs(analogs): add whisper.cpp, NeMo Parakeet-TDT, Canary-1B, and Qwen2-Audio to ASR analogs backlog`
  - Commit `ce0075c`: `docs(architecture): document MFA corpus staging batch architecture and Windows 11 toolchain integration`
  - Commit `0948d5b`: `docs(terminology): standardize on Montreal Forced Aligner (MFA) and Forced Alignment`
- Direct observation from `git branch -a`:
  - The branch `feature/increment-5-exporters-and-pipeline` exists, is checked out, and directly incorporates Increment 4 commits.

### 1.2 Existing Exporters in `src/subtitle_workbench/export.py`
- Line 1-58 in `src/subtitle_workbench/export.py`:
  - `milliseconds(seconds: float) -> int`:
    Uses `finite_number(seconds, "timestamp")`, checks `value < 0`, and rounds using `Decimal(str(value)) * 1000` with `ROUND_HALF_UP`.
  - `timestamp(seconds: float) -> str`:
    Divides total milliseconds into hours, minutes, seconds, milliseconds: `f"{hours:02d}:{minutes:02d}:{sec:02d}.{ms:03d}"`.
  - `webvtt(cues: list[Cue]) -> str`:
    Emits classic WebVTT blocks with `cue.id`, cue timestamps, and HTML-escaped text (`html.escape(cue.text, quote=False)`).
    Rejects collapsing cues: `if milliseconds(cue.end) <= milliseconds(cue.start): raise ValueError("cue collapses after millisecond rounding")`.
  - `jsonld(cues: list[Cue], duration: float, media_name: str) -> dict`:
    Emits schema.org `VideoObject` with `Clip` parts for `Cue` objects.
- Line 1-49 in `tests/test_export.py`:
  - Contains unit tests for `timestamp` (rounding, carrying, invalid types like `-1`, `NaN`, `inf`, `bool`), `webvtt` (markup escaping, cue collapse rejection), and `jsonld` (semantic schema and offset checks).

### 1.3 Code Provenance and Models Investigation
- `src/subtitle_workbench/provenance.py`:
  - Does NOT exist currently.
  - Command: `find_by_name` and `view_file` confirmed file absence.
- Location of `code_provenance()` and `sha256()`:
  - Lines 22-57 in `src/subtitle_workbench/pipeline.py`:
    - `sha256(path: Path) -> str`: reads 64 KB blocks and returns `hashlib.sha256().hexdigest()`.
    - `code_provenance() -> dict`: hashes all sorted `*.py` files in `package` (`src/subtitle_workbench/`), queries `git rev-parse HEAD` and `git status --porcelain` for `git_revision` and `git_worktree_dirty`.
- Import Graph & Circular Dependency Hazard:
  - `src/subtitle_workbench/pipeline.py` line 18 imports:
    `from .export import jsonld, webvtt`
  - If `src/subtitle_workbench/export.py` imports `code_provenance` or `sha256` directly from `.pipeline`, Python raises `ImportError: cannot import name ... from partially initialized module ... (most likely due to a circular import)`.
- Models in `src/subtitle_workbench/models.py`:
  - `WordToken`: immutable frozen dataclass with fields `id: str`, `text: str`, `normalized: str`, `start: float`, `end: float`, `confidence: float`, `phonemes: list[PhonemeCue] = field(default_factory=list)`, `char_start: int | None = None`, `char_end: int | None = None`. Validates `0.0 <= start < end`, `0.0 <= confidence <= 1.0`, non-empty ASCII identifier, non-empty plain text without control characters, valid char span offsets.
  - `PhonemeCue`: immutable frozen dataclass with `phoneme: str`, `start: float`, `end: float`, `confidence: float`. Validates `0.0 <= start < end`, `0.0 <= confidence <= 1.0`.
  - `Cue`: frozen dataclass with `id: str`, `start: float`, `end: float`, `text: str`.
  - `finite_number(value: object, name: str) -> float`: strictly forbids `bool`, non-`Real`, `NaN`, and `inf`.

### 1.4 Test Suite and Linter Baseline
- Running `uv run --locked pytest`:
  - Result: `446 passed, 1 skipped in 4.49s` (the 1 skipped test is `tests/test_asr.py` faster-whisper live model test which is properly skipped when optional weights are absent).
- Running `uv run --locked ruff check .`:
  - Result: `All checks passed!`
- Running `uv run --locked ruff format --check .`:
  - Result: `210 files already formatted`.
- Running `scripts/smoke_wheel.py` inspection:
  - Line 59-61: Executes `main(['--reference', ..., '--target', ..., '--cues', ..., '--output', ...])`.
  - Backward compatibility of root flags in `cli.py` is mandatory for installed-wheel smoke test success.

---

## 2. Logic Chain

### 2.1 Branch and SDLC Positioning
1. Premise: Increment 5 requires building on top of Increment 4 forced alignment.
2. Observation: The branch `feature/increment-5-exporters-and-pipeline` is active and checked out. Git log shows the head commit is `261f508` (Increment 4 SDLC completion).
3. Deduction: No branching or git cherry-picking is needed. Work proceeds directly on `feature/increment-5-exporters-and-pipeline`.

### 2.2 Provenance Modularization to Break Circular Dependency
1. Premise: Requirement R1 requires `generate_manifest` in `export.py` to incorporate `code_provenance()` and output file SHA-256 digests.
2. Observation: `code_provenance()` and `sha256()` currently live in `pipeline.py`. `pipeline.py` already imports `export.py` (`from .export import jsonld, webvtt`).
3. Deduction: If `export.py` imports from `pipeline.py`, a circular module import will trigger a runtime failure.
4. Solution: Extract `sha256` and `code_provenance` into `src/subtitle_workbench/provenance.py`. Both `export.py` and `pipeline.py` will import from `provenance.py`. Re-exporting `sha256` and `code_provenance` in `pipeline.py` preserves complete backward compatibility for existing tests (such as `tests/test_integration.py`).

### 2.3 Mathematical and Contractual Specifications for Requirement R1

#### Specification A: `format_vtt_timestamp(seconds: float) -> str`
- Contract:
  - Input: `seconds: float`. Must be finite, non-`bool`, nonnegative (`>= 0.0`).
  - Validation: delegate to `milliseconds(seconds: float) -> int`.
  - Format: `HH:MM:SS.mmm`. Hours padded to 2 digits, minutes to 2 digits, seconds to 2 digits, milliseconds to 3 digits.
  - Rounding: `ROUND_HALF_UP` (e.g. `0.0005` -> `00:00:00.001`, `59.9995` -> `00:01:00.000`).
  - Backward compatibility: keep `timestamp = format_vtt_timestamp` alias.

#### Specification B: `export_karaoke_vtt(words: list[WordToken], max_line_words: int = 8, max_line_chars: int = 42, max_pause_break: float = 1.0) -> str`
- Contract:
  - Parameters:
    - `words: list[WordToken]`: sequence of aligned word tokens.
    - `max_line_words: int = 8`: maximum words permitted in a single cue block.
    - `max_line_chars: int = 42`: maximum display character count (excluding HTML markup tags) of the cue text.
    - `max_pause_break: float = 1.0`: pause duration in seconds triggering an automatic cue break.
  - Empty input:
    - If `not words`: return `"WEBVTT\n\n"`.
  - Defensive validation:
    - `words` must be `list[WordToken]`. Raise `ValueError` if elements are not `WordToken` or if `words` is not a list.
    - `max_line_words >= 1`, `max_line_chars >= 1`, `max_pause_break > 0`. Raise `ValueError` if bounds violated.
    - Monotonicity: verify `words[i + 1].start >= words[i].start`. If an inversion occurs, raise `ValueError("words must have monotonic timestamps")`.
  - Segmentation algorithm:
    - Iterate through `words`. Maintain `current_cue: list[WordToken]`.
    - For candidate word `w`:
      - If `current_cue` is empty: add `w`.
      - Else, evaluate 3 break conditions:
        1. Word count limit: `len(current_cue) >= max_line_words`.
        2. Character length limit: `len(" ".join(t.text for t in current_cue + [w])) > max_line_chars`.
        3. Pause break: `round(w.start - current_cue[-1].end, 4) >= max_pause_break - 1e-6`.
      - If any break condition is True: finalize `current_cue` into a cue block, start new `current_cue = [w]`.
      - Else: `current_cue.append(w)`.
  - Cue block formatting:
    - Index: 1-based sequential cue number (`1`, `2`, `3`, ...).
    - Timestamp line: `{cue_start_vtt} --> {cue_end_vtt}`
      where `cue_start_vtt = format_vtt_timestamp(current_cue[0].start)`
      and `cue_end_vtt = format_vtt_timestamp(current_cue[-1].end)`.
      Ensure `milliseconds(current_cue[-1].end) > milliseconds(current_cue[0].start)`.
    - Payload line:
      Word tag format: `<c.word><{format_vtt_timestamp(w.start)}>{html.escape(w.text, quote=False)}</c>`.
      Join words with single spaces: `" ".join(...)`.
    - Document structure:
      Starts with `"WEBVTT\n\n"`. Blocks separated by `\n\n`. Ends with trailing `\n`.

#### Specification C: `export_jsonld(words: list[WordToken], audio_duration: float, media_urn: str, language: str = "en") -> dict`
- Contract:
  - Input validation:
    - `audio_duration`: finite nonnegative number (`>= 0.0`).
    - `media_urn`: non-empty string.
    - `language`: non-empty string, default `"en"`.
    - `words`: `list[WordToken]`.
  - Top-level schema.org `VideoObject`:
    - `"@context": "https://schema.org"`
    - `"@type": "VideoObject"`
    - `"@id": quote(media_urn, safe=":/-_.")`
    - `"name": "Speech alignment timeline"`
    - `"inLanguage": language`
    - `"duration": f"PT{audio_duration:.3f}S"`
    - `"description": "Word-level speech alignment timeline compliant with WCAG 2.1 Media Accessibility Guidelines."`
    - `"hasPart": [...]`
  - `hasPart` items:
    - For each `WordToken` `w` in `words`:
      ```python
      {
          "@type": "Clip",
          "@id": f"{quoted_media}#word-{quote(w.id, safe='-_')}",
          "name": w.text,
          "startOffset": round(w.start, 6),
          "endOffset": round(w.end, 6),
          "inLanguage": language,
      }
      ```
  - Empty `words`: returns valid `VideoObject` with `"hasPart": []`.
  - Backward compatibility: preserve `jsonld(cues: list[Cue], duration: float, media_name: str) -> dict`.

#### Specification D: `export_raw_alignment(words: list[WordToken], audio_path: Path | str, alignment_method: str, metrics: dict | None = None) -> dict`
- Contract:
  - Input validation:
    - `words`: `list[WordToken]`.
    - `audio_path`: `Path | str`.
    - `alignment_method`: non-empty string.
    - `metrics`: optional dictionary of additional metrics.
  - Calculation of summary metrics:
    - `total_words = len(words)`
    - `all_phonemes = [p for w in words for p in w.phonemes]`
    - `total_phonemes = len(all_phonemes)`
    - `mean_word_confidence = sum(w.confidence for w in words) / total_words` if `total_words > 0` else `0.0`
    - `mean_phoneme_confidence = sum(p.confidence for p in all_phonemes) / total_phonemes` if `total_phonemes > 0` else `0.0`
    - `speech_duration_seconds = sum(w.end - w.start for w in words)`
    - `pause_duration_seconds`:
      If `total_words > 1`: sum of positive gaps `sum(max(0.0, words[i+1].start - words[i].end) for i in range(total_words - 1))`
      If `total_words <= 1`: `0.0`
    - `speech_to_pause_ratio = speech_duration_seconds / pause_duration_seconds` if `pause_duration_seconds > 0.0` else `0.0`
  - Output dictionary:
    ```python
    {
        "schema_version": 1,
        "audio_file": Path(audio_path).name,
        "audio_path": str(audio_path),
        "alignment_method": alignment_method,
        "summary": {
            "total_words": total_words,
            "total_phonemes": total_phonemes,
            "mean_word_confidence": round(mean_word_confidence, 4),
            "mean_phoneme_confidence": round(mean_phoneme_confidence, 4),
            "speech_duration_seconds": round(speech_duration_seconds, 4),
            "pause_duration_seconds": round(pause_duration_seconds, 4),
            "speech_to_pause_ratio": round(speech_to_pause_ratio, 4),
            **(metrics or {}),
        },
        "words": [
            {
                "id": w.id,
                "text": w.text,
                "normalized": w.normalized,
                "start": round(w.start, 4),
                "end": round(w.end, 4),
                "confidence": round(w.confidence, 4),
                "char_start": w.char_start,
                "char_end": w.char_end,
                "phonemes": [
                    {
                        "phoneme": p.phoneme,
                        "start": round(p.start, 4),
                        "end": round(p.end, 4),
                        "confidence": round(p.confidence, 4),
                    }
                    for p in w.phonemes
                ],
            }
            for w in words
        ],
    }
    ```

#### Specification E: `generate_manifest(input_audio_path: Path, output_dir: Path, words: list[WordToken], metrics: dict, config: dict | None = None) -> dict`
- Contract:
  - Input:
    - `input_audio_path: Path`: path to input WAV file.
    - `output_dir: Path`: directory where generated artifacts reside.
    - `words: list[WordToken]`: aligned words.
    - `metrics: dict`: execution metrics.
    - `config: dict | None`: pipeline configuration dictionary.
  - Prerequisite files in `output_dir`:
    - `subtitles.vtt`
    - `timeline.jsonld`
    - `alignment_raw.json`
    If any file is missing, raises `FileNotFoundError`.
  - Cryptographic hashing:
    - Input audio: `sha256(input_audio_path)`.
    - Generated outputs: `sha256(output_dir / "subtitles.vtt")`, `sha256(output_dir / "timeline.jsonld")`, `sha256(output_dir / "alignment_raw.json")`.
  - Provenance:
    - Calls `code_provenance()` to retrieve source files fingerprint and git commit / worktree state.
  - Manifest dictionary structure:
    ```python
    manifest = {
        "schema_version": 1,
        "tool": {"name": "local-subtitle-workbench", "version": __version__},
        "code": code_provenance(),
        "inputs": {
            "audio": {
                "filename": input_audio_path.name,
                "sha256": sha256(input_audio_path),
            }
        },
        "config": config or {},
        "outputs": {
            "subtitles.vtt": {"sha256": sha256(output_dir / "subtitles.vtt")},
            "timeline.jsonld": {"sha256": sha256(output_dir / "timeline.jsonld")},
            "alignment_raw.json": {"sha256": sha256(output_dir / "alignment_raw.json")},
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "metrics": metrics,
        "limitations": [
            "Phoneme-level alignments depend on acoustic model fidelity and pronunciation dictionary.",
            "Display WebVTT timings are millisecond-rounded and clamped for reading ergonomics.",
            "Acoustic confidence is a model score and does not guarantee human-level accuracy.",
        ],
    }
    ```
  - Serialization: writes `output_dir / "manifest.json"` with UTF-8 encoding and 2-space indentation. Returns `manifest`.

---

## 3. Caveats

1. **Strict Read-Only Investigation**:
   No source code or test files were created or modified during this investigation. All findings and code snippets are proposals for the implementer agent.
2. **Backward Compatibility Dependencies**:
   Existing tests (`tests/test_export.py`, `tests/test_integration.py`, `scripts/smoke_wheel.py`) invoke `timestamp()`, `webvtt()`, and `jsonld(cues, ...)`. The new functions must coexist with existing functions or alias them without altering legacy signatures.
3. **External Dependencies**:
   `faster-whisper` and `torch` optional dependencies are omitted from the default offline CI test run. All new unit tests in `tests/test_export.py` must execute in pure Python/NumPy with zero network access and sub-second execution speed.

---

## 4. Conclusion

Requirement R1 specifies 5 standardized accessibility exporters in `src/subtitle_workbench/export.py` with cryptographic audit logging.

Key structural recommendations:
1. **Module Separation**: Extract `sha256(path: Path) -> str` and `code_provenance() -> dict` from `pipeline.py` into a new `src/subtitle_workbench/provenance.py` module. Re-export them from `pipeline.py` for backward compatibility. This prevents circular import errors between `export.py` and `pipeline.py`.
2. **Defensive Validation**:
   - `format_vtt_timestamp` enforces finite nonnegative values, rejecting `NaN`, `inf`, `-inf`, booleans, and negative numbers.
   - `export_karaoke_vtt` verifies `WordToken` types, enforces monotonicity, handles empty input gracefully (`WEBVTT\n\n`), segments lines via `max_line_words`, `max_line_chars`, and `max_pause_break`, and formats `<c.word><timestamp>text</c>`.
   - `export_jsonld` outputs valid schema.org `VideoObject` and `Clip` items conforming to WCAG 2.1 and ISO 8601 duration `PT...S`.
   - `export_raw_alignment` produces hierarchical word/phoneme JSON with exact timestamps and summary metrics.
   - `generate_manifest` hashes all inputs and outputs using SHA-256 and writes `manifest.json`.
3. **Public API Exports**: Export the new functions in `src/subtitle_workbench/__init__.py` under `__all__`:
   - `format_vtt_timestamp`
   - `export_karaoke_vtt`
   - `export_jsonld`
   - `export_raw_alignment`
   - `generate_manifest`
   - `code_provenance`

---

## 5. Verification Method

To independently verify all findings and confirm the system is ready for Increment 5 implementation:

1. **Verify Git Branch and Clean Working Tree**:
   ```pwsh
   git status
   git branch --show-current
   git log -n 3 --oneline
   ```
   *Expected output*: Branch is `feature/increment-5-exporters-and-pipeline`, top commit is `261f508`.

2. **Verify Existing Test Baseline**:
   ```pwsh
   uv run --locked pytest
   ```
   *Expected output*: 446 passed, 1 skipped in < 5.0s.

3. **Verify Linting & Formatting**:
   ```pwsh
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```
   *Expected output*: 0 errors, 210 files formatted.

4. **Verify Wheel Packaging**:
   ```pwsh
   uv run --locked python -m build --wheel --no-isolation
   ```
   *Expected output*: Clean wheel build in `dist/`.

5. **Future Verification of Requirement R1 Implementation**:
   Once implemented by the implementer agent, verify new unit tests in `tests/test_export.py`:
   ```pwsh
   uv run --locked pytest tests/test_export.py -v
   ```
   *Invalidation conditions*: Any circular import between `export.py` and `pipeline.py`, any failure to escape HTML in karaoke tags, non-monotonic timestamps passing silently, or missing SHA-256 hashes in `manifest.json`.
