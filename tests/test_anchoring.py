"""Tests for coarse transcript anchoring (banded word-level sequence alignment)."""

from __future__ import annotations

import pytest

from subtitle_workbench.anchoring import (
    anchor_transcript,
    banded_sequence_alignment,
    reference_tokens,
)
from subtitle_workbench.chunker import ChunkConfig, aligner_text, partition_into_chunks
from subtitle_workbench.models import ASRSegment, WordToken


def _hyp(words: list[tuple[str, float, float]]) -> list[WordToken]:
    return [
        WordToken(id=f"h{i}", text=t, normalized=t, start=s, end=e, confidence=0.9)
        for i, (t, s, e) in enumerate(words)
    ]


def test_reference_tokens_keep_contractions_and_numbers_whole() -> None:
    toks = reference_tokens("Don't count 42 apples.")
    assert [t.text for t in toks] == ["Don't", "count", "42", "apples"]
    assert toks[0].normalized == "do not"
    assert toks[2].normalized == "forty two"


def test_banded_alignment_exact_and_with_errors() -> None:
    ref = ["a", "b", "c", "d", "e"]
    assert banded_sequence_alignment(ref, ref) == [(i, i) for i in range(5)]
    # deletion of "c" and substitution of "e" in hypothesis
    hyp = ["a", "b", "d", "x"]
    assert banded_sequence_alignment(ref, hyp) == [(0, 0), (1, 1), (3, 2)]
    assert banded_sequence_alignment([], hyp) == []


def test_banded_alignment_long_sequence_with_offset() -> None:
    ref = [f"w{i}" for i in range(3000)]
    hyp = ["noise"] * 40 + ref[100:2900]  # missing head/tail, inserted noise
    pairs = banded_sequence_alignment(ref, hyp)
    assert len(pairs) == 2800
    assert all(ref[i] == hyp[j] for i, j in pairs)
    assert pairs == sorted(pairs)


def test_anchor_transcript_inherits_asr_times_and_interpolates_gaps() -> None:
    hyp = _hyp([("hello", 1.0, 1.4), ("big", 1.5, 1.8), ("world", 3.0, 3.5)])
    res = anchor_transcript("Hello brave new world", hyp, total_duration=5.0)
    assert res.n_reference == 4 and res.n_anchors == 2
    assert res.anchor_ratio == pytest.approx(0.5)
    hello, brave, new, world = res.words
    assert (hello.start, hello.end) == (1.0, 1.4)
    assert (world.start, world.end) == (3.0, 3.5)
    # Unmatched words are placed strictly between the anchors, in order
    assert hello.end <= brave.start < brave.end <= new.start < new.end <= world.start
    assert brave.confidence == 0.0


def test_anchor_transcript_without_hypothesis_spreads_over_audio() -> None:
    res = anchor_transcript("one two three", [], total_duration=3.0)
    assert res.n_anchors == 0
    assert res.words[0].start == 0.0
    assert res.words[-1].end <= 3.0
    assert all(a.end <= b.start for a, b in zip(res.words, res.words[1:], strict=False))


def test_anchor_transcript_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="no valid words"):
        anchor_transcript("... !!!", [], total_duration=1.0)


def test_long_lecture_anchoring_routes_text_to_correct_chunks() -> None:
    """Regression for uniform seeding: text must land in the chunk where it is spoken.

    Speech occupies only the second half of a 120 s recording. Uniform time seeding
    (old behaviour) put half of the words into the silent first half.
    """
    words = [f"term{i}" for i in range(120)]
    hyp = _hyp([(w, 60.0 + i * 0.5, 60.0 + i * 0.5 + 0.4) for i, w in enumerate(words)])
    res = anchor_transcript(" ".join(words), hyp, total_duration=120.0)
    assert res.n_anchors == 120
    seg = ASRSegment(id="s0", start=0.0, end=120.0, text="x", words=res.words)
    chunks = partition_into_chunks(
        [seg], silences=[(0.0, 59.9)], total_duration=120.0, config=ChunkConfig()
    )
    for chunk in chunks:
        for w in chunk.words:
            assert chunk.start - 1e-6 <= w.start and w.end <= chunk.end + 1e-6
    assert all(w.start >= 60.0 for c in chunks for w in c.words)


def test_aligner_text_spells_out_digits_only() -> None:
    w_num = WordToken(id="a", text="42", normalized="forty two", start=0, end=1, confidence=1)
    w_con = WordToken(id="b", text="don't", normalized="do not", start=1, end=2, confidence=1)
    assert aligner_text(w_num) == "forty two"
    assert aligner_text(w_con) == "don't"
