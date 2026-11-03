"""Overlap-and-stitch alignment of chunked recordings (S1b; a documented deviation from v1).

Chosen on the seam micro-test (docs/S1B_MICROTEST_FINDINGS.md) after check C failed with
the seam-safe reconciler. Three changes, all applied by wrappers; the package is unchanged:

1. VAD: Silero-VAD with ``speech_pad_ms = SPEECH_PAD_MS`` instead of faster-whisper's
   default 400 ms, which hides every pause shorter than about 1.2 s, so seams land in
   real pauses.
2. Overlap: each chunk also gets the neighbouring chunks' words on both sides until they
   cover at least ``MIN_OVERLAP_S``; its audio ends in the gap after the outermost of
   them, so the padding holds no speech without text.
3. Stitch: at every seam both tracks have aligned the shared words. The anchor is a word
   aligned by both with the same text and boundaries within ``ANCHOR_TOL_S``, the one
   closest to the seam (never a track's outermost word). Track A keeps labels up to the
   anchor, track B those after it. Without an anchor the cut falls back to the seam time
   (logged). A monotone pass then guarantees a valid timeline.

A single-chunk recording is reconciled by the frozen function, exactly as before.
``stitched_pipeline()`` swaps 1-3 into ``prepare_alignment_job`` and the frozen aligner
for the duration of a ``with`` block.
"""

from __future__ import annotations

import dataclasses
import functools
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from scripts.seam_safe import monotone_timeline
from subtitle_workbench import aligner as aligner_module
from subtitle_workbench import pipeline as pipeline_module
from subtitle_workbench.chunker import aligner_text, reconcile_chunk_alignments
from subtitle_workbench.models import AudioChunk, WordToken

SPEECH_PAD_MS = 30
MIN_OVERLAP_S = 3.0
ANCHOR_TOL_S = 0.02


def vad_backend(samples: Any, sample_rate: int, min_silence_duration_ms: int) -> list:
    """Silero-VAD speech chunks (sample indices) with a small speech padding."""
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    opts = VadOptions(min_silence_duration_ms=min_silence_duration_ms, speech_pad_ms=SPEECH_PAD_MS)
    return get_speech_timestamps(samples, vad_options=opts)


def overlap_chunks(
    chunks: list[AudioChunk], duration: float, min_overlap: float = MIN_OVERLAP_S
) -> list[AudioChunk]:
    """Each chunk with its neighbours' words (>= ``min_overlap`` s each side) added."""
    out = []
    for k, c in enumerate(chunks):
        left: list[WordToken] = []
        right: list[WordToken] = []
        ps, pe = c.padded_start, c.padded_end
        if k > 0:
            prev = chunks[k - 1].words
            i = len(prev)
            while i > 0 and (not left or c.start - left[0].start < min_overlap):
                i -= 1
                left.insert(0, prev[i])
            ps = (prev[i - 1].end + prev[i].start) / 2 if i > 0 else chunks[k - 1].padded_start
            ps = min(ps, prev[i].start)
        if k < len(chunks) - 1:
            nxt = chunks[k + 1].words
            j = 0
            while j < len(nxt) and (not right or right[-1].end - c.end < min_overlap):
                right.append(nxt[j])
                j += 1
            pe = (nxt[j - 1].end + nxt[j].start) / 2 if j < len(nxt) else chunks[k + 1].padded_end
            pe = max(pe, nxt[j - 1].end)
        out.append(
            dataclasses.replace(
                c,
                padded_start=min(c.start, round(max(0.0, ps), 4)),
                padded_end=max(c.end, round(min(duration, pe), 4)),
                text=" ".join(aligner_text(w) for w in left + c.words + right),
            )
        )
    return out


def stitch(
    chunks: list[AudioChunk],
    chunk_aligned_words: list[list[WordToken]],
    padded_coordinates: bool = False,
    log: list[dict[str, Any]] | None = None,
) -> list[WordToken]:
    """Drop-in replacement for the frozen reconciler on overlapped chunks."""
    if len(chunks) == 1:
        words = reconcile_chunk_alignments(chunks, chunk_aligned_words, padded_coordinates)
        if log is not None:
            log.append({"n_chunks": 1, "method": "frozen_single_chunk", "n_words": len(words)})
        return words
    base = [c.padded_start if padded_coordinates else c.start for c in chunks]
    lo = [0] * len(chunks)
    hi = [len(w) for w in chunk_aligned_words]
    seams: list[dict[str, Any]] = []
    for k in range(len(chunks) - 1):
        a, b, t = chunk_aligned_words[k], chunk_aligned_words[k + 1], chunks[k].end
        best: tuple[float, int, int] | None = None
        for i, x in enumerate(a[1:], 1):
            xs, xe = base[k] + x.start, base[k] + x.end
            for j, y in enumerate(b[:-1]):
                ys, ye = base[k + 1] + y.start, base[k + 1] + y.end
                if (
                    x.normalized == y.normalized
                    and abs(xs - ys) <= ANCHOR_TOL_S
                    and abs(xe - ye) <= ANCHOR_TOL_S
                ):
                    d = abs((xs + xe) / 2 - t)
                    if best is None or d < best[0]:
                        best = (d, i, j)
        if best is None:  # fallback: cut at the seam time
            hi[k] = sum(base[k] + (x.start + x.end) / 2 < t for x in a)
            lo[k + 1] = sum(base[k + 1] + (y.start + y.end) / 2 < t for y in b)
            seams.append({"seam_s": round(t, 4), "anchor": None})
        else:
            hi[k], lo[k + 1] = best[1] + 1, best[2] + 1
            seams.append(
                {
                    "seam_s": round(t, 4),
                    "anchor": a[best[1]].text,
                    "anchor_to_seam_s": round(best[0], 3),
                }
            )
    kept = [w[lo[i] : hi[i]] for i, w in enumerate(chunk_aligned_words)]
    words = monotone_timeline(chunks, kept, padded_coordinates)
    if log is not None:
        log.append(
            {
                "n_chunks": len(chunks),
                "method": "stitch",
                "n_words": len(words),
                "n_no_anchor": sum(s["anchor"] is None for s in seams),
                "seams": seams,
            }
        )
    return words


@contextmanager
def stitched_pipeline(log: list[dict[str, Any]]) -> Iterator[None]:
    """Use the small-padding VAD, overlapped chunks and ``stitch`` for this block."""
    original_prepare = pipeline_module.prepare_alignment_job
    original_reconcile = aligner_module.reconcile_chunk_alignments

    @functools.wraps(original_prepare)
    def prepare(*args: Any, **kwargs: Any) -> Any:
        kwargs["vad_backend"] = vad_backend
        job = original_prepare(*args, **kwargs)
        return dataclasses.replace(job, chunks=overlap_chunks(job.chunks, job.duration))

    pipeline_module.prepare_alignment_job = prepare
    aligner_module.reconcile_chunk_alignments = functools.partial(stitch, log=log)
    try:
        yield
    finally:
        pipeline_module.prepare_alignment_job = original_prepare
        aligner_module.reconcile_chunk_alignments = original_reconcile
