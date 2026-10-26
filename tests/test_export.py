import json
from pathlib import Path

import pytest

from subtitle_workbench.export import (
    export_jsonld,
    export_karaoke_vtt,
    export_raw_alignment,
    format_vtt_timestamp,
    generate_manifest,
    jsonld,
    timestamp,
    webvtt,
)
from subtitle_workbench.models import Config, Cue, PhonemeCue, WordToken
from subtitle_workbench.provenance import code_provenance, sha256


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
    assert format_vtt_timestamp(value) == expected


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True])
def test_invalid_timestamp(value):
    with pytest.raises(ValueError):
        timestamp(value)
    with pytest.raises(ValueError):
        format_vtt_timestamp(value)


def test_format_vtt_timestamp_alias():
    assert timestamp is format_vtt_timestamp


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


# -----------------------------------------------------------------------------
# export_karaoke_vtt tests
# -----------------------------------------------------------------------------


def test_export_karaoke_vtt_empty():
    assert export_karaoke_vtt([]) == "WEBVTT\n\n"


def test_export_karaoke_vtt_single_word():
    w = WordToken(id="w1", text="Hello", normalized="hello", start=1.0, end=1.5, confidence=0.98)
    output = export_karaoke_vtt([w])
    expected = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:01.500\n<c.word><00:00:01.000>Hello</c>\n"
    assert output == expected


def test_export_karaoke_vtt_escapes_html():
    w = WordToken(
        id="w1",
        text="Rock & <Roll>",
        normalized="rock roll",
        start=0.5,
        end=1.2,
        confidence=0.9,
    )
    output = export_karaoke_vtt([w])
    assert "<c.word><00:00:00.500>Rock &amp; &lt;Roll&gt;</c>" in output


def test_export_karaoke_vtt_breaks_on_max_line_words():
    words = [
        WordToken(
            id=f"w{i}",
            text=f"word{i}",
            normalized=f"word{i}",
            start=float(i),
            end=float(i) + 0.8,
            confidence=0.9,
        )
        for i in range(10)
    ]
    # With max_line_words=4, 10 words should segment into 4 + 4 + 2 = 3 cues
    output = export_karaoke_vtt(words, max_line_words=4, max_line_chars=100, max_pause_break=10.0)
    blocks = [b for b in output.strip().split("\n\n") if b != "WEBVTT"]
    assert len(blocks) == 3
    assert blocks[0].startswith("1\n00:00:00.000 --> 00:00:03.800")
    assert blocks[1].startswith("2\n00:00:04.000 --> 00:00:07.800")
    assert blocks[2].startswith("3\n00:00:08.000 --> 00:00:09.800")


def test_export_karaoke_vtt_breaks_on_max_line_chars():
    words = [
        WordToken(
            id="w1",
            text="FirstLongWord",
            normalized="firstlongword",
            start=0.0,
            end=1.0,
            confidence=0.9,
        ),
        WordToken(
            id="w2",
            text="SecondLongWord",
            normalized="secondlongword",
            start=1.1,
            end=2.0,
            confidence=0.9,
        ),
        WordToken(
            id="w3",
            text="ThirdLongWord",
            normalized="thirdlongword",
            start=2.1,
            end=3.0,
            confidence=0.9,
        ),
    ]
    # "FirstLongWord SecondLongWord" has 28 characters. With max_line_chars=25, it must break.
    output = export_karaoke_vtt(words, max_line_words=10, max_line_chars=25, max_pause_break=5.0)
    blocks = [b for b in output.strip().split("\n\n") if b != "WEBVTT"]
    assert len(blocks) == 3


def test_export_karaoke_vtt_breaks_on_pause():
    words = [
        WordToken(id="w1", text="Before", normalized="before", start=0.0, end=1.0, confidence=0.9),
        WordToken(id="w2", text="Pause", normalized="pause", start=1.1, end=2.0, confidence=0.9),
        # Gap of 1.5s between end=2.0 and start=3.5
        WordToken(id="w3", text="After", normalized="after", start=3.5, end=4.5, confidence=0.9),
    ]
    output = export_karaoke_vtt(words, max_line_words=10, max_line_chars=100, max_pause_break=1.0)
    blocks = [b for b in output.strip().split("\n\n") if b != "WEBVTT"]
    assert len(blocks) == 2
    assert blocks[0].startswith("1\n00:00:00.000 --> 00:00:02.000")
    assert blocks[1].startswith("2\n00:00:03.500 --> 00:00:04.500")


def test_export_karaoke_vtt_non_monotonic_raises():
    words = [
        WordToken(id="w1", text="Second", normalized="second", start=2.0, end=3.0, confidence=0.9),
        WordToken(id="w2", text="First", normalized="first", start=1.0, end=1.5, confidence=0.9),
    ]
    with pytest.raises(ValueError, match="monotonic"):
        export_karaoke_vtt(words)


def test_export_karaoke_vtt_parameter_validation():
    w = WordToken(id="w1", text="Test", normalized="test", start=0.0, end=1.0, confidence=0.9)
    with pytest.raises(ValueError, match="words must be a list"):
        export_karaoke_vtt("not a list")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="WordToken"):
        export_karaoke_vtt(["not", "wordtokens"])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="max_line_words"):
        export_karaoke_vtt([w], max_line_words=0)
    with pytest.raises(ValueError, match="max_line_chars"):
        export_karaoke_vtt([w], max_line_chars=0)
    with pytest.raises(ValueError, match="max_pause_break"):
        export_karaoke_vtt([w], max_pause_break=0.0)


# -----------------------------------------------------------------------------
# export_jsonld tests
# -----------------------------------------------------------------------------


def test_export_jsonld_structure_and_types():
    words = [
        WordToken(id="w1", text="Hello", normalized="hello", start=0.5, end=1.25, confidence=0.95),
        WordToken(id="w2", text="world", normalized="world", start=1.3, end=2.0, confidence=0.90),
    ]
    data = export_jsonld(words, audio_duration=5.5, media_urn="urn:uuid:12345", language="en-US")
    assert data["@context"] == "https://schema.org"
    assert data["@type"] == "VideoObject"
    assert data["@id"] == "urn:uuid:12345"
    assert data["name"] == "Speech alignment timeline"
    assert data["inLanguage"] == "en-US"
    assert data["duration"] == "PT5.500S"
    assert len(data["hasPart"]) == 2

    clip1 = data["hasPart"][0]
    assert clip1["@type"] == "Clip"
    assert clip1["@id"] == "urn:uuid:12345#word-w1"
    assert clip1["name"] == "Hello"
    assert clip1["startOffset"] == 0.5
    assert clip1["endOffset"] == 1.25
    assert clip1["inLanguage"] == "en-US"


def test_export_jsonld_empty_words():
    data = export_jsonld([], audio_duration=0.0, media_urn="media.wav")
    assert data["duration"] == "PT0.000S"
    assert data["hasPart"] == []


def test_export_jsonld_validation():
    w = WordToken(id="w1", text="Hi", normalized="hi", start=0.0, end=1.0, confidence=0.9)
    with pytest.raises(ValueError, match="audio_duration"):
        export_jsonld([w], audio_duration=-1.0, media_urn="test")
    with pytest.raises(ValueError, match="media_urn"):
        export_jsonld([w], audio_duration=1.0, media_urn="")
    with pytest.raises(ValueError, match="language"):
        export_jsonld([w], audio_duration=1.0, media_urn="test", language="")
    with pytest.raises(ValueError, match="words must be a list"):
        export_jsonld("invalid", audio_duration=1.0, media_urn="test")  # type: ignore[arg-type]


# -----------------------------------------------------------------------------
# export_raw_alignment tests
# -----------------------------------------------------------------------------


def test_export_raw_alignment_metrics_and_hierarchy():
    phonemes = [
        PhonemeCue(phoneme="HH", start=0.1, end=0.3, confidence=0.9),
        PhonemeCue(phoneme="AH", start=0.3, end=0.5, confidence=0.8),
    ]
    words = [
        WordToken(
            id="w1",
            text="Huh",
            normalized="huh",
            start=0.1,
            end=0.5,
            confidence=0.85,
            char_start=0,
            char_end=3,
            phonemes=phonemes,
        ),
        WordToken(
            id="w2",
            text="what",
            normalized="what",
            start=1.0,
            end=1.5,
            confidence=0.95,
            char_start=4,
            char_end=8,
            phonemes=[],
        ),
    ]
    result = export_raw_alignment(
        words=words,
        audio_path="audio/test.wav",
        alignment_method="mfa",
        metrics={"custom_metric": 42},
    )

    assert result["schema_version"] == 1
    assert result["audio_file"] == "test.wav"
    assert result["audio_path"] == "audio/test.wav"
    assert result["alignment_method"] == "mfa"

    summary = result["summary"]
    assert summary["total_words"] == 2
    assert summary["total_phonemes"] == 2
    assert summary["mean_word_confidence"] == round((0.85 + 0.95) / 2, 4)
    assert summary["mean_phoneme_confidence"] == round((0.9 + 0.8) / 2, 4)
    # speech: (0.5 - 0.1) + (1.5 - 1.0) = 0.4 + 0.5 = 0.9
    assert summary["speech_duration_seconds"] == 0.9
    # pause: 1.0 - 0.5 = 0.5
    assert summary["pause_duration_seconds"] == 0.5
    assert summary["speech_to_pause_ratio"] == round(0.9 / 0.5, 4)
    assert summary["custom_metric"] == 42

    assert len(result["words"]) == 2
    assert result["words"][0]["id"] == "w1"
    assert result["words"][0]["char_start"] == 0
    assert len(result["words"][0]["phonemes"]) == 2
    assert result["words"][0]["phonemes"][0]["phoneme"] == "HH"


def test_export_raw_alignment_empty():
    result = export_raw_alignment(
        words=[],
        audio_path=Path("sample.wav"),
        alignment_method="ctc",
    )
    assert result["summary"]["total_words"] == 0
    assert result["summary"]["total_phonemes"] == 0
    assert result["summary"]["mean_word_confidence"] == 0.0
    assert result["summary"]["mean_phoneme_confidence"] == 0.0
    assert result["summary"]["speech_duration_seconds"] == 0.0
    assert result["summary"]["pause_duration_seconds"] == 0.0
    assert result["summary"]["speech_to_pause_ratio"] == 0.0
    assert result["words"] == []


def test_export_raw_alignment_validation():
    with pytest.raises(ValueError, match="words must be a list"):
        export_raw_alignment("bad", "test.wav", "ctc")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="audio_path"):
        export_raw_alignment([], 123, "ctc")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="alignment_method"):
        export_raw_alignment([], "test.wav", "")
    with pytest.raises(ValueError, match="metrics"):
        export_raw_alignment([], "test.wav", "ctc", metrics="not-a-dict")  # type: ignore[arg-type]


# -----------------------------------------------------------------------------
# generate_manifest tests
# -----------------------------------------------------------------------------


def test_generate_manifest_success(tmp_path: Path):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"RIFF dummy wav audio content 12345")

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    vtt_text = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.000\nHello\n"
    (output_dir / "subtitles.vtt").write_text(vtt_text, encoding="utf-8")
    (output_dir / "timeline.jsonld").write_text(
        '{"@context": "https://schema.org"}', encoding="utf-8"
    )
    (output_dir / "alignment_raw.json").write_text('{"schema_version": 1}', encoding="utf-8")

    words = [
        WordToken(id="w1", text="Hello", normalized="hello", start=1.0, end=2.0, confidence=0.99)
    ]
    metrics = {"rtf": 0.05, "duration": 2.0}
    config = Config(band_seconds=1.0)

    manifest = generate_manifest(
        input_audio_path=audio_path,
        output_dir=output_dir,
        words=words,
        metrics=metrics,
        config=config,
    )

    manifest_file = output_dir / "manifest.json"
    assert manifest_file.is_file()
    saved = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert saved == manifest

    assert manifest["schema_version"] == 1
    assert manifest["tool"]["name"] == "local-subtitle-workbench"
    assert manifest["inputs"]["audio"]["filename"] == "audio.wav"
    assert manifest["inputs"]["audio"]["sha256"] == sha256(audio_path)
    assert manifest["outputs"]["subtitles.vtt"]["sha256"] == sha256(output_dir / "subtitles.vtt")
    assert manifest["outputs"]["timeline.jsonld"]["sha256"] == sha256(
        output_dir / "timeline.jsonld"
    )
    assert manifest["outputs"]["alignment_raw.json"]["sha256"] == sha256(
        output_dir / "alignment_raw.json"
    )
    assert manifest["config"]["band_seconds"] == 1.0
    assert manifest["metrics"]["rtf"] == 0.05
    assert len(manifest["limitations"]) == 3
    assert len(manifest["code"]["source_sha256"]) == 64


def test_generate_manifest_missing_input_audio(tmp_path: Path):
    audio_path = tmp_path / "nonexistent.wav"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "subtitles.vtt").write_text("vtt")
    (output_dir / "timeline.jsonld").write_text("jsonld")
    (output_dir / "alignment_raw.json").write_text("raw")

    with pytest.raises(FileNotFoundError, match="Input audio file not found"):
        generate_manifest(audio_path, output_dir, [], {})


def test_generate_manifest_missing_output_file(tmp_path: Path):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio content")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "subtitles.vtt").write_text("vtt")
    # Missing timeline.jsonld and alignment_raw.json

    with pytest.raises(FileNotFoundError, match="Expected generated output file not found"):
        generate_manifest(audio_path, output_dir, [], {})


# -----------------------------------------------------------------------------
# provenance tests
# -----------------------------------------------------------------------------


def test_sha256_computation(tmp_path: Path):
    f = tmp_path / "sample.txt"
    f.write_text("hello world", encoding="utf-8")
    import hashlib

    expected = hashlib.sha256(b"hello world").hexdigest()
    assert sha256(f) == expected
    assert sha256(str(f)) == expected


def test_code_provenance():
    prov = code_provenance()
    assert isinstance(prov, dict)
    assert "source_sha256" in prov
    assert len(prov["source_sha256"]) == 64
    assert "git_revision" in prov
    assert "git_worktree_dirty" in prov
