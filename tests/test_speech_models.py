"""Unit tests for speech data contracts and boundary validations."""

import pytest

from subtitle_workbench.models import (
    AlignmentResult,
    ASRSegment,
    PhonemeCue,
    WordToken,
    validate_identifier,
    validate_text,
)


def sample_phoneme() -> PhonemeCue:
    return PhonemeCue(phoneme="DH", start=0.1, end=0.18, confidence=0.95)


def sample_word() -> WordToken:
    return WordToken(
        id="w_1",
        text="The",
        normalized="the",
        start=0.1,
        end=0.35,
        confidence=0.98,
        phonemes=[sample_phoneme()],
        char_start=0,
        char_end=3,
    )


# --- PhonemeCue Tests ---


def test_phoneme_cue_valid():
    cue = PhonemeCue(phoneme="AE", start=0, end=0.25, confidence=1)
    assert cue.phoneme == "AE"
    assert cue.start == 0.0
    assert cue.end == 0.25
    assert cue.confidence == 1.0


@pytest.mark.parametrize(
    "start,end",
    [
        (0.5, 0.5),
        (0.6, 0.5),
        (-0.01, 0.5),
        (-1.0, -0.5),
    ],
)
def test_phoneme_cue_invalid_intervals(start, end):
    with pytest.raises(ValueError):
        PhonemeCue(phoneme="P", start=start, end=end, confidence=0.9)


@pytest.mark.parametrize(
    "field,value",
    [
        ("start", float("nan")),
        ("start", float("inf")),
        ("start", -float("inf")),
        ("start", True),
        ("start", False),
        ("start", "0.1"),
        ("start", None),
        ("end", float("nan")),
        ("end", float("inf")),
        ("end", True),
        ("confidence", float("nan")),
        ("confidence", float("inf")),
        ("confidence", True),
        ("confidence", -0.01),
        ("confidence", 1.01),
    ],
)
def test_phoneme_cue_nan_inf_bool(field, value):
    kwargs = {"phoneme": "T", "start": 0.1, "end": 0.2, "confidence": 0.9}
    kwargs[field] = value
    with pytest.raises(ValueError):
        PhonemeCue(**kwargs)


@pytest.mark.parametrize(
    "phoneme",
    [
        "",
        "   ",
        "DH\x00",
        "DH\x1f",
        "DH\x7f",
        "DH\x80",
        "DH\n",
        "DH\ud800",
        123,
        True,
        None,
    ],
)
def test_phoneme_cue_invalid_text(phoneme):
    with pytest.raises(ValueError):
        PhonemeCue(phoneme=phoneme, start=0.1, end=0.2, confidence=0.9)


# --- WordToken Tests ---


def test_word_token_valid():
    token = WordToken(
        id="word-01",
        text="don't",
        normalized="do",
        start=0.5,
        end=0.8,
        confidence=0.92,
    )
    assert token.id == "word-01"
    assert token.phonemes == []
    assert token.char_start is None
    assert token.char_end is None


@pytest.mark.parametrize(
    "bad_id",
    [
        "",
        "   ",
        "word 01",
        "word\n01",
        "word-->01",
        "w@rd",
        "w.1",
        "слово",
        "a" * 129,
        123,
        True,
        None,
    ],
)
def test_word_token_invalid_id(bad_id):
    with pytest.raises(ValueError):
        WordToken(
            id=bad_id,
            text="hello",
            normalized="hello",
            start=0.1,
            end=0.4,
            confidence=0.9,
        )


@pytest.mark.parametrize(
    "start,end",
    [
        (0.5, 0.5),
        (0.6, 0.5),
        (-0.1, 0.5),
    ],
)
def test_word_token_invalid_intervals(start, end):
    with pytest.raises(ValueError):
        WordToken(
            id="w1",
            text="hello",
            normalized="hello",
            start=start,
            end=end,
            confidence=0.9,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("start", float("nan")),
        ("start", True),
        ("end", float("inf")),
        ("confidence", float("nan")),
        ("confidence", 1.5),
        ("confidence", -0.1),
        ("confidence", True),
    ],
)
def test_word_token_nan_inf_bool(field, value):
    kwargs = {
        "id": "w1",
        "text": "hello",
        "normalized": "hello",
        "start": 0.1,
        "end": 0.4,
        "confidence": 0.9,
    }
    kwargs[field] = value
    with pytest.raises(ValueError):
        WordToken(**kwargs)


@pytest.mark.parametrize(
    "field,bad_text",
    [
        ("text", ""),
        ("text", "   "),
        ("text", "hello\x00"),
        ("text", "hello\x7f"),
        ("text", "hello\x80"),
        ("text", "hello\nworld"),
        ("text", 123),
        ("text", None),
        ("normalized", ""),
        ("normalized", "   "),
        ("normalized", "hello\x00"),
        ("normalized", "hello\x7f"),
        ("normalized", "hello\x80"),
        ("normalized", "hello\nworld"),
        ("normalized", 123),
    ],
)
def test_word_token_invalid_text_and_normalized(field, bad_text):
    kwargs = {
        "id": "w1",
        "text": "hello",
        "normalized": "hello",
        "start": 0.1,
        "end": 0.4,
        "confidence": 0.9,
    }
    kwargs[field] = bad_text
    with pytest.raises(ValueError):
        WordToken(**kwargs)


@pytest.mark.parametrize(
    "bad_phonemes",
    [
        "not_a_list",
        [123],
        [None],
        ["AE"],
    ],
)
def test_word_token_invalid_phonemes(bad_phonemes):
    with pytest.raises(ValueError):
        WordToken(
            id="w1",
            text="hello",
            normalized="hello",
            start=0.1,
            end=0.4,
            confidence=0.9,
            phonemes=bad_phonemes,
        )


@pytest.mark.parametrize(
    "char_start,char_end",
    [
        (5, None),
        (None, 5),
        (-1, 5),
        (5, 3),
        (True, 5),
        (0, True),
        (1.5, 5),
        ("0", "5"),
    ],
)
def test_word_token_invalid_char_spans(char_start, char_end):
    with pytest.raises(ValueError):
        WordToken(
            id="w1",
            text="hello",
            normalized="hello",
            start=0.1,
            end=0.4,
            confidence=0.9,
            char_start=char_start,
            char_end=char_end,
        )


# --- ASRSegment Tests ---


def test_asr_segment_valid():
    w = sample_word()
    seg = ASRSegment(id="seg_01", start=0.0, end=1.0, text="The quick brown fox", words=[w])
    assert seg.id == "seg_01"
    assert seg.start == 0.0
    assert seg.end == 1.0
    assert len(seg.words) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", ""),
        ("id", "seg 01"),
        ("id", "seg-->01"),
        ("start", float("nan")),
        ("start", True),
        ("start", -0.1),
        ("end", float("inf")),
        ("end", 0.0),
        ("text", ""),
        ("text", "hello\x00world"),
        ("text", "hello\x7fworld"),
        ("text", "hello\x80world"),
        ("words", "not_a_list"),
        ("words", [123]),
        ("words", None),
    ],
)
def test_asr_segment_invalid_fields(field, value):
    kwargs = {
        "id": "seg_01",
        "start": 0.0,
        "end": 1.0,
        "text": "Hello world",
        "words": [sample_word()],
    }
    kwargs[field] = value
    with pytest.raises(ValueError):
        ASRSegment(**kwargs)


# --- AlignmentResult Tests ---


def test_alignment_result_valid():
    res = AlignmentResult(
        words=[sample_word()],
        phonemes=[sample_phoneme()],
        alignment_method="mfa_hmm",
        path_cost=12.5,
        evaluated_cells=15000,
    )
    assert res.alignment_method == "mfa_hmm"
    assert res.path_cost == 12.5
    assert res.evaluated_cells == 15000


@pytest.mark.parametrize(
    "field,value",
    [
        ("words", "not_a_list"),
        ("words", [123]),
        ("phonemes", "not_a_list"),
        ("phonemes", [123]),
        ("alignment_method", ""),
        ("alignment_method", "mfa\x00"),
        ("alignment_method", "mfa\x7f"),
        ("alignment_method", "mfa\x80"),
        ("alignment_method", "mfa\n"),
        ("path_cost", -0.01),
        ("path_cost", float("nan")),
        ("path_cost", float("inf")),
        ("path_cost", True),
        ("evaluated_cells", -1),
        ("evaluated_cells", True),
        ("evaluated_cells", 1.5),
        ("evaluated_cells", "100"),
    ],
)
def test_alignment_result_invalid_fields(field, value):
    kwargs = {
        "words": [sample_word()],
        "phonemes": [sample_phoneme()],
        "alignment_method": "mfa_hmm",
        "path_cost": 5.0,
        "evaluated_cells": 1000,
    }
    kwargs[field] = value
    with pytest.raises(ValueError):
        AlignmentResult(**kwargs)


# --- Helper Tests ---


def test_validation_helpers():
    assert validate_identifier("valid_ID-123") == "valid_ID-123"
    with pytest.raises(ValueError):
        validate_identifier("bad id!")

    assert validate_text("Valid text\nwith newline") == "Valid text\nwith newline"
    with pytest.raises(ValueError):
        validate_text("Invalid\nwhen disallowed", allow_newlines=False)
    with pytest.raises(ValueError, match="control"):
        validate_text("bad\x7ftext")
    with pytest.raises(ValueError, match="control"):
        validate_text("bad\x80text")


def test_speech_models_zero_and_extreme_boundaries():
    # PhonemeCue boundary cases: start=0, confidence=0.0, confidence=1.0
    p0 = PhonemeCue(phoneme="DH", start=0.0, end=0.05, confidence=0.0)
    p1 = PhonemeCue(phoneme="AH", start=0.05, end=0.1, confidence=1.0)
    assert p0.confidence == 0.0
    assert p1.confidence == 1.0

    # WordToken boundary cases: empty phonemes, confidence=0.0, confidence=1.0
    w0 = WordToken(
        id="w-0",
        text="a",
        normalized="a",
        start=0.0,
        end=0.05,
        confidence=0.0,
        phonemes=[],
        char_start=0,
        char_end=1,
    )
    assert w0.confidence == 0.0
    assert w0.phonemes == []

    # ASRSegment boundary cases: empty words, multiline text
    seg = ASRSegment(
        id="seg-zero",
        start=0.0,
        end=10.0,
        text="Line one\nLine two\nLine three",
        words=[],
    )
    assert seg.words == []
    assert seg.start == 0.0

    # AlignmentResult boundary cases: path_cost=0.0, evaluated_cells=0, empty lists
    res0 = AlignmentResult(
        words=[],
        phonemes=[],
        alignment_method="exact_match",
        path_cost=0.0,
        evaluated_cells=0,
    )
    assert res0.path_cost == 0.0
    assert res0.evaluated_cells == 0
