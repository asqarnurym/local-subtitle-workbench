"""Tests for the seam-safe chunk reconciliation (scripts/seam_safe.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.seam_safe import (  # noqa: E402
    reconcile_seam_safe,
    seam_safe_reconciliation,
)
from subtitle_workbench import aligner as aligner_module  # noqa: E402
from subtitle_workbench.chunker import (  # noqa: E402
    MonotonicityError,
    reconcile_chunk_alignments,
)
from subtitle_workbench.models import AudioChunk, PhonemeCue, WordToken  # noqa: E402


def _word(wid: str, s: float, e: float, n_phones: int = 2) -> WordToken:
    step = (e - s) / n_phones
    phones = [PhonemeCue(f"p{k}", s + k * step, s + (k + 1) * step, 1.0) for k in range(n_phones)]
    return WordToken(wid, wid, wid, s, e, 0.9, phones)


def _chunk(i: int, start: float, end: float, total: float, pad: float = 0.5) -> AudioChunk:
    return AudioChunk(
        id=f"chunk_{i}",
        index=i,
        start=start,
        end=end,
        padded_start=max(0.0, start - pad) if i else 0.0,
        padded_end=min(total, end + pad),
        text="x",
    )


def _assert_valid(words: list[WordToken]) -> None:
    for a, b in zip(words, words[1:], strict=False):
        assert b.start > a.start and a.end <= b.start
    assert all(w.end > w.start for w in words)


def test_single_chunk_is_identical_to_frozen() -> None:
    chunk = _chunk(0, 0.0, 10.0, 10.0)
    words = [_word(f"w{i}", 0.3 + i, 0.9 + i) for i in range(9)]
    log: list = []
    got = reconcile_seam_safe([chunk], [words], padded_coordinates=True, log=log)
    assert got == reconcile_chunk_alignments([chunk], [words], padded_coordinates=True)
    assert log[0]["n_clipped"] == 0 and log[0]["method"] == "frozen_after_clip"


def test_stretched_edge_word_no_longer_fails_and_stays_in_its_chunk() -> None:
    # Seam at 10.0; chunk 1 audio starts at 9.5. Its first word was stretched back over
    # the previous chunk's last word (as for s02: 'everything' before 'with').
    chunks = [_chunk(0, 0.0, 10.0, 20.0), _chunk(1, 10.0, 20.0, 20.0)]
    first = [_word("a", 8.0, 9.0), _word("with", 9.4, 9.9)]
    second = [_word("everything", 9.5 - 9.5, 10.6 - 9.5), _word("b", 11.0 - 9.5, 11.5 - 9.5)]
    with pytest.raises(MonotonicityError):
        reconcile_chunk_alignments(chunks, [first, second], padded_coordinates=True)
    log: list = []
    got = reconcile_seam_safe(chunks, [first, second], padded_coordinates=True, log=log)
    assert [w.id for w in got] == ["a", "with", "everything", "b"]
    _assert_valid(got)
    assert got[2].start == pytest.approx(10.0) and got[2].end == pytest.approx(10.6)
    assert got[1].start == pytest.approx(9.4) and got[1].end == pytest.approx(9.9)
    assert log[0]["n_clipped"] == 1 and log[0]["max_clip_shift_ms"] == pytest.approx(500.0)


def test_word_wholly_in_padding_is_kept_at_the_core_edge() -> None:
    chunks = [_chunk(0, 0.0, 10.0, 20.0), _chunk(1, 10.0, 20.0, 20.0)]
    first = [_word("a", 8.0, 9.0), _word("z", 10.1, 10.4)]  # entirely in trailing padding
    second = [_word("b", 10.05 - 9.5, 10.5 - 9.5)]
    got = reconcile_seam_safe(chunks, [first, second], padded_coordinates=True)
    assert [w.id for w in got] == ["a", "z", "b"]
    _assert_valid(got)
    assert got[1].end <= 10.0 + 1e-9


def test_random_garbage_always_gives_a_valid_complete_timeline() -> None:
    rng = np.random.default_rng(0)
    for trial in range(300):
        n_chunks = int(rng.integers(1, 6))
        total = 10.0 * n_chunks
        chunks = [_chunk(i, 10.0 * i, 10.0 * (i + 1), total) for i in range(n_chunks)]
        per_chunk = []
        for c in chunks:
            span = c.padded_end - c.padded_start
            words = []
            for k in range(int(rng.integers(0, 12))):
                s = float(rng.uniform(0, span - 0.002))
                e = float(min(span, s + rng.uniform(0.001, 1.5)))
                words.append(_word(f"t{trial}c{c.index}w{k}", s, e, int(rng.integers(1, 6))))
            per_chunk.append(words)  # arbitrary order and overlaps within a chunk too
        got = reconcile_seam_safe(chunks, per_chunk, padded_coordinates=True)
        assert [w.id for w in got] == [w.id for ws in per_chunk for w in ws]
        _assert_valid(got)
        assert all(p.end > p.start for w in got for p in w.phonemes)


def test_context_manager_swaps_and_restores_the_frozen_reconciler() -> None:
    original = aligner_module.reconcile_chunk_alignments
    log: list = []
    with seam_safe_reconciliation(log):
        assert aligner_module.reconcile_chunk_alignments is not original
        chunk = _chunk(0, 0.0, 2.0, 2.0)
        aligner_module.reconcile_chunk_alignments([chunk], [[_word("w", 0.1, 0.5)]], True)
    assert aligner_module.reconcile_chunk_alignments is original
    assert len(log) == 1
