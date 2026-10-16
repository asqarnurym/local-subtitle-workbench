"""Unit tests for token-span text normalizer and reverse cue projection."""

import pytest

from subtitle_workbench.export import webvtt
from subtitle_workbench.models import WordToken, validate_cues
from subtitle_workbench.text_norm import (
    TokenSpan,
    integer_to_words,
    normalize_text_spans,
    parse_number_to_words,
    project_tokens_to_cues,
)


def assert_token_span_invariant(text: str, spans: list[TokenSpan]) -> None:
    """Enforce the critical invariant: text[span.char_start:span.char_end] == span.token."""
    for span in spans:
        extracted = text[span.char_start : span.char_end]
        assert extracted == span.token, (
            f"Invariant violated: expected {span.token!r}, got {extracted!r} "
            f"at offsets ({span.char_start}, {span.char_end})"
        )


# --- TokenSpan Dataclass Contract ---


def test_token_span_valid():
    span = TokenSpan(token="21", normalized="twenty", char_start=0, char_end=2)
    assert span.token == "21"
    assert span.normalized == "twenty"
    assert span.char_start == 0
    assert span.char_end == 2


@pytest.mark.parametrize(
    "token,normalized,char_start,char_end",
    [
        ("", "word", 0, 4),
        ("word", "", 0, 4),
        ("word", "word", -1, 4),
        ("word", "word", 5, 3),
        ("word", "word", True, 4),
        ("word", "word", 0, False),
        ("word", "word", 1.5, 4),
        (123, "word", 0, 4),
        ("word", 123, 0, 4),
    ],
)
def test_token_span_invalid(token, normalized, char_start, char_end):
    with pytest.raises(ValueError):
        TokenSpan(token=token, normalized=normalized, char_start=char_start, char_end=char_end)


# --- Number-to-Words Helper Tests ---


@pytest.mark.parametrize(
    "number,expected",
    [
        (0, ["zero"]),
        (1, ["one"]),
        (12, ["twelve"]),
        (21, ["twenty", "one"]),
        (100, ["one", "hundred"]),
        (105, ["one", "hundred", "five"]),
        (121, ["one", "hundred", "twenty", "one"]),
        (1000, ["one", "thousand"]),
        (1000000, ["one", "million"]),
        (-5, ["negative", "five"]),
    ],
)
def test_integer_to_words(number, expected):
    assert integer_to_words(number) == expected


@pytest.mark.parametrize(
    "token_str,expected",
    [
        ("21", ["twenty", "one"]),
        ("21st", ["twenty", "first"]),
        ("1st", ["first"]),
        ("2nd", ["second"]),
        ("3rd", ["third"]),
        ("4th", ["fourth"]),
        ("12th", ["twelfth"]),
        ("20th", ["twentieth"]),
        ("100th", ["one", "hundredth"]),
        ("1,000", ["one", "thousand"]),
        ("3.14", ["three", "point", "one", "four"]),
        ("-5", ["negative", "five"]),
        ("not_a_number", None),
    ],
)
def test_parse_number_to_words(token_str, expected):
    assert parse_number_to_words(token_str) == expected


# --- Normalization: Contractions ---


def test_normalize_contractions():
    text = "Don't say I'm not ready, because we'll win."
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)

    norm_words = [s.normalized for s in spans]
    # "Don't" -> ["do", "not"], "I'm" -> ["i", "am"], "we'll" -> ["we", "will"]
    assert "do" in norm_words
    assert "not" in norm_words
    assert "i" in norm_words
    assert "am" in norm_words
    assert "we" in norm_words
    assert "will" in norm_words

    # Verify original spans for contraction tokens
    dont_spans = [s for s in spans if s.token == "Don't"]
    assert len(dont_spans) == 2
    assert dont_spans[0].normalized == "do"
    assert dont_spans[1].normalized == "not"
    assert dont_spans[0].char_start == dont_spans[1].char_start == 0
    assert dont_spans[0].char_end == dont_spans[1].char_end == 5


def test_normalize_curly_apostrophes():
    text = "They didn’t believe it’s true."
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)
    norm_words = [s.normalized for s in spans]
    assert "did" in norm_words and "not" in norm_words
    assert "it" in norm_words and "is" in norm_words


# --- Normalization: Numbers & Ordinals ---


def test_normalize_numbers_and_ordinals():
    text = "At 21st century, don't stop at 42."
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)

    norm_words = [s.normalized for s in spans]
    assert norm_words == [
        "at",
        "twenty",
        "first",
        "century",
        "do",
        "not",
        "stop",
        "at",
        "forty",
        "two",
    ]

    # Verify both expanded tokens map to the exact same original slice
    twenty_span = [s for s in spans if s.normalized == "twenty"][0]
    first_span = [s for s in spans if s.normalized == "first"][0]
    assert twenty_span.token == "21st"
    assert first_span.token == "21st"
    assert (twenty_span.char_start, twenty_span.char_end) == (3, 7)
    assert (first_span.char_start, first_span.char_end) == (3, 7)


def test_normalize_negative_and_decimals():
    text = "Temperature dropped to -5 degrees with 3.14 ratio."
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)
    norm_words = [s.normalized for s in spans]
    assert "negative" in norm_words
    assert "five" in norm_words
    assert "three" in norm_words
    assert "point" in norm_words
    assert "one" in norm_words
    assert "four" in norm_words


# --- Normalization: Hyphenated Words & Acronyms ---


def test_normalize_hyphenated_words():
    text = "We built an end-to-end model."
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)

    hyphen_tokens = [s for s in spans if s.normalized in ("end", "to")]
    assert len(hyphen_tokens) == 3
    assert [s.token for s in hyphen_tokens] == ["end", "to", "end"]
    assert [s.normalized for s in hyphen_tokens] == ["end", "to", "end"]
    assert hyphen_tokens[0].char_start == 12 and hyphen_tokens[0].char_end == 15
    assert hyphen_tokens[1].char_start == 16 and hyphen_tokens[1].char_end == 18
    assert hyphen_tokens[2].char_start == 19 and hyphen_tokens[2].char_end == 22


def test_normalize_acronyms_and_casing():
    text = "The API and CPU performance on Windows."
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)

    norm_words = [s.normalized for s in spans]
    assert norm_words == ["the", "api", "and", "cpu", "performance", "on", "windows"]

    api_span = [s for s in spans if s.normalized == "api"][0]
    assert api_span.token == "API"
    assert text[api_span.char_start : api_span.char_end] == "API"


# --- Normalization: Punctuation & Whitespace Edge Cases ---


def test_normalize_edge_cases():
    assert normalize_text_spans("") == []
    assert normalize_text_spans("   \t\n  ") == []
    assert normalize_text_spans("... --- !!! ???") == []


def test_normalize_boundary_punctuation_and_multiple_whitespace():
    text = '  "...(Hello, world!)",   said   [CPU]  --end--!  '
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)

    norm_words = [s.normalized for s in spans]
    assert norm_words == ["hello", "world", "said", "cpu", "end"]


@pytest.mark.parametrize(
    "invalid_input",
    [
        123,
        True,
        None,
        ["Hello"],
        "Hello\x00World",
        "Hello\ud800World",
    ],
)
def test_normalize_text_invalid_inputs(invalid_input):
    with pytest.raises(ValueError):
        normalize_text_spans(invalid_input)


# --- Reverse Cue Projection Tests ---


def test_project_tokens_to_cues_single_cue():
    text = "At 21st century, don't stop."
    spans = normalize_text_spans(text)
    tokens = [
        WordToken(
            id=f"w{i}",
            text=span.token,
            normalized=span.normalized,
            start=round(i * 0.25, 3),
            end=round((i + 1) * 0.25, 3),
            confidence=0.95,
            char_start=span.char_start,
            char_end=span.char_end,
        )
        for i, span in enumerate(spans)
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 1
    assert cues[0].id == "c1"
    assert cues[0].start == tokens[0].start
    assert cues[0].end == tokens[-1].end
    assert cues[0].text == "At 21st century, don't stop."

    # Verify that the generated Cue serializes cleanly into WebVTT
    vtt = webvtt(cues)
    assert "WEBVTT" in vtt
    assert "00:00:00.000 --> 00:00:01.750" in vtt
    assert "At 21st century, don't stop." in vtt


def test_project_tokens_to_cues_multi_cue():
    text = "First cue.\n\nSecond cue."
    spans = normalize_text_spans(text)
    tokens = [
        WordToken(
            id=f"w{i}",
            text=span.token,
            normalized=span.normalized,
            start=round(i * 0.5, 3),
            end=round((i + 1) * 0.5, 3),
            confidence=0.99,
            char_start=span.char_start,
            char_end=span.char_end,
        )
        for i, span in enumerate(spans)
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 2
    assert cues[0].id == "c1"
    assert cues[0].text == "First cue."
    assert cues[0].start == tokens[0].start
    assert cues[0].end == tokens[1].end

    assert cues[1].id == "c2"
    assert cues[1].text == "Second cue."
    assert cues[1].start == tokens[2].start
    assert cues[1].end == tokens[3].end

    vtt = webvtt(cues)
    assert "First cue." in vtt
    assert "Second cue." in vtt


def test_project_tokens_to_cues_preserves_custom_ids():
    text = "cue-A\nFirst sentence.\n\ncue-B\nSecond sentence."
    spans = normalize_text_spans(text)
    tokens = [
        WordToken(
            id=f"w{i}",
            text=span.token,
            normalized=span.normalized,
            start=round(i * 0.5, 3),
            end=round((i + 1) * 0.5, 3),
            confidence=0.95,
            char_start=span.char_start,
            char_end=span.char_end,
        )
        for i, span in enumerate(spans)
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 2
    assert cues[0].id == "cue-A"
    assert cues[0].text == "First sentence."
    assert cues[1].id == "cue-B"
    assert cues[1].text == "Second sentence."


def test_project_tokens_to_cues_without_char_spans():
    text = "First sentence.\n\nSecond sentence."
    tokens = [
        WordToken("w1", "First", "first", 0.1, 0.4, 0.9),
        WordToken("w2", "sentence", "sentence", 0.4, 0.8, 0.9),
        WordToken("w3", "Second", "second", 1.0, 1.4, 0.9),
        WordToken("w4", "sentence", "sentence", 1.4, 1.9, 0.9),
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 2
    assert cues[0].start == 0.1
    assert cues[0].end == 0.8
    assert cues[1].start == 1.0
    assert cues[1].end == 1.9


def test_project_tokens_to_cues_empty_and_error_cases():
    assert project_tokens_to_cues([], "Some text") == []
    token = WordToken("w1", "word", "word", 0.1, 0.5, 0.9)
    assert project_tokens_to_cues([token], "") == []
    assert project_tokens_to_cues([token], "   \n\n  ") == []

    with pytest.raises(ValueError):
        project_tokens_to_cues("not_a_list", "Some text")
    with pytest.raises(ValueError):
        project_tokens_to_cues([123], "Some text")
    with pytest.raises(ValueError):
        project_tokens_to_cues([token], 123)


def test_project_tokens_to_cues_multiline_subtitle_without_id():
    text = "Hello\nworld"
    spans = normalize_text_spans(text)
    tokens = [
        WordToken(
            id=f"w{i}",
            text=span.token,
            normalized=span.normalized,
            start=round(i * 0.5, 3),
            end=round((i + 1) * 0.5, 3),
            confidence=0.95,
            char_start=span.char_start,
            char_end=span.char_end,
        )
        for i, span in enumerate(spans)
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 1
    assert cues[0].id == "c1"
    assert cues[0].text == "Hello\nworld"
    assert cues[0].start == 0.0
    assert cues[0].end == 1.0

    text2 = "Welcome\nto our presentation!"
    spans2 = normalize_text_spans(text2)
    tokens2 = [
        WordToken(
            f"w{i}",
            s.token,
            s.normalized,
            float(i),
            float(i + 1),
            0.9,
            char_start=s.char_start,
            char_end=s.char_end,
        )
        for i, s in enumerate(spans2)
    ]
    cues2 = project_tokens_to_cues(tokens2, text2)
    assert len(cues2) == 1
    assert cues2[0].id == "c1"
    assert cues2[0].text == "Welcome\nto our presentation!"


def test_project_tokens_to_cues_windows_crlf_newlines():
    text = "First line.\r\nSecond line.\r\n\r\nSecond cue."
    spans = normalize_text_spans(text)
    tokens = [
        WordToken(
            id=f"w{i}",
            text=span.token,
            normalized=span.normalized,
            start=round(i * 0.4, 3),
            end=round((i + 1) * 0.4, 3),
            confidence=0.95,
            char_start=span.char_start,
            char_end=span.char_end,
        )
        for i, span in enumerate(spans)
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 2
    assert "\r" not in cues[0].text
    assert cues[0].text == "First line.\nSecond line."
    assert cues[1].text == "Second cue."

    cue_data = {
        "language": "en",
        "cues": [{"id": c.id, "start": c.start, "end": c.end, "text": c.text} for c in cues],
    }
    validated = validate_cues(cue_data, duration=5.0)
    assert len(validated) == 2


def test_project_tokens_to_cues_deduplicate_duplicate_ids():
    text = "cue-A\nFirst sentence.\n\ncue-A\nSecond sentence."
    spans = normalize_text_spans(text)
    tokens = [
        WordToken(
            id=f"w{i}",
            text=span.token,
            normalized=span.normalized,
            start=round(i * 0.5, 3),
            end=round((i + 1) * 0.5, 3),
            confidence=0.95,
            char_start=span.char_start,
            char_end=span.char_end,
        )
        for i, span in enumerate(spans)
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 2
    assert cues[0].id == "cue-A"
    assert cues[1].id == "cue-A_1"
    cue_data = {
        "language": "en",
        "cues": [{"id": c.id, "start": c.start, "end": c.end, "text": c.text} for c in cues],
    }
    assert len(validate_cues(cue_data, duration=5.0)) == 2


def test_project_tokens_to_cues_input_validation():
    token = WordToken("w1", "test", "test", 0.0, 1.0, 0.9)
    with pytest.raises(ValueError, match="id_prefix"):
        project_tokens_to_cues([token], "test", id_prefix="")
    with pytest.raises(ValueError, match="id_prefix"):
        project_tokens_to_cues([token], "test", id_prefix="bad id!")
    with pytest.raises(ValueError, match="control"):
        project_tokens_to_cues([token], "test\x7ftext")
    with pytest.raises(ValueError, match="control"):
        project_tokens_to_cues([token], "test\x00text")
    with pytest.raises(ValueError, match="surrogate"):
        project_tokens_to_cues([token], "test\ud800text")


def test_normalize_academic_abbreviations_and_degrees():
    text = "Dr. Smith got his Ph.D. and M.Sc. in the U.S.A., e.g. at MIT."
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)
    norm_map = {s.token: s.normalized for s in spans}
    assert norm_map["Ph.D"] == "phd"
    assert norm_map["M.Sc"] == "msc"
    assert norm_map["U.S.A"] == "usa"
    assert norm_map["e.g"] == "eg"


def test_normalize_curly_possessives():
    text = "John’s book and Mary‘s car."
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)
    assert [s.token for s in spans] == ["John’s", "book", "and", "Mary‘s", "car"]
    assert [s.normalized for s in spans] == ["john's", "book", "and", "mary's", "car"]


def test_normalize_control_chars_rejected():
    with pytest.raises(ValueError, match="control"):
        normalize_text_spans("hello\x7fworld")
    with pytest.raises(ValueError, match="control"):
        normalize_text_spans("hello\x80world")


def test_token_span_defensive_control_and_surrogates():
    with pytest.raises(ValueError, match="control"):
        TokenSpan(token="hello\x00", normalized="hello", char_start=0, char_end=5)
    with pytest.raises(ValueError, match="control"):
        TokenSpan(token="hello", normalized="hello\x7f", char_start=0, char_end=5)
    with pytest.raises(ValueError, match="control"):
        TokenSpan(token="hello", normalized="hello\x80", char_start=0, char_end=5)
    with pytest.raises(ValueError, match="control"):
        TokenSpan(token="hello\n", normalized="hello", char_start=0, char_end=5)
    with pytest.raises(ValueError, match="surrogate"):
        TokenSpan(token="hello\ud800", normalized="hello", char_start=0, char_end=5)
    with pytest.raises(ValueError, match="non-empty text"):
        TokenSpan(token="   ", normalized="hello", char_start=0, char_end=3)
    with pytest.raises(ValueError, match="non-empty text"):
        TokenSpan(token="hello", normalized="   ", char_start=0, char_end=5)


def test_normalize_unicode_ellipsis_and_symbols():
    text = "Wait… is that a song? ♪ Soft music playing ♪ …yes!"
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)
    tokens = [s.token for s in spans]
    normalized = [s.normalized for s in spans]
    assert tokens == ["Wait", "is", "that", "a", "song", "Soft", "music", "playing", "yes"]
    assert normalized == ["wait", "is", "that", "a", "song", "soft", "music", "playing", "yes"]
    assert "…" not in normalized
    assert "♪" not in normalized


def test_normalize_unicode_minus_and_currency():
    text = "Loss of −42 points, −3.14 ratio, price €50 or £25 or ¥1000."
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)
    norm_words = [s.normalized for s in spans]
    assert "negative" in norm_words
    assert "forty" in norm_words
    assert "two" in norm_words
    assert "point" in norm_words
    assert "fifty" in norm_words
    assert "twenty" in norm_words
    assert "five" in norm_words
    assert "thousand" in norm_words


def test_normalize_typographical_quotes():
    text = "„Hello“ said Tom, ‚Yes’ and ‹Goodbye›."
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)
    tokens = [s.token for s in spans]
    assert tokens == ["Hello", "said", "Tom", "Yes", "and", "Goodbye"]
    assert [s.normalized for s in spans] == ["hello", "said", "tom", "yes", "and", "goodbye"]


def test_normalize_loanword_diacritics_cmudict_compatibility():
    text = "He drank a café au lait at a naïve protégé résumé event."
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)
    tokens = [s.token for s in spans]
    assert "café" in tokens
    assert "naïve" in tokens
    assert "protégé" in tokens
    assert "résumé" in tokens
    norm_words = [s.normalized for s in spans]
    assert "cafe" in norm_words
    assert "naive" in norm_words
    assert "protege" in norm_words
    assert "resume" in norm_words


def test_normalize_expanded_contractions():
    text = "It'd be nice, who'd know what'd happen, who'll see what'll come."
    spans = normalize_text_spans(text)
    assert_token_span_invariant(text, spans)
    norm_words = [s.normalized for s in spans]
    assert "it" in norm_words and "would" in norm_words
    assert "who" in norm_words and "did" in norm_words
    assert "what" in norm_words and "will" in norm_words


def test_project_tokens_to_cues_overlapping_mitigation():
    text = "First block.\n\nSecond block."
    # Simulate slightly overlapping tokens across cues from ASR
    tokens = [
        WordToken("w1", "First", "first", 0.0, 1.5, 0.9, char_start=0, char_end=5),
        WordToken("w2", "block", "block", 0.5, 1.5, 0.9, char_start=6, char_end=11),
        WordToken("w3", "Second", "second", 1.4, 2.5, 0.9, char_start=14, char_end=20),
        WordToken("w4", "block", "block", 1.8, 2.8, 0.9, char_start=21, char_end=26),
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 2
    assert cues[0].end == 1.5
    assert cues[1].start == 1.5
    assert cues[1].end == 2.8
    cue_data = {
        "language": "en",
        "cues": [{"id": c.id, "start": c.start, "end": c.end, "text": c.text} for c in cues],
    }
    assert len(validate_cues(cue_data, duration=5.0)) == 2


def test_project_tokens_to_cues_overlong_id_fallback():
    long_id = "cue-" + "x" * 200
    text = f"{long_id}\nHello world"
    spans = normalize_text_spans(text)
    tokens = [
        WordToken(
            id=f"w{i}",
            text=span.token,
            normalized=span.normalized,
            start=round(i * 0.5, 3),
            end=round((i + 1) * 0.5, 3),
            confidence=0.9,
            char_start=span.char_start,
            char_end=span.char_end,
        )
        for i, span in enumerate(spans)
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 1
    assert cues[0].id == "c1"


def test_project_tokens_to_cues_enclosed_overlap_monotonicity():
    text = "First block.\n\nSecond block."
    # Second block's tokens fall completely within or earlier than the first block's end time
    tokens = [
        WordToken("w1", "First", "first", 0.0, 1.5, 0.9, char_start=0, char_end=5),
        WordToken("w2", "block", "block", 0.5, 1.5, 0.9, char_start=6, char_end=11),
        WordToken("w3", "Second", "second", 0.5, 1.2, 0.9, char_start=14, char_end=20),
        WordToken("w4", "block", "block", 0.8, 1.2, 0.9, char_start=21, char_end=26),
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 2
    assert cues[0].start == 0.0
    assert cues[0].end == 1.5
    assert cues[1].start == 1.5
    assert cues[1].end == 2.2  # 1.5 + (1.2 - 0.5)
    cue_data = {
        "language": "en",
        "cues": [{"id": c.id, "start": c.start, "end": c.end, "text": c.text} for c in cues],
    }
    assert len(validate_cues(cue_data, duration=5.0)) == 2
    vtt = webvtt(cues)
    assert "00:00:00.000 --> 00:00:01.500" in vtt
    assert "00:00:01.500 --> 00:00:02.200" in vtt


def test_project_tokens_to_cues_fallback_enclosed_overlap():
    text = "First block.\n\nSecond block."
    # Test the fallback branch (without char spans) with enclosed overlap
    tokens = [
        WordToken("w1", "First", "first", 0.0, 1.5, 0.9),
        WordToken("w2", "block", "block", 0.5, 1.5, 0.9),
        WordToken("w3", "Second", "second", 0.4, 1.0, 0.9),
        WordToken("w4", "block", "block", 0.7, 1.0, 0.9),
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 2
    assert cues[0].start == 0.0
    assert cues[0].end == 1.5
    assert cues[1].start >= cues[0].end
    assert cues[1].end > cues[1].start
    cue_data = {
        "language": "en",
        "cues": [{"id": c.id, "start": c.start, "end": c.end, "text": c.text} for c in cues],
    }
    assert len(validate_cues(cue_data, duration=5.0)) == 2


def test_project_tokens_to_cues_submillisecond_collapse_prevention():
    text = "Tiny cue"
    # Token duration is 0.0004s, which collapses to 0ms without boundary protection
    tokens = [WordToken("w1", "Tiny", "tiny", 0.0, 0.0004, 0.9, char_start=0, char_end=4)]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 1
    # webvtt must not raise "cue collapses after millisecond rounding"
    vtt = webvtt(cues)
    assert "00:00:00.000 --> 00:00:00.001" in vtt


def test_project_tokens_to_cues_tab_character_normalization():
    text = "Hello\tworld\n\nSecond\tline"
    tokens = [
        WordToken("w1", "Hello", "hello", 0.0, 1.0, 0.9, char_start=0, char_end=5),
        WordToken("w2", "world", "world", 1.0, 2.0, 0.9, char_start=6, char_end=11),
        WordToken("w3", "Second", "second", 2.0, 3.0, 0.9, char_start=13, char_end=19),
        WordToken("w4", "line", "line", 3.0, 4.0, 0.9, char_start=20, char_end=24),
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 2
    assert cues[0].text == "Hello world"
    assert cues[1].text == "Second line"
    assert "\t" not in cues[0].text
    assert "\t" not in cues[1].text
    cue_data = {
        "language": "en",
        "cues": [{"id": c.id, "start": c.start, "end": c.end, "text": c.text} for c in cues],
    }
    assert len(validate_cues(cue_data, duration=5.0)) == 2


def test_project_tokens_to_cues_webvtt_timestamp_line_filtering():
    text = "c1\n00:00:01.000 --> 00:00:02.000\nHello world"
    tokens = [
        WordToken("w1", "Hello", "hello", 0.5, 1.5, 0.9),
        WordToken("w2", "world", "world", 1.5, 2.5, 0.9),
    ]
    cues = project_tokens_to_cues(tokens, text)
    assert len(cues) == 1
    assert cues[0].id == "c1"
    assert cues[0].text == "Hello world"
    assert cues[0].start == 0.5
    assert cues[0].end == 2.5
    vtt = webvtt(cues)
    assert "-->" in vtt
    # Ensure there is only 1 arrow line in the generated cue block
    assert vtt.count("-->") == 1
