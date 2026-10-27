"""Buckeye Speech Corpus native format reader and clip segmentation.

The corpus (Pitt et al., 2007; free for non-commercial use after registration at
buckeyecorpus.osu.edu) ships each interview track as ``sNNNNx.wav`` with
hand-corrected ``.words`` and ``.phones`` label files in xwaves format: a header
terminated by ``#``, then one line per interval ``<END time> <color> <label>``.
Interval start = previous interval end.

Interviews are long (≈10 min tracks) and contain interviewer speech (``<IVER>``),
noise and cut-off words, which are not transcribed. For forced-alignment
evaluation the speaker's speech is split into clips: maximal runs of ordinary
words that contain no non-speech/unknown token. Clips keep a short silence margin
but never extend into interviewer speech or noise.
"""

from __future__ import annotations

import re
import wave
from dataclasses import dataclass
from pathlib import Path

from .metrics import CorpusFormatError

SILENCE_LABELS = {"<sil>", "sil"}
_WORD_OK = re.compile(r"^[a-z][a-z'\-]*$")


@dataclass(frozen=True)
class Interval:
    start: float
    end: float
    label: str


@dataclass(frozen=True)
class BuckeyeClip:
    clip_id: str
    speaker: str
    start: float  # clip start in the track (seconds)
    end: float
    words: list[Interval]  # times relative to the track
    phones: list[Interval]


def _read_xwaves(path: Path) -> list[tuple[float, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Buckeye label file not found: {path}")
    # Some Buckeye files contain stray carriage returns inside lines (e.g. s3504a).
    lines = path.read_bytes().decode("latin-1").replace("\r", "").split("\n")
    try:
        body_start = next(i for i, line in enumerate(lines) if line.strip() == "#") + 1
    except StopIteration as err:
        raise CorpusFormatError(f"Missing '#' header terminator in {path.name}") from err
    rows: list[tuple[float, str]] = []
    for line_no, line in enumerate(lines[body_start:], start=body_start + 1):
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(None, 2)
        if len(parts) < 2:
            raise CorpusFormatError(f"Malformed line {line_no} in {path.name}: {line!r}")
        try:
            t = float(parts[0])
        except ValueError as err:
            raise CorpusFormatError(f"Non-numeric time on line {line_no} in {path.name}") from err
        label = parts[2] if len(parts) == 3 else ""
        rows.append((t, label))
    return rows


def _to_intervals(rows: list[tuple[float, str]]) -> list[Interval]:
    out: list[Interval] = []
    prev = 0.0
    for t, label in rows:
        if t > prev + 1e-9:
            out.append(Interval(prev, t, label))
        prev = max(prev, t)
    return out


def parse_buckeye_words(path: Path | str) -> list[Interval]:
    """Parse ``.words``; the label is the orthographic word (first ';' field), lowercased."""
    rows = [(t, lab.split(";")[0].strip().lower()) for t, lab in _read_xwaves(Path(path))]
    return _to_intervals(rows)


def parse_buckeye_phones(path: Path | str) -> list[Interval]:
    """Parse ``.phones``; the label is the phone (first token), lowercased."""
    rows = []
    for t, lab in _read_xwaves(Path(path)):
        token = lab.split(";")[0].strip().split()
        rows.append((t, token[0].lower() if token else ""))
    return _to_intervals(rows)


def is_regular_word(label: str) -> bool:
    return bool(_WORD_OK.match(label))


def segment_track(
    track_id: str,
    speaker: str,
    words: list[Interval],
    phones: list[Interval],
    track_duration: float,
    margin: float = 0.25,
    min_words: int = 3,
    min_duration: float = 1.0,
    max_duration: float = 30.0,
) -> tuple[list[BuckeyeClip], dict[str, int]]:
    """Split one track into evaluation clips; returns clips and exclusion counts."""
    clips: list[BuckeyeClip] = []
    stats = {"runs": 0, "too_short": 0, "too_long": 0}
    runs: list[list[int]] = []
    current: list[int] = []
    for idx, w in enumerate(words):
        if is_regular_word(w.label):
            current.append(idx)
        else:
            if current:
                runs.append(current)
            current = []
    if current:
        runs.append(current)

    for run in runs:
        stats["runs"] += 1
        first, last = words[run[0]], words[run[-1]]
        if len(run) < min_words or last.end - first.start < min_duration:
            stats["too_short"] += 1
            continue
        if last.end - first.start > max_duration:
            stats["too_long"] += 1
            continue
        prev_w = words[run[0] - 1] if run[0] > 0 else None
        next_w = words[run[-1] + 1] if run[-1] + 1 < len(words) else None
        left = first.start - margin if (prev_w and prev_w.label in SILENCE_LABELS) else first.start
        right = last.end + margin if (next_w and next_w.label in SILENCE_LABELS) else last.end
        if prev_w is not None:
            left = max(left, prev_w.start)
        if next_w is not None:
            right = min(right, next_w.end)
        left = max(0.0, left)
        right = min(track_duration, right)
        clip_words = [words[i] for i in run]
        clip_phones = [
            p for p in phones if p.start >= first.start - 1e-6 and p.end <= last.end + 1e-6
        ]
        clips.append(
            BuckeyeClip(
                clip_id=f"{track_id}_{len(clips):04d}",
                speaker=speaker,
                start=round(left, 6),
                end=round(right, 6),
                words=clip_words,
                phones=clip_phones,
            )
        )
    return clips, stats


def _textgrid(words: list[Interval], phones: list[Interval], offset: float, xmax: float) -> str:
    def tier(name: str, items: list[Interval], index: int) -> list[str]:
        filled: list[tuple[float, float, str]] = []
        cur = 0.0
        for it in items:
            s, e = round(it.start - offset, 6), round(it.end - offset, 6)
            if s > cur + 1e-9:
                filled.append((cur, s, ""))
            filled.append((s, e, it.label))
            cur = e
        if cur < xmax - 1e-9:
            filled.append((cur, xmax, ""))
        out = [
            f"    item [{index}]:",
            '        class = "IntervalTier"',
            f'        name = "{name}"',
            "        xmin = 0",
            f"        xmax = {xmax}",
            f"        intervals: size = {len(filled)}",
        ]
        for k, (s, e, lab) in enumerate(filled, start=1):
            out += [
                f"        intervals [{k}]:",
                f"            xmin = {s}",
                f"            xmax = {e}",
                f'            text = "{lab}"',
            ]
        return out

    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        f"xmax = {xmax}",
        "tiers? <exists>",
        "size = 2",
        "item []:",
    ]
    lines += tier("words", words, 1)
    lines += tier("phones", phones, 2)
    return "\n".join(lines) + "\n"


def stage_track(
    wav_path: Path | str,
    words_path: Path | str,
    phones_path: Path | str,
    out_dir: Path | str,
    speaker: str | None = None,
) -> tuple[list[BuckeyeClip], dict[str, int]]:
    """Cut one Buckeye track into ``<clip>.wav`` + ``<clip>.TextGrid`` + ``<clip>.txt``."""
    wav_path = Path(wav_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    track_id = wav_path.stem
    speaker = speaker or track_id[:3]
    with wave.open(str(wav_path), "rb") as src:
        sr, n_ch, width = src.getframerate(), src.getnchannels(), src.getsampwidth()
        if n_ch != 1 or width != 2:
            raise CorpusFormatError(f"{wav_path.name}: expected mono PCM16 audio")
        frames = src.readframes(src.getnframes())
    duration = len(frames) / (2 * sr)
    words = parse_buckeye_words(words_path)
    phones = parse_buckeye_phones(phones_path)
    clips, stats = segment_track(track_id, speaker, words, phones, duration)
    for clip in clips:
        a, b = int(round(clip.start * sr)) * 2, int(round(clip.end * sr)) * 2
        with wave.open(str(out_dir / f"{clip.clip_id}.wav"), "wb") as dst:
            dst.setnchannels(1)
            dst.setsampwidth(2)
            dst.setframerate(sr)
            dst.writeframes(frames[a:b])
        xmax = round(clip.end - clip.start, 6)
        (out_dir / f"{clip.clip_id}.TextGrid").write_text(
            _textgrid(clip.words, clip.phones, clip.start, xmax), encoding="utf-8"
        )
        (out_dir / f"{clip.clip_id}.txt").write_text(
            " ".join(w.label for w in clip.words) + "\n", encoding="utf-8"
        )
    return clips, stats


__all__ = [
    "BuckeyeClip",
    "Interval",
    "is_regular_word",
    "parse_buckeye_phones",
    "parse_buckeye_words",
    "segment_track",
    "stage_track",
]
