"""Seam-safe reconciliation of chunk alignments (S1b; a documented deviation from v1).

The frozen ``reconcile_chunk_alignments`` gives each chunk only its own words but its
audio with 0.5 s of context padding, where the neighbouring chunk's speech is. The
aligner must place every word it is given, so it often stretches an edge word over
that untranscribed speech; the two chunks then claim the same audio and the frozen
reconciler raises ``MonotonicityError`` for the whole recording.

Here every word is first clipped to its own chunk's core interval [start, end] (the
chunker assigned it there), then reconciled by the frozen function. If that still
fails or drops a word, a monotone pass makes onsets strictly increasing and removes
overlaps, so the result is always a valid timeline with every aligned word. Chunk 0
has no lower and the last chunk no upper clip, so a single-chunk recording is
reconciled exactly as by the frozen function.

``seam_safe_reconciliation()`` swaps it into the frozen aligner for the duration of a
``with`` block, leaving the package code unchanged.
"""

from __future__ import annotations

import functools
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from subtitle_workbench import aligner as aligner_module
from subtitle_workbench.chunker import MonotonicityError, reconcile_chunk_alignments
from subtitle_workbench.models import AudioChunk, PhonemeCue, WordToken

MIN_STEP_S = 0.001  # smallest onset step and word duration made here
MIN_PHONE_S = 0.0001  # one rounding step of the frozen 4-decimal timeline


def _clip(value: float, lo: float, hi: float) -> float:
    return min(max(value, lo), hi)


def _moved(
    w: WordToken, start: float, end: float, offset: float = 0.0, digits: int | None = None
) -> WordToken:
    """``w`` at [start, end]; phones are mapped linearly from the old span (+ offset)."""
    old_s, old_e = w.start + offset, w.end + offset
    scale = (end - start) / (old_e - old_s)

    def at(t: float) -> float:
        x = start + (t + offset - old_s) * scale
        return round(x, digits) if digits is not None else x

    phones = []
    for p in w.phonemes:
        ps, pe = at(p.start), at(p.end)
        if pe <= ps:
            pe = round(ps + MIN_PHONE_S, 4)
        phones.append(PhonemeCue(p.phoneme, ps, pe, p.confidence))
    return WordToken(
        id=w.id,
        text=w.text,
        normalized=w.normalized,
        start=start,
        end=end,
        confidence=w.confidence,
        phonemes=phones,
        char_start=w.char_start,
        char_end=w.char_end,
    )


def clip_to_core(
    chunks: list[AudioChunk], chunk_words: list[list[WordToken]], padded_coordinates: bool
) -> tuple[list[list[WordToken]], list[float]]:
    """Clip words (chunk-local time) to their chunk's core; returns words and shifts (s).

    A word lying wholly in the padding keeps ``MIN_STEP_S`` at the core edge.
    """
    last = len(chunks) - 1
    out: list[list[WordToken]] = []
    shifts: list[float] = []
    for c_idx, (chunk, words) in enumerate(zip(chunks, chunk_words, strict=True)):
        base = chunk.padded_start if padded_coordinates else chunk.start
        lo = chunk.start - base if c_idx > 0 else float("-inf")
        hi = chunk.end - base if c_idx < last else float("inf")
        clipped = []
        for w in words:
            s, e = _clip(w.start, lo, hi), _clip(w.end, lo, hi)
            if s == w.start and e == w.end:
                clipped.append(w)
                continue
            if e - s < MIN_STEP_S:
                s, e = (hi - MIN_STEP_S, hi) if s >= hi else (s, s + MIN_STEP_S)
            shifts.append(max(abs(s - w.start), abs(e - w.end)))
            clipped.append(_moved(w, s, e))
        out.append(clipped)
    return out, shifts


def monotone_timeline(
    chunks: list[AudioChunk], chunk_words: list[list[WordToken]], padded_coordinates: bool
) -> list[WordToken]:
    """Global timeline with strictly increasing onsets, positive durations, no overlaps."""
    flat: list[list[Any]] = []  # [word, base, start, end] in global time
    for chunk, words in zip(chunks, chunk_words, strict=True):
        base = chunk.padded_start if padded_coordinates else chunk.start
        flat.extend([w, base, max(0.0, base + w.start), base + w.end] for w in words)
    for i, item in enumerate(flat):
        item[2] = round(item[2], 4)
        if i > 0 and item[2] <= flat[i - 1][2]:
            item[2] = round(flat[i - 1][2] + MIN_STEP_S, 4)
        item[3] = round(max(item[3], item[2] + MIN_STEP_S), 4)
        if i > 0 and flat[i - 1][3] > item[2]:
            flat[i - 1][3] = item[2]  # still above the previous onset, which is < item[2]
    return [_moved(w, s, e, offset=base, digits=4) for w, base, s, e in flat]


def reconcile_seam_safe(
    chunks: list[AudioChunk],
    chunk_aligned_words: list[list[WordToken]],
    padded_coordinates: bool = False,
    log: list[dict[str, Any]] | None = None,
) -> list[WordToken]:
    """Drop-in replacement for the frozen reconciler that never fails on seams."""
    try:
        reconcile_chunk_alignments(chunks, chunk_aligned_words, padded_coordinates)
        frozen_ok = True
    except MonotonicityError:
        frozen_ok = False
    clipped, shifts = clip_to_core(chunks, chunk_aligned_words, padded_coordinates)
    n_in = sum(len(w) for w in clipped)
    method = "frozen_after_clip"
    try:
        words = reconcile_chunk_alignments(chunks, clipped, padded_coordinates)
    except MonotonicityError:
        words = []
    # The frozen seam deduplication drops a word clipped onto the very end of its
    # chunk; every aligned word is kept here, so such cases also take the monotone pass.
    if len(words) != n_in:
        words = monotone_timeline(chunks, clipped, padded_coordinates)
        method = "monotone_pass"
    if log is not None:
        log.append(
            {
                "n_chunks": len(chunks),
                "seams_s": [round(c.start, 4) for c in chunks[1:]],
                "n_words": len(words),
                "frozen_reconciler_ok": frozen_ok,
                "n_clipped": len(shifts),
                "max_clip_shift_ms": round(max(shifts, default=0.0) * 1000, 1),
                "method": method,
            }
        )
    return words


@contextmanager
def seam_safe_reconciliation(log: list[dict[str, Any]]) -> Iterator[None]:
    """Use ``reconcile_seam_safe`` inside the frozen ``ForcedAligner`` for this block."""
    original = aligner_module.reconcile_chunk_alignments
    aligner_module.reconcile_chunk_alignments = functools.partial(reconcile_seam_safe, log=log)
    try:
        yield
    finally:
        aligner_module.reconcile_chunk_alignments = original
