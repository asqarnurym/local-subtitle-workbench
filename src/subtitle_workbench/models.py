"""Input contracts and resource bounds."""

from dataclasses import dataclass, field
from numbers import Real


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


@dataclass(frozen=True)
class Config:
    sample_rate: int = 16000
    hop_seconds: float = 0.02
    window_seconds: float = 0.04
    band_seconds: float = 0.5
    spectral_weight: float = 0.15
    max_frames: int = 3000
    max_cells: int = 2_000_000

    def __post_init__(self) -> None:
        if self.sample_rate != 16000 or isinstance(self.sample_rate, bool):
            raise ValueError("sample_rate must be 16000 Hz")
        for key, low, high in (
            ("hop_seconds", 0.005, 0.1),
            ("window_seconds", 0.005, 0.2),
            ("band_seconds", 0.02, 5.0),
            ("spectral_weight", 0.0, 1.0),
        ):
            if not low <= finite_number(getattr(self, key), key) <= high:
                raise ValueError(f"{key} must be between {low} and {high}")
        if self.window_seconds < self.hop_seconds:
            raise ValueError("window_seconds must be at least hop_seconds")
        for key, ceiling in (("max_frames", 10000), ("max_cells", 5_000_000)):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, int) or not 2 <= value <= ceiling:
                raise ValueError(f"{key} must be an integer between 2 and {ceiling}")


@dataclass(frozen=True)
class Cue:
    id: str
    start: float
    end: float
    text: str


def validate_cues(data: object, duration: float) -> list[Cue]:
    """Require checked, non-overlapping reference cues labelled English."""
    duration = finite_number(duration, "duration")
    if duration <= 0:
        raise ValueError("duration must be positive")
    if not isinstance(data, dict) or data.get("language") != "en":
        raise ValueError("cue JSON must contain language='en'")
    rows = data.get("cues")
    if not isinstance(rows, list) or not rows:
        raise ValueError("cues must be a non-empty list")
    result: list[Cue] = []
    ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "start", "end", "text"}:
            raise ValueError("each cue requires exactly id, start, end and text")
        identifier, text = row["id"], row["text"]
        if (
            not isinstance(identifier, str)
            or not identifier
            or len(identifier) > 128
            or any(not (char.isascii() and (char.isalnum() or char in "_-")) for char in identifier)
            or identifier in ids
        ):
            raise ValueError("cue IDs must be unique ASCII letters/digits/underscore/hyphen")
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text) > 4000
            or any(ord(char) < 32 and char != "\n" for char in text)
            or "\n\n" in text
            or text.startswith("\n")
            or text.endswith("\n")
            or any(0xD800 <= ord(char) <= 0xDFFF for char in text)
        ):
            raise ValueError("cue text must be plain Unicode without control/blank lines")
        start = finite_number(row["start"], "cue start")
        end = finite_number(row["end"], "cue end")
        if not 0 <= start < end <= duration:
            raise ValueError("cue times must satisfy 0 <= start < end <= audio duration")
        if result and start < result[-1].end:
            raise ValueError("cues must be ordered and non-overlapping")
        result.append(Cue(identifier, start, end, text))
        ids.add(identifier)
    return result


@dataclass(frozen=True)
class PhonemeCue:
    phoneme: str
    start: float
    end: float
    confidence: float

    def __post_init__(self) -> None:
        validate_text(self.phoneme, "phoneme", allow_newlines=False)
        start = finite_number(self.start, "start")
        end = finite_number(self.end, "end")
        if start < 0.0:
            raise ValueError("start must be nonnegative")
        if start >= end:
            raise ValueError("start must be strictly less than end")
        confidence = finite_number(self.confidence, "confidence")
        if not (0.0 <= confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        object.__setattr__(self, "confidence", confidence)


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

    def __post_init__(self) -> None:
        validate_identifier(self.id, "id")
        validate_text(self.text, "text", allow_newlines=False)
        validate_text(self.normalized, "normalized", allow_newlines=False)
        start = finite_number(self.start, "start")
        end = finite_number(self.end, "end")
        if start < 0.0:
            raise ValueError("start must be nonnegative")
        if start >= end:
            raise ValueError("start must be strictly less than end")
        confidence = finite_number(self.confidence, "confidence")
        if not (0.0 <= confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not isinstance(self.phonemes, list) or any(
            not isinstance(p, PhonemeCue) for p in self.phonemes
        ):
            raise ValueError("phonemes must be a list of PhonemeCue instances")
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("char_start and char_end must both be None or both be integers")
        if self.char_start is not None and self.char_end is not None:
            if (
                isinstance(self.char_start, bool)
                or not isinstance(self.char_start, int)
                or self.char_start < 0
            ):
                raise ValueError("char_start must be a nonnegative integer")
            if (
                isinstance(self.char_end, bool)
                or not isinstance(self.char_end, int)
                or self.char_end < self.char_start
            ):
                raise ValueError("char_end must be an integer >= char_start")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        object.__setattr__(self, "confidence", confidence)


@dataclass(frozen=True)
class ASRSegment:
    id: str
    start: float
    end: float
    text: str
    words: list[WordToken]

    def __post_init__(self) -> None:
        validate_identifier(self.id, "id")
        start = finite_number(self.start, "start")
        end = finite_number(self.end, "end")
        if start < 0.0:
            raise ValueError("start must be nonnegative")
        if start >= end:
            raise ValueError("start must be strictly less than end")
        validate_text(self.text, "text", allow_newlines=True)
        if not isinstance(self.words, list) or any(
            not isinstance(w, WordToken) for w in self.words
        ):
            raise ValueError("words must be a list of WordToken instances")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


@dataclass(frozen=True)
class AlignmentResult:
    words: list[WordToken]
    phonemes: list[PhonemeCue]
    alignment_method: str
    path_cost: float
    evaluated_cells: int

    def __post_init__(self) -> None:
        if not isinstance(self.words, list) or any(
            not isinstance(w, WordToken) for w in self.words
        ):
            raise ValueError("words must be a list of WordToken instances")
        if not isinstance(self.phonemes, list) or any(
            not isinstance(p, PhonemeCue) for p in self.phonemes
        ):
            raise ValueError("phonemes must be a list of PhonemeCue instances")
        validate_text(self.alignment_method, "alignment_method", allow_newlines=False)
        path_cost = finite_number(self.path_cost, "path_cost")
        if path_cost < 0.0:
            raise ValueError("path_cost must be nonnegative")
        if (
            isinstance(self.evaluated_cells, bool)
            or not isinstance(self.evaluated_cells, int)
            or self.evaluated_cells < 0
        ):
            raise ValueError("evaluated_cells must be a nonnegative integer")
        object.__setattr__(self, "path_cost", path_cost)
