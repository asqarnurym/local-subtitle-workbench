"""Tests for phone-set folding and the Buckeye native-format reader/segmenter."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from subtitle_workbench.buckeye import (
    Interval,
    parse_buckeye_phones,
    parse_buckeye_words,
    segment_track,
    stage_track,
)
from subtitle_workbench.corpora import parse_buckeye_textgrid
from subtitle_workbench.metrics import CorpusFormatError, evaluate_alignment_boundaries
from subtitle_workbench.models import PhonemeCue
from subtitle_workbench.phone_sets import fold_label, fold_phones

# ---------------------------------------------------------------------------
# Phone folding
# ---------------------------------------------------------------------------


def test_fold_label_inventories() -> None:
    assert fold_label("AH0") == "ah"  # ARPAbet stress removed
    assert fold_label("AO1") == "aa"  # 61->39 folding
    assert fold_label("ix") == "ih"
    assert fold_label("zh") == "sh"
    assert fold_label("aan") == "aa"  # Buckeye nasalized vowel
    assert fold_label("dx") == "t"
    for silent in ("h#", "pau", "epi", "q", "tq", "sil", "spn", "<SIL>", "{B_TRANS}"):
        assert fold_label(silent) is None


def test_fold_phones_merges_closure_and_release() -> None:
    timit = [
        PhonemeCue("bcl", 0.10, 0.15, 1.0),
        PhonemeCue("b", 0.15, 0.17, 1.0),
        PhonemeCue("ix", 0.17, 0.25, 1.0),
        PhonemeCue("tcl", 0.25, 0.30, 1.0),  # unreleased closure
        PhonemeCue("q", 0.30, 0.32, 1.0),
        PhonemeCue("dcl", 0.32, 0.36, 1.0),
        PhonemeCue("jh", 0.36, 0.42, 1.0),
    ]
    folded = fold_phones(timit)
    assert [(p.phoneme, p.start, p.end) for p in folded] == [
        ("b", 0.10, 0.17),
        ("ih", 0.17, 0.25),
        ("t", 0.25, 0.30),
        ("jh", 0.32, 0.42),
    ]


def test_folded_timit_and_mfa_phones_are_comparable() -> None:
    ref = fold_phones(
        [
            PhonemeCue("sh", 0.0, 0.1, 1.0),
            PhonemeCue("ix", 0.1, 0.2, 1.0),
            PhonemeCue("dcl", 0.2, 0.25, 1.0),
            PhonemeCue("d", 0.25, 0.3, 1.0),
        ]
    )
    mfa = fold_phones(
        [
            PhonemeCue("SH", 0.0, 0.11, 1.0),
            PhonemeCue("IH1", 0.11, 0.2, 1.0),
            PhonemeCue("D", 0.2, 0.3, 1.0),
        ]
    )
    ev = evaluate_alignment_boundaries(mfa, ref)
    assert ev.num_matched == 3 and ev.num_unmatched == 0


# ---------------------------------------------------------------------------
# Buckeye
# ---------------------------------------------------------------------------

WORDS_FILE = """signal s0101a
type 0
color 121
font -misc-*-bold-*-*-*-15-*-*-*-*-*-*-*
separator ;
nfields 4
#
    0.500000  121 <SIL>; <SIL>; <SIL>; null
    0.800000  121 okay; ow k ey; ow k ey; UH
    1.100000  121 so; s ow; s ow; RB
    1.500000  121 we; w iy; w iy; PRP
    1.900000  121 went; w eh n t; w eh n; VBD
    2.600000  121 <SIL>; <SIL>; <SIL>; null
    4.000000  121 <IVER>; <IVER>; <IVER>; null
    4.300000  121 yeah; y eh; y eh; UH
    4.600000  121 <SIL>; <SIL>; <SIL>; null
"""

PHONES_FILE = """signal s0101a
type 0
color 121
#
    0.500000  122 SIL
    0.600000  122 ow
    0.700000  122 k
    0.800000  122 ey
    0.950000  122 s
    1.100000  122 own
    1.300000  122 w
    1.500000  122 iy
    1.600000  122 w
    1.750000  122 eh
    1.900000  122 n
    2.600000  122 SIL
    4.000000  122 IVER
    4.150000  122 y
    4.300000  122 eh
    4.600000  122 SIL
"""


def _write_track(tmp_path: Path) -> tuple[Path, Path, Path]:
    wav = tmp_path / "s0101a.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x10\x00" * int(16000 * 4.6))
    words = tmp_path / "s0101a.words"
    phones = tmp_path / "s0101a.phones"
    words.write_text(WORDS_FILE, encoding="latin-1")
    phones.write_text(PHONES_FILE, encoding="latin-1")
    return wav, words, phones


def test_parse_buckeye_words_and_phones(tmp_path: Path) -> None:
    _, words, phones = _write_track(tmp_path)
    w = parse_buckeye_words(words)
    assert w[0] == Interval(0.0, 0.5, "<sil>")
    assert w[1] == Interval(0.5, 0.8, "okay")
    p = parse_buckeye_phones(phones)
    assert p[1] == Interval(0.5, 0.6, "ow")
    assert p[5].label == "own"


def test_parse_buckeye_requires_header_terminator(tmp_path: Path) -> None:
    bad = tmp_path / "bad.words"
    bad.write_text("signal x\n 0.5 121 hi; h ay; h ay; UH\n", encoding="latin-1")
    with pytest.raises(CorpusFormatError, match="header terminator"):
        parse_buckeye_words(bad)


def test_segment_track_splits_on_non_speech_and_limits_margins(tmp_path: Path) -> None:
    _, words, phones = _write_track(tmp_path)
    clips, stats = segment_track(
        "s0101a", "s01", parse_buckeye_words(words), parse_buckeye_phones(phones), 4.6
    )
    assert len(clips) == 1  # "yeah" after <IVER> is a 1-word run -> too short
    assert stats == {"runs": 2, "too_short": 1, "too_long": 0}
    clip = clips[0]
    assert [w.label for w in clip.words] == ["okay", "so", "we", "went"]
    # 0.25 s silence margin on both sides (neighbours are <SIL>)
    assert (clip.start, clip.end) == (0.25, 2.15)
    assert [p.label for p in clip.phones][:3] == ["ow", "k", "ey"]


def test_stage_track_writes_clip_audio_and_textgrid(tmp_path: Path) -> None:
    wav, words, phones = _write_track(tmp_path)
    out = tmp_path / "clips"
    clips, _ = stage_track(wav, words, phones, out)
    clip_id = clips[0].clip_id
    with wave.open(str(out / f"{clip_id}.wav"), "rb") as w:
        assert abs(w.getnframes() / 16000 - 1.9) < 1e-3
    ref_words = parse_buckeye_textgrid(out / f"{clip_id}.TextGrid")
    assert [w.text for w in ref_words] == ["okay", "so", "we", "went"]
    assert ref_words[0].start == pytest.approx(0.25, abs=1e-4)  # clip-relative
    assert [p.phoneme for p in ref_words[0].phonemes] == ["ow", "k", "ey"]
    assert (out / f"{clip_id}.txt").read_text().strip() == "okay so we went"


def test_parse_buckeye_tolerates_stray_carriage_returns(tmp_path: Path) -> None:
    f = tmp_path / "x.words"
    f.write_bytes(
        b"signal x\r\nnfields 1(\r\n#\r\n   0.500000 122 <IVER>\r; null\n"
        b"   0.900000 122 right; r ay t; r ay t\r; RB\n"
    )
    assert [w.label for w in parse_buckeye_words(f)] == ["<iver>", "right"]
