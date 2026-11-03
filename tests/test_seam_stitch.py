"""Tests for overlap-and-stitch alignment of chunked recordings (scripts/seam_stitch.py)."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import seam_stitch  # noqa: E402
from scripts.seam_stitch import overlap_chunks, stitch, stitched_pipeline  # noqa: E402
from subtitle_workbench import aligner as aligner_module  # noqa: E402
from subtitle_workbench import pipeline as pipeline_module  # noqa: E402
from subtitle_workbench.chunker import reconcile_chunk_alignments  # noqa: E402
from subtitle_workbench.models import AudioChunk, WordToken  # noqa: E402

TOTAL = 30.0


@dataclasses.dataclass
class FakeJob:
    chunks: list
    duration: float


def _word(i: int, s: float, e: float) -> WordToken:
    return WordToken(f"w{i}", f"word{i}", f"word{i}", s, e, 0.9)


def _layout() -> list[AudioChunk]:
    """30 words of 0.4 s every 1 s; seams at 10 and 20 s, frozen 0.5 s padding."""
    words = [_word(i, i + 0.3, i + 0.7) for i in range(30)]
    out = []
    for k, (s, e) in enumerate([(0.0, 10.0), (10.0, 20.0), (20.0, 30.0)]):
        out.append(
            AudioChunk(
                id=f"chunk_{k}",
                index=k,
                start=s,
                end=e,
                padded_start=max(0.0, s - 0.5),
                padded_end=min(TOTAL, e + 0.5),
                text="x",
                words=[w for w in words if s <= w.start < e],
            )
        )
    return out


def _track(chunk: AudioChunk, shift: float = 0.0) -> list[WordToken]:
    """What an aligner returns for an overlapped chunk: its text's words, local times."""
    by_text = {w.text: w for c in _layout() for w in c.words}
    return [
        dataclasses.replace(
            by_text[t],
            start=round(by_text[t].start - chunk.padded_start + shift, 4),
            end=round(by_text[t].end - chunk.padded_start + shift, 4),
        )
        for t in chunk.text.split()
    ]


def _assert_valid(words: list[WordToken]) -> None:
    for a, b in zip(words, words[1:], strict=False):
        assert b.start > a.start and a.end <= b.start
    assert all(w.end > w.start for w in words)


def test_overlap_adds_at_least_min_overlap_of_neighbour_words_and_keeps_cores() -> None:
    chunks = _layout()
    got = overlap_chunks(chunks, TOTAL, min_overlap=3.0)
    for k, (old, new) in enumerate(zip(chunks, got, strict=True)):
        assert (new.start, new.end, new.words) == (old.start, old.end, old.words)
        own = " ".join(w.text for w in old.words)
        assert own in new.text
        if k > 0:  # >= 3 s of the previous chunk's words, audio starts in the gap before
            assert new.text.split()[0] == f"word{10 * k - 4}" and new.padded_start == 10 * k - 4.0
        if k < 2:  # >= 3 s of the next chunk's words, audio ends in the gap after
            assert new.text.split()[-1] == f"word{10 * (k + 1) + 3}"
            assert new.padded_end == 10 * (k + 1) + 4.0
        assert new.padded_start <= new.start and new.end <= new.padded_end


def test_single_chunk_is_reconciled_by_the_frozen_function() -> None:
    chunk = AudioChunk(
        id="chunk_0", index=0, start=0.0, end=TOTAL, padded_start=0.0, padded_end=TOTAL, text="x"
    )
    words = [_word(i, i + 0.3, i + 0.7) for i in range(30)]
    log: list = []
    got = stitch([chunk], [words], padded_coordinates=True, log=log)
    assert got == reconcile_chunk_alignments([chunk], [words], padded_coordinates=True)
    assert log[0]["method"] == "frozen_single_chunk"


def test_agreeing_tracks_give_every_word_once_at_its_time() -> None:
    chunks = overlap_chunks(_layout(), TOTAL)
    log: list = []
    got = stitch(chunks, [_track(c) for c in chunks], padded_coordinates=True, log=log)
    assert [w.text for w in got] == [f"word{i}" for i in range(30)]
    assert all(abs(w.start - (i + 0.3)) < 1e-6 for i, w in enumerate(got))
    assert log[0]["n_no_anchor"] == 0
    assert [s["anchor_to_seam_s"] for s in log[0]["seams"]] == [0.5, 0.5]


def test_anchor_is_where_the_tracks_agree_not_the_seam() -> None:
    # Track B is off by 0.1 s except at word8, so the cut must be at word8 (2 s before the
    # seam): word9 comes from track B, words up to word8 from track A.
    chunks = overlap_chunks(_layout(), TOTAL)
    tracks = [_track(c) for c in chunks]
    tracks[1] = [
        w if w.text == "word8" else dataclasses.replace(w, start=w.start + 0.1, end=w.end + 0.1)
        for w in tracks[1]
    ]
    got = stitch(chunks, tracks, padded_coordinates=True)
    assert [w.text for w in got] == [f"word{i}" for i in range(30)]
    assert abs(got[8].start - 8.3) < 1e-6 and abs(got[9].start - 9.4) < 1e-6
    _assert_valid(got)


def test_no_anchor_falls_back_to_the_seam_time_and_stays_valid() -> None:
    chunks = overlap_chunks(_layout(), TOTAL)
    tracks = [_track(c, shift=0.05 * k) for k, c in enumerate(chunks)]
    log: list = []
    got = stitch(chunks, tracks, padded_coordinates=True, log=log)
    assert log[0]["n_no_anchor"] == 2 and log[0]["seams"][0]["anchor"] is None
    assert [w.text for w in got] == [f"word{i}" for i in range(30)]
    _assert_valid(got)


def test_pipeline_patch_uses_small_vad_padding_overlaps_and_restores() -> None:
    calls: dict = {}

    def fake_prepare(path, **kwargs):
        calls.update(kwargs)
        return FakeJob(chunks=_layout(), duration=TOTAL)

    original_prepare, original_reconcile = fake_prepare, aligner_module.reconcile_chunk_alignments
    saved = pipeline_module.prepare_alignment_job
    pipeline_module.prepare_alignment_job = fake_prepare
    try:
        with stitched_pipeline([]):
            job = pipeline_module.prepare_alignment_job("a.wav", max_chunk_sec=30.0)
            assert aligner_module.reconcile_chunk_alignments.func is stitch
        assert calls["vad_backend"] is seam_stitch.vad_backend
        assert job.chunks[1].text.split()[0] == "word6"
        assert pipeline_module.prepare_alignment_job is original_prepare
        assert aligner_module.reconcile_chunk_alignments is original_reconcile
    finally:
        pipeline_module.prepare_alignment_job = saved
