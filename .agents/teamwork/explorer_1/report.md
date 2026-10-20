# Technical Analysis Report: Speech Data Models & Validation Contracts (Increment 3 / R1)

**Working Directory:** `C:\Users\nurym\Desktop\local-subtitle-workbench`  
**Investigator:** `explorer_1`  
**Date:** 2026-10-20  
**Status:** Completed  

---

## 1. Executive Summary

Increment 3 introduces the **Bounded Chunker** ($L \le 30.0\text{ s}$), **Contextual Overlap Padding** ($0.5\text{ s}$), and the **Global Monotonic Alignment Reconciler** to prevent cumulative timestamp drift during long educational recordings (10–60 minutes) while strictly maintaining $O(N)$ linear memory complexity.

Requirement **R1** lays the foundational contracts in `src/subtitle_workbench/models.py`:
1. `AudioChunk`: An immutable data contract representing a bounded temporal window with symmetric overlap padding and internal speech tokens.
2. `ChunkConfig`: An immutable configuration contract setting chunk duration limits, overlap padding, and VAD silence pause thresholds.
3. Exporting these contracts in `src/subtitle_workbench/__init__.py`.

This investigation examines the existing data modeling and validation patterns in `src/subtitle_workbench/models.py`, `src/subtitle_workbench/__init__.py`, and `pyproject.toml`. It defines the exact field signatures, defensive boundary checks, relational invariants, immutability mechanisms, and test matrices required for a zero-defect, regression-free implementation.

---

## 2. Analysis of Existing Data Models in `src/subtitle_workbench/models.py`

### 2.1 Architecture and Dependencies
- **Purity**: `src/subtitle_workbench/models.py` depends solely on Python's standard library (`dataclasses.dataclass`, `dataclasses.field`, `numbers.Real`). It imports zero external packages (not even NumPy), guaranteeing zero startup overhead, offline safety, and isolation from heavy dependencies.
- **Python Compatibility**: Targets Python 3.11/3.12 (`requires-python = ">=3.11,<3.13"` in `pyproject.toml`). It uses standard PEP 585 generics (`list[T]`) and PEP 604 union types (`int | None`).

### 2.2 Existing Validation Helpers

`models.py` establishes three primary validation helpers:

#### 1. `finite_number(value: object, name: str) -> float` (lines 7–16)
```python
def finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not (-float("inf") < number < float("inf")):
        raise ValueError(f"{name} must be a finite number")
    return number
```
- **Type Guard**: In Python, `bool` is a subclass of `int` (and thus `Real`). Therefore, `isinstance(value, bool)` is explicitly checked and rejected before checking `isinstance(value, Real)`.
- **Conversion & Overflow**: Safely casts `value` to `float`, catching `OverflowError`, `TypeError`, and `ValueError`.
- **Finiteness**: Rejects `float("inf")`, `-float("inf")`, and `float("nan")` (because comparisons with `NaN` return `False`, i.e., `not (-inf < nan < inf)` evaluates to `True`).

#### 2. `validate_identifier(identifier: object, name: str = "id") -> str` (lines 19–30)
```python
def validate_identifier(identifier: object, name: str = "id") -> str:
    if (
        isinstance(identifier, bool)
        or not isinstance(identifier, str)
        or not identifier
        or len(identifier) > 128
        or any(not (char.isascii() and (char.isalnum() or char in "_-")) for char in identifier)
    ):
        raise ValueError(
            f"{name} must be a non-empty ASCII identifier (letters, digits, underscore, hyphen)"
        )
    return identifier
```
- Rejects non-string types, boolean instances, empty strings, and strings exceeding 128 characters.
- Restricts characters strictly to ASCII alphanumeric characters, underscore `_`, and hyphen `-`. Disallows spaces, symbols (e.g., `@`, `/`, `#`), and non-ASCII Unicode (e.g., Cyrillic).

#### 3. `validate_text(text: object, name: str = "text", allow_newlines: bool = True) -> str` (lines 33–51)
```python
def validate_text(text: object, name: str = "text", allow_newlines: bool = True) -> str:
    if isinstance(text, bool) or not isinstance(text, str) or not text.strip():
        raise ValueError(f"{name} must be non-empty text")
    if len(text) > 4000:
        raise ValueError(f"{name} exceeds maximum length of 4000 characters")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in text):
        raise ValueError(f"{name} must not contain surrogate characters")
    if allow_newlines:
        if any(
            (ord(char) < 32 and char not in "\t\n\r")
            or ord(char) == 127
            or (128 <= ord(char) <= 159)
            for char in text
        ):
            raise ValueError(f"{name} must not contain control characters")
    else:
        if any(ord(char) < 32 or ord(char) == 127 or (128 <= ord(char) <= 159) for char in text):
            raise ValueError(f"{name} must not contain control characters")
    return text
```
- Enforces non-empty Unicode string with `text.strip()`.
- Imposes strict 4000-character ceiling to prevent buffer overflow attacks.
- Rejects UTF-16 surrogate codepoints (`0xD800`–`0xDFFF`).
- Sanitizes C0 controls (`ord < 32`), DEL (`127`), and C1 controls (`128..159`), selectively permitting `\t`, `\n`, `\r` when `allow_newlines=True`.

### 2.3 Inventory of Existing Models

| Model | Immutability | Key Fields | Validation Logic in `__post_init__` |
|---|---|---|---|
| `Config` | `frozen=True` | `sample_rate`, `hop_seconds`, `window_seconds`, `band_seconds`, `spectral_weight`, `max_frames`, `max_cells` | Exact sample rate (16000), bounds on floats via `finite_number`, `window_seconds >= hop_seconds`, integer ceiling for frames/cells. |
| `Cue` | `frozen=True` | `id`, `start`, `end`, `text` | Instantiated via `validate_cues(data, duration)`. Validates language='en', unique ASCII ID, plain Unicode text, `0 <= start < end <= duration`, strictly ordered non-overlapping. |
| `PhonemeCue` | `frozen=True` | `phoneme`, `start`, `end`, `confidence` | `validate_text(phoneme, allow_newlines=False)`, `0.0 <= start < end`, `0.0 <= confidence <= 1.0`. Coerces floats via `object.__setattr__`. |
| `WordToken` | `frozen=True` | `id`, `text`, `normalized`, `start`, `end`, `confidence`, `phonemes`, `char_start`, `char_end` | `validate_identifier(id)`, `validate_text` on `text` and `normalized`, `0.0 <= start < end`, `0.0 <= confidence <= 1.0`, `phonemes` is `list[PhonemeCue]`, character span consistency (`char_start <= char_end`). Coerces floats. |
| `ASRSegment` | `frozen=True` | `id`, `start`, `end`, `text`, `words` | `validate_identifier(id)`, `0.0 <= start < end`, `validate_text(text, allow_newlines=True)`, `words` is `list[WordToken]`. Coerces floats. |
| `AlignmentResult`| `frozen=True` | `words`, `phonemes`, `alignment_method`, `path_cost`, `evaluated_cells` | Validates list types of words and phonemes, single-line method name, non-negative finite `path_cost`, non-negative integer `evaluated_cells`. |

### 2.4 Representation of Subtitle Documents (`WebVTTDocument`)
- In `local-subtitle-workbench`, there is **no standalone `WebVTTDocument` class** in `models.py`.
- Instead, subtitle documents are modeled as `list[Cue]` instances.
- WebVTT serialization is implemented as a pure function `webvtt(cues: list[Cue]) -> str` in `src/subtitle_workbench/export.py`.
- Parsing and boundary validation of input cue data is handled by `validate_cues(data: object, duration: float) -> list[Cue]` in `src/subtitle_workbench/models.py`.
- Token-to-cue projection is performed by `project_tokens_to_cues(tokens: list[WordToken], original_text: str) -> list[Cue]` in `src/subtitle_workbench/text_norm.py`.

### 2.5 The Immutability Pattern (`frozen=True`)
In all existing models, `@dataclass(frozen=True)` is used to guarantee immutability. Because frozen dataclasses prohibit normal attribute assignment in `__post_init__` (raising `dataclasses.FrozenInstanceError`), attribute normalization and float coercion are performed using:
```python
object.__setattr__(self, "attribute_name", coerced_value)
```
This pattern must be strictly replicated in `AudioChunk` and `ChunkConfig`.

---

## 3. Requirement R1: Detailed Specification for `AudioChunk`

### 3.1 Field Signatures and Semantics
`AudioChunk` represents a partitioned audio window with padding seams:

```python
@dataclass(frozen=True)
class AudioChunk:
    id: str
    index: int
    start: float
    end: float
    padded_start: float
    padded_end: float
    text: str
    words: list[WordToken] = field(default_factory=list)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | Required | Unique ASCII identifier for the chunk (e.g., `"chunk_0"`, `"chunk-001"`). |
| `index` | `int` | Required | Non-negative sequential index of the chunk ($0, 1, 2, \dots$). |
| `start` | `float` | Required | Core chunk start timestamp in seconds (speech boundary). |
| `end` | `float` | Required | Core chunk end timestamp in seconds (speech boundary). |
| `padded_start` | `float` | Required | Left-padded timestamp in seconds ($\max(0.0, \text{start} - \Delta)$). |
| `padded_end` | `float` | Required | Right-padded timestamp in seconds ($\min(T_{\text{total}}, \text{end} + \Delta)$). |
| `text` | `str` | Required | Transcript text corresponding to the core audio chunk. |
| `words` | `list[WordToken]` | `field(default_factory=list)` | Words located within this chunk. |

### 3.2 Invariant Analysis
The core temporal invariant mandated by R1 is:
$$\mathbf{0.0 \le padded\_start \le start < end \le padded\_end}$$

To provide deterministic and clear error messages, this compound invariant decomposes into four sequential checks:
1. **Lower Bound Non-negativity**: `padded_start >= 0.0`. If `padded_start < 0.0`, raise `ValueError("padded_start must be nonnegative")`.
2. **Left Overlap Invariant**: `padded_start <= start`. If `padded_start > start`, raise `ValueError("padded_start must be less than or equal to start")`.
3. **Core Interval Strictly Positive Duration**: `start < end`. If `start >= end`, raise `ValueError("start must be strictly less than end")`.
   - *Note*: If `start == end`, duration is zero; if `start > end`, interval is inverted. Both are invalid.
4. **Right Overlap Invariant**: `end <= padded_end`. If `end > padded_end`, raise `ValueError("end must be less than or equal to padded_end")`.

**Mathematical Consequences of the Invariants:**
- Since $0.0 \le \text{padded\_start} \le \text{start}$, then $\text{start} \ge 0.0$ is unconditionally satisfied.
- Since $\text{start} < \text{end}$, then $\text{end} > 0.0$ is unconditionally satisfied.
- Since $\text{end} \le \text{padded\_end}$, then $\text{padded\_end} > 0.0$ is unconditionally satisfied.
- Boundary equality is explicitly valid:
  - At audio beginning ($t = 0.0$), $\text{padded\_start} = \text{start} = 0.0$.
  - At audio end ($t = T_{\text{total}}$), $\text{end} = \text{padded\_end} = T_{\text{total}}$.
  - When padding is configured as $0.0$, $\text{padded\_start} = \text{start}$ and $\text{end} = \text{padded\_end}$.

### 3.3 Non-Temporal Boundary Checks
1. **Identifier (`id`)**:
   - Must be verified via `validate_identifier(self.id, "id")`.
   - Rejects non-string, `bool`, empty string, length $> 128$, or characters outside `[A-Za-z0-9_-]`.
2. **Sequential Index (`index`)**:
   - Must be an `int` and not a `bool`: `isinstance(self.index, bool) or not isinstance(self.index, int)`.
   - Must be non-negative: `self.index < 0`.
   - Raises `ValueError("index must be a nonnegative integer")`.
3. **Transcript Text (`text`)**:
   - Must be verified via `validate_text(self.text, "text", allow_newlines=True)`.
   - Rejects empty, whitespace-only, $> 4000$ characters, surrogates, and control characters (allowing `\t`, `\n`, `\r`).
4. **Word Tokens (`words`)**:
   - Must be a `list` where every element is an instance of `WordToken`:
     ```python
     if not isinstance(self.words, list) or any(not isinstance(w, WordToken) for w in self.words):
         raise ValueError("words must be a list of WordToken instances")
     ```
   - Defensive copy: Store `list(self.words)` via `object.__setattr__(self, "words", list(self.words))` to prevent caller mutation of the internal list.

### 3.4 Proposed Implementation for `AudioChunk`
```python
@dataclass(frozen=True)
class AudioChunk:
    id: str
    index: int
    start: float
    end: float
    padded_start: float
    padded_end: float
    text: str
    words: list[WordToken] = field(default_factory=list)

    def __post_init__(self) -> None:
        validate_identifier(self.id, "id")
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
            raise ValueError("index must be a nonnegative integer")

        start = finite_number(self.start, "start")
        end = finite_number(self.end, "end")
        padded_start = finite_number(self.padded_start, "padded_start")
        padded_end = finite_number(self.padded_end, "padded_end")

        if padded_start < 0.0:
            raise ValueError("padded_start must be nonnegative")
        if padded_start > start:
            raise ValueError("padded_start must be less than or equal to start")
        if start >= end:
            raise ValueError("start must be strictly less than end")
        if end > padded_end:
            raise ValueError("end must be less than or equal to padded_end")

        validate_text(self.text, "text", allow_newlines=True)

        if not isinstance(self.words, list) or any(
            not isinstance(w, WordToken) for w in self.words
        ):
            raise ValueError("words must be a list of WordToken instances")

        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        object.__setattr__(self, "padded_start", padded_start)
        object.__setattr__(self, "padded_end", padded_end)
        object.__setattr__(self, "words", list(self.words))
```

---

## 4. Requirement R1: Detailed Specification for `ChunkConfig`

### 4.1 Field Signatures and Defaults
`ChunkConfig` governs macro-chunking duration thresholds and padding bounds:

```python
@dataclass(frozen=True)
class ChunkConfig:
    max_chunk_duration: float = 30.0
    min_chunk_duration: float = 1.0
    overlap_padding: float = 0.5
    min_silence_duration: float = 0.4
```

| Field | Type | Default | Domain / Bound | Description |
|---|---|---|---|---|
| `max_chunk_duration` | `float` | `30.0` | $> 0.0, \ge \text{min\_chunk\_duration}$ | Upper bound on chunk duration ($L \le 30.0\text{ s}$). |
| `min_chunk_duration` | `float` | `1.0` | $> 0.0$ | Minimum speech duration before a split is allowed. |
| `overlap_padding` | `float` | `0.5` | $\ge 0.0$ | Symmetric contextual padding ($\Delta = 0.5\text{ s}$). |
| `min_silence_duration` | `float` | `0.4` | $> 0.0$ | Natural pause threshold ($400\text{ ms}$, aligns with Silero-VAD). |

### 4.2 Invariant Analysis
1. **Finiteness & Type Safety**:
   - All fields must be verified with `finite_number(...)`.
   - Rejects `bool` (`True`/`False`), strings, `None`, `NaN`, `+inf`, `-inf`.
2. **Positivity of Durations**:
   - `min_chunk_duration`: A chunk cannot have zero or negative duration. `if min_chunk_duration <= 0.0: raise ValueError("min_chunk_duration must be positive")`.
   - `max_chunk_duration`: Must be at least `min_chunk_duration`. `if max_chunk_duration < min_chunk_duration: raise ValueError("max_chunk_duration must be at least min_chunk_duration")`.
3. **Non-negativity of Padding**:
   - `overlap_padding`: Can be zero ($0.0\text{ s}$) if unpadded chunking is desired, but cannot be negative. `if overlap_padding < 0.0: raise ValueError("overlap_padding must be nonnegative")`.
4. **Positivity of Silence Threshold**:
   - `min_silence_duration`: Silence duration for VAD pause detection must be positive. `if min_silence_duration <= 0.0: raise ValueError("min_silence_duration must be positive")`.

### 4.3 Proposed Implementation for `ChunkConfig`
```python
@dataclass(frozen=True)
class ChunkConfig:
    max_chunk_duration: float = 30.0
    min_chunk_duration: float = 1.0
    overlap_padding: float = 0.5
    min_silence_duration: float = 0.4

    def __post_init__(self) -> None:
        max_dur = finite_number(self.max_chunk_duration, "max_chunk_duration")
        min_dur = finite_number(self.min_chunk_duration, "min_chunk_duration")
        overlap = finite_number(self.overlap_padding, "overlap_padding")
        min_sil = finite_number(self.min_silence_duration, "min_silence_duration")

        if min_dur <= 0.0:
            raise ValueError("min_chunk_duration must be positive")
        if max_dur < min_dur:
            raise ValueError("max_chunk_duration must be at least min_chunk_duration")
        if overlap < 0.0:
            raise ValueError("overlap_padding must be nonnegative")
        if min_sil <= 0.0:
            raise ValueError("min_silence_duration must be positive")

        object.__setattr__(self, "max_chunk_duration", max_dur)
        object.__setattr__(self, "min_chunk_duration", min_dur)
        object.__setattr__(self, "overlap_padding", overlap)
        object.__setattr__(self, "min_silence_duration", min_sil)
```

---

## 5. Exports and Packaging (`src/subtitle_workbench/__init__.py`)

### 5.1 Current Exports
In `src/subtitle_workbench/__init__.py`:
```python
from .asr import (
    ASRError,
    ASRInferenceError,
    AudioFormatError,
    VRAMAllocationError,
    WhisperTranscriber,
    extract_vad_silences,
)
from .models import AlignmentResult, ASRSegment, Config, Cue, PhonemeCue, WordToken
from .text_norm import TokenSpan, normalize_text_spans, project_tokens_to_cues
```
`__all__` lists 16 symbols sorted alphabetically.

### 5.2 Updated Exports for Increment 3
`AudioChunk` and `ChunkConfig` must be exported from `src/subtitle_workbench/models.py`. In addition, when R2 (`chunker.py`) is implemented, `ChunkingError`, `MonotonicityError`, `partition_into_chunks`, and `reconcile_chunk_alignments` will also be exposed.

The updated `src/subtitle_workbench/__init__.py` will import:
```python
from .asr import (
    ASRError,
    ASRInferenceError,
    AudioFormatError,
    VRAMAllocationError,
    WhisperTranscriber,
    extract_vad_silences,
)
from .chunker import (
    ChunkingError,
    MonotonicityError,
    partition_into_chunks,
    reconcile_chunk_alignments,
)
from .models import (
    AlignmentResult,
    ASRSegment,
    AudioChunk,
    ChunkConfig,
    Config,
    Cue,
    PhonemeCue,
    WordToken,
)
from .text_norm import TokenSpan, normalize_text_spans, project_tokens_to_cues

__version__ = "0.1.0"

__all__ = [
    "ASRError",
    "ASRInferenceError",
    "ASRSegment",
    "AlignmentResult",
    "AudioChunk",
    "AudioFormatError",
    "ChunkConfig",
    "ChunkingError",
    "Config",
    "Cue",
    "MonotonicityError",
    "PhonemeCue",
    "TokenSpan",
    "VRAMAllocationError",
    "WhisperTranscriber",
    "WordToken",
    "extract_vad_silences",
    "normalize_text_spans",
    "partition_into_chunks",
    "project_tokens_to_cues",
    "reconcile_chunk_alignments",
]
```
Maintaining strict alphabetical sorting in `__all__` conforms to the project's formatting standard (`ruff`).

---

## 6. Comprehensive Test Matrix for R1

The test suite must cover both valid edge cases and defensive rejections. These unit tests should be co-located with speech model contracts in `tests/test_speech_models.py` (or a dedicated section in `tests/test_chunker.py`).

### 6.1 `AudioChunk` Test Cases

| Category | Test Case | Parameters / Condition | Expected Outcome |
|---|---|---|---|
| **Positive** | Standard instantiation | `id="c0", index=0, start=1.0, end=10.0, padded_start=0.5, padded_end=10.5, text="Hello", words=[sample_word()]` | Valid instance; floats coerced. |
| **Positive** | Left temporal boundary | `padded_start=0.0, start=0.0` (at audio start) | Valid (`padded_start == start`). |
| **Positive** | Right temporal boundary | `end=60.0, padded_end=60.0` (at audio end) | Valid (`end == padded_end`). |
| **Positive** | Unpadded chunk | `padded_start=5.0, start=5.0, end=15.0, padded_end=15.0` | Valid (`padded_start == start`, `end == padded_end`). |
| **Positive** | Empty words list | `words=[]` or omitted default | Valid (`chunk.words == []`). |
| **Positive** | Multiline text | `text="Line 1\nLine 2"` | Valid text. |
| **Negative** | Negative `padded_start` | `padded_start=-0.01` | Raises `ValueError("padded_start must be nonnegative")`. |
| **Negative** | Inverted left overlap | `padded_start=2.5, start=2.0` | Raises `ValueError("padded_start must be less than or equal to start")`. |
| **Negative** | Zero duration | `start=5.0, end=5.0` | Raises `ValueError("start must be strictly less than end")`. |
| **Negative** | Inverted core interval | `start=6.0, end=5.0` | Raises `ValueError("start must be strictly less than end")`. |
| **Negative** | Inverted right overlap | `end=10.0, padded_end=9.5` | Raises `ValueError("end must be less than or equal to padded_end")`. |
| **Negative** | Non-finite timestamps | `NaN`, `inf`, `-inf` in any of the 4 float fields | Raises `ValueError("... must be a finite number")`. |
| **Negative** | Boolean timestamps | `True`, `False` in any of the 4 float fields | Raises `ValueError("... must be a finite number")`. |
| **Negative** | Invalid `id` | `""`, `"   "`, `"chunk 0"`, `"chunk@0"`, `"кусок"`, `True`, `123`, `None`, `"a" * 129` | Raises `ValueError("id must be a non-empty ASCII identifier...")`. |
| **Negative** | Invalid `index` | `-1`, `0.5`, `"0"`, `True`, `False`, `None` | Raises `ValueError("index must be a nonnegative integer")`. |
| **Negative** | Invalid `text` | `""`, `"   "`, `None`, `123`, `\x00`, `\x7f`, `\ud800`, `"a" * 4001` | Raises `ValueError`. |
| **Negative** | Invalid `words` | `"not_a_list"`, `None`, `[123]`, `["word"]`, `[sample_phoneme()]` | Raises `ValueError("words must be a list of WordToken instances")`. |
| **Immutability**| Field mutation | `chunk.start = 2.0` | Raises `FrozenInstanceError` (or `AttributeError`). |

### 6.2 `ChunkConfig` Test Cases

| Category | Test Case | Parameters / Condition | Expected Outcome |
|---|---|---|---|
| **Positive** | Default values | `ChunkConfig()` | `max_chunk_duration == 30.0`, `min_chunk_duration == 1.0`, `overlap_padding == 0.5`, `min_silence_duration == 0.4`. |
| **Positive** | Custom valid configuration | `ChunkConfig(max_chunk_duration=15.0, min_chunk_duration=2.0, overlap_padding=0.25, min_silence_duration=0.3)` | Values stored as floats. |
| **Positive** | Zero overlap padding | `ChunkConfig(overlap_padding=0.0)` | Valid (`overlap_padding == 0.0`). |
| **Positive** | Equal min and max duration | `ChunkConfig(max_chunk_duration=5.0, min_chunk_duration=5.0)` | Valid (`max == min`). |
| **Negative** | `max < min` duration | `max_chunk_duration=1.0, min_chunk_duration=5.0` | Raises `ValueError("max_chunk_duration must be at least min_chunk_duration")`. |
| **Negative** | Non-positive min duration | `min_chunk_duration=0.0` or `-1.0` | Raises `ValueError("min_chunk_duration must be positive")`. |
| **Negative** | Negative overlap padding | `overlap_padding=-0.1` | Raises `ValueError("overlap_padding must be nonnegative")`. |
| **Negative** | Non-positive silence | `min_silence_duration=0.0` or `-0.4` | Raises `ValueError("min_silence_duration must be positive")`. |
| **Negative** | Non-finite / Boolean | `NaN`, `inf`, `True`, `False`, `"30.0"` in any field | Raises `ValueError("... must be a finite number")`. |
| **Immutability**| Field mutation | `config.max_chunk_duration = 20.0` | Raises `FrozenInstanceError` (or `AttributeError`). |

---

## 7. Implementation Roadmap & Recommendations for Parent / Implementers

1. **Phase 1 Implementation Order**:
   - Step 1: Add `AudioChunk` and `ChunkConfig` dataclasses to `src/subtitle_workbench/models.py`.
   - Step 2: Update `src/subtitle_workbench/__init__.py` with imports and alphabetized `__all__`.
   - Step 3: Implement unit test cases in `tests/test_speech_models.py` or `tests/test_chunker.py`.
   - Step 4: Run verification loop (`pytest`, `ruff check`, `ruff format --check`, wheel build).
2. **Defensive List Retention**:
   - In `AudioChunk.__post_init__`, retain `object.__setattr__(self, "words", list(self.words))` so that external modifications to the caller's list will not affect the chunk's internal word token sequence.
3. **No Retracted Claims & Zero Fabrications**:
   - In documentation and logs, maintain that Macro-DTW chunking guarantees linear $O(N)$ execution time across chunks, eliminating drift without unmeasured claims.
