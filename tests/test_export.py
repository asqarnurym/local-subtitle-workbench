import pytest

from subtitle_workbench.export import jsonld, timestamp, webvtt
from subtitle_workbench.models import Cue


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "00:00:00.000"),
        (0.0005, "00:00:00.001"),
        (59.9995, "00:01:00.000"),
        (3599.9995, "01:00:00.000"),
        (36000.1234, "10:00:00.123"),
    ],
)
def test_timestamp_rounding_and_carry(value, expected):
    assert timestamp(value) == expected


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True])
def test_invalid_timestamp(value):
    with pytest.raises(ValueError):
        timestamp(value)


def test_webvtt_escapes_markup_and_has_valid_blank_line_boundaries():
    text = webvtt([Cue("c1", 1.0, 2.001, "A <b>word</b> & B --> C")])
    assert text == (
        "WEBVTT\n\nc1\n00:00:01.000 --> 00:00:02.001\nA &lt;b&gt;word&lt;/b&gt; &amp; B --&gt; C\n"
    )


def test_collapsed_rounded_cue_is_rejected():
    with pytest.raises(ValueError, match="collapses"):
        webvtt([Cue("c1", 0.0001, 0.0002, "Too short")])


def test_jsonld_semantic_contract_and_offsets():
    data = jsonld([Cue("c1", 0.5, 1.2, "A & B")], 2.0, "lecture.mp4")
    assert data["@context"] == "https://schema.org"
    assert data["@type"] == "VideoObject"
    assert data["inLanguage"] == "en"
    assert data["duration"] == "PT2.000S"
    clip = data["hasPart"][0]
    assert clip["@type"] == "Clip"
    assert (clip["startOffset"], clip["endOffset"]) == (0.5, 1.2)
    assert clip["name"] == "A & B"
