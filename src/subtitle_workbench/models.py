"""Input contracts and resource bounds."""

from dataclasses import dataclass
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
