"""Adversarial challenge test harness for Milestone 1 Increment 5.

Verifies:
- export_jsonld: schema validity, field types, duration format, media URN quoting
- export_raw_alignment: metrics calculations, hierarchy, division by zero safeguards
- generate_manifest: SHA-256 digest consistency, missing files handling, code provenance
- stress testing and property-based boundary checks
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from subtitle_workbench.export import (
    export_jsonld,
    export_raw_alignment,
    generate_manifest,
)
from subtitle_workbench.models import PhonemeCue, WordToken
from subtitle_workbench.provenance import code_provenance, sha256

# -----------------------------------------------------------------------------
# 1. Adversarial Tests for export_jsonld
# -----------------------------------------------------------------------------


def test_jsonld_schema_validity_and_iso8601_duration():
    """Verify schema.org VideoObject structure and ISO 8601 duration regex."""
    words = [
        WordToken(id="w1", text="Hello", normalized="hello", start=0.0, end=0.8, confidence=0.95),
        WordToken(id="w2", text="world", normalized="world", start=1.0, end=1.75, confidence=0.90),
    ]

    durations_to_test = [
        (0.0, "PT0.000S"),
        (0.001, "PT0.001S"),
        (10.5, "PT10.500S"),
        (59.999, "PT59.999S"),
        (3600.123, "PT3600.123S"),
        (86400.0, "PT86400.000S"),
    ]

    iso_regex = re.compile(r"^PT\d+\.\d{3}S$")

    for duration_val, expected_str in durations_to_test:
        doc = export_jsonld(words, audio_duration=duration_val, media_urn="urn:lecture:001")
        assert doc["@context"] == "https://schema.org"
        assert doc["@type"] == "VideoObject"
        assert doc["duration"] == expected_str
        assert iso_regex.match(doc["duration"]) is not None


def test_jsonld_clip_parts_field_types_and_invariants():
    """Verify Clip parts field types, offset bounds, and JSON serializability."""
    words = [
        WordToken(
            id="w_0",
            text="Intro",
            normalized="intro",
            start=0.1234567,
            end=0.654321,
            confidence=0.88,
        ),
        WordToken(
            id="w_1",
            text="Speech",
            normalized="speech",
            start=0.7,
            end=1.5,
            confidence=0.92,
        ),
    ]

    doc = export_jsonld(words, audio_duration=2.0, media_urn="urn:test:media", language="en-US")
    parts = doc["hasPart"]
    assert isinstance(parts, list)
    assert len(parts) == 2

    for part, w in zip(parts, words, strict=True):
        assert part["@type"] == "Clip"
        assert part["@id"] == f"urn:test:media#word-{w.id}"
        assert part["name"] == w.text
        assert isinstance(part["startOffset"], (float, int))
        assert isinstance(part["endOffset"], (float, int))
        assert part["startOffset"] == round(w.start, 6)
        assert part["endOffset"] == round(w.end, 6)
        assert part["startOffset"] < part["endOffset"]
        assert part["inLanguage"] == "en-US"

    # Entire document must be valid JSON
    serialized = json.dumps(doc)
    deserialized = json.loads(serialized)
    assert deserialized == doc


def test_jsonld_media_urn_quoting():
    """Verify URI quoting behavior for media URN with spaces and characters."""
    words = [WordToken(id="w1", text="A", normalized="a", start=0.0, end=1.0, confidence=0.9)]

    # Media URN with spaces and query parameters
    doc = export_jsonld(
        words,
        audio_duration=2.0,
        media_urn="urn:my lectures/session 1.mp4",
        language="en",
    )
    assert doc["@id"] == "urn:my%20lectures/session%201.mp4"
    assert doc["hasPart"][0]["@id"] == "urn:my%20lectures/session%201.mp4#word-w1"


def test_jsonld_empty_words_boundary():
    """Empty words list must return empty hasPart without errors."""
    doc = export_jsonld([], audio_duration=0.0, media_urn="urn:empty")
    assert doc["hasPart"] == []
    assert doc["duration"] == "PT0.000S"
    assert doc["@id"] == "urn:empty"


@pytest.mark.parametrize(
    "bad_duration",
    [-0.001, -100.0, float("nan"), float("inf"), float("-inf"), True, False],
)
def test_jsonld_rejects_invalid_durations(bad_duration):
    """Verify strict rejection of invalid duration values."""
    w = WordToken(id="w1", text="A", normalized="a", start=0.0, end=1.0, confidence=0.9)
    with pytest.raises(ValueError):
        export_jsonld([w], audio_duration=bad_duration, media_urn="urn:test")


@pytest.mark.parametrize("bad_urn", ["", None, 12345, []])
def test_jsonld_rejects_invalid_media_urn(bad_urn):
    """Verify strict rejection of invalid media_urn."""
    w = WordToken(id="w1", text="A", normalized="a", start=0.0, end=1.0, confidence=0.9)
    with pytest.raises(ValueError):
        export_jsonld([w], audio_duration=1.0, media_urn=bad_urn)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_lang", ["", None, 12345])
def test_jsonld_rejects_invalid_language(bad_lang):
    """Verify strict rejection of invalid language."""
    w = WordToken(id="w1", text="A", normalized="a", start=0.0, end=1.0, confidence=0.9)
    with pytest.raises(ValueError):
        export_jsonld([w], audio_duration=1.0, media_urn="urn:test", language=bad_lang)  # type: ignore[arg-type]


# -----------------------------------------------------------------------------
# 2. Adversarial Tests for export_raw_alignment
# -----------------------------------------------------------------------------


def test_raw_alignment_division_by_zero_safeguards():
    """Adversarially verify division by zero protections in summary metrics.

    Scenarios:
    1. Zero words: empty list -> total_words=0, confidences=0.0, ratio=0.0
    2. Single word, zero phonemes: total_phonemes=0 -> confidence=0.0, pause=0.0, ratio=0.0
    3. Multiple contiguous words with zero pause: pause_duration_seconds=0.0 -> ratio=0.0
    4. Overlapping words: pause duration clamped to 0.0 -> ratio=0.0
    """
    # Scenario 1: Zero words
    res1 = export_raw_alignment([], "audio.wav", "ctc")
    s1 = res1["summary"]
    assert s1["total_words"] == 0
    assert s1["total_phonemes"] == 0
    assert s1["mean_word_confidence"] == 0.0
    assert s1["mean_phoneme_confidence"] == 0.0
    assert s1["speech_duration_seconds"] == 0.0
    assert s1["pause_duration_seconds"] == 0.0
    assert s1["speech_to_pause_ratio"] == 0.0

    # Scenario 2: Single word, zero phonemes
    w_single = WordToken(
        id="w1",
        text="Solitary",
        normalized="solitary",
        start=1.0,
        end=2.5,
        confidence=0.8,
        phonemes=[],
    )
    res2 = export_raw_alignment([w_single], "audio.wav", "mfa")
    s2 = res2["summary"]
    assert s2["total_words"] == 1
    assert s2["total_phonemes"] == 0
    assert s2["mean_word_confidence"] == 0.8
    assert s2["mean_phoneme_confidence"] == 0.0
    assert s2["speech_duration_seconds"] == 1.5
    assert s2["pause_duration_seconds"] == 0.0
    assert s2["speech_to_pause_ratio"] == 0.0

    # Scenario 3: Multiple contiguous words with zero pauses
    w_contig = [
        WordToken(id="w1", text="One", normalized="one", start=0.0, end=1.0, confidence=0.9),
        WordToken(id="w2", text="Two", normalized="two", start=1.0, end=2.0, confidence=0.9),
        WordToken(id="w3", text="Three", normalized="three", start=2.0, end=3.0, confidence=0.9),
    ]
    res3 = export_raw_alignment(w_contig, "audio.wav", "mfa")
    s3 = res3["summary"]
    assert s3["total_words"] == 3
    assert s3["speech_duration_seconds"] == 3.0
    assert s3["pause_duration_seconds"] == 0.0
    assert s3["speech_to_pause_ratio"] == 0.0

    # Scenario 4: Overlapping words (start[i+1] < end[i])
    w_overlap = [
        WordToken(id="w1", text="Alpha", normalized="alpha", start=0.0, end=1.5, confidence=0.9),
        WordToken(id="w2", text="Beta", normalized="beta", start=1.0, end=2.5, confidence=0.9),
    ]
    res4 = export_raw_alignment(w_overlap, "audio.wav", "mfa")
    s4 = res4["summary"]
    assert s4["pause_duration_seconds"] == 0.0
    assert s4["speech_to_pause_ratio"] == 0.0


def test_raw_alignment_phoneme_confidence_and_hierarchy():
    """Verify phoneme-level hierarchy and weighted confidence averaging."""
    p1 = PhonemeCue(phoneme="W", start=0.0, end=0.2, confidence=0.8)
    p2 = PhonemeCue(phoneme="AH", start=0.2, end=0.5, confidence=0.9)
    p3 = PhonemeCue(phoneme="N", start=0.5, end=0.7, confidence=1.0)
    w1 = WordToken(
        id="w1",
        text="One",
        normalized="one",
        start=0.0,
        end=0.7,
        confidence=0.9,
        phonemes=[p1, p2, p3],
    )

    # Second word without phonemes
    w2 = WordToken(
        id="w2",
        text="Two",
        normalized="two",
        start=1.0,
        end=1.8,
        confidence=0.7,
        phonemes=[],
    )

    res = export_raw_alignment([w1, w2], "test.wav", "mfa")
    summary = res["summary"]
    assert summary["total_words"] == 2
    assert summary["total_phonemes"] == 3
    assert summary["mean_word_confidence"] == round((0.9 + 0.7) / 2, 4)
    assert summary["mean_phoneme_confidence"] == round((0.8 + 0.9 + 1.0) / 3, 4)
    # pause: 1.0 - 0.7 = 0.3
    assert summary["pause_duration_seconds"] == 0.3
    # speech: 0.7 + 0.8 = 1.5
    assert summary["speech_duration_seconds"] == 1.5
    assert summary["speech_to_pause_ratio"] == round(1.5 / 0.3, 4)

    # Validate full JSON serialization
    serialized = json.dumps(res)
    assert json.loads(serialized) == res


def test_raw_alignment_stress_10000_words():
    """Stress test export_raw_alignment with 10,000 words and 30,000 phonemes."""
    words = []
    t = 0.0
    for i in range(10000):
        p_list = [
            PhonemeCue(phoneme="A", start=round(t, 4), end=round(t + 0.05, 4), confidence=0.9),
            PhonemeCue(
                phoneme="B",
                start=round(t + 0.05, 4),
                end=round(t + 0.10, 4),
                confidence=0.95,
            ),
            PhonemeCue(
                phoneme="C",
                start=round(t + 0.10, 4),
                end=round(t + 0.15, 4),
                confidence=0.85,
            ),
        ]
        words.append(
            WordToken(
                id=f"w_{i}",
                text="abc",
                normalized="abc",
                start=round(t, 4),
                end=round(t + 0.15, 4),
                confidence=0.90,
                phonemes=p_list,
            )
        )
        t += 0.20  # 0.05s pause between words

    res = export_raw_alignment(words, "stress.wav", "ctc")
    assert res["summary"]["total_words"] == 10000
    assert res["summary"]["total_phonemes"] == 30000
    assert res["summary"]["mean_word_confidence"] == 0.9
    assert res["summary"]["mean_phoneme_confidence"] == 0.9
    assert len(res["words"]) == 10000


# -----------------------------------------------------------------------------
# 3. Adversarial Tests for generate_manifest & provenance
# -----------------------------------------------------------------------------


def test_generate_manifest_sha256_exact_consistency(tmp_path: Path):
    """Verify manifest SHA-256 digests strictly match multi-block file contents."""
    audio_path = tmp_path / "long_audio.wav"
    # Create 150 KB dummy file to test multi-block 64KB hashing
    chunk = b"A" * 65536 + b"B" * 65536 + b"C" * 20000
    audio_path.write_bytes(chunk)
    expected_audio_hash = hashlib.sha256(chunk).hexdigest()

    output_dir = tmp_path / "run_out"
    output_dir.mkdir()

    vtt_bytes = b"WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.000\nTest\n"
    jsonld_bytes = b'{"@context": "https://schema.org", "@type": "VideoObject"}'
    raw_bytes = b'{"schema_version": 1, "words": []}'

    (output_dir / "subtitles.vtt").write_bytes(vtt_bytes)
    (output_dir / "timeline.jsonld").write_bytes(jsonld_bytes)
    (output_dir / "alignment_raw.json").write_bytes(raw_bytes)

    words = [WordToken(id="w1", text="Test", normalized="test", start=0.0, end=1.0, confidence=0.9)]
    metrics = {"rtf": 0.04}

    manifest = generate_manifest(
        input_audio_path=audio_path,
        output_dir=output_dir,
        words=words,
        metrics=metrics,
    )

    # Check input hash
    assert manifest["inputs"]["audio"]["sha256"] == expected_audio_hash
    assert sha256(audio_path) == expected_audio_hash

    # Check output hashes
    vtt_sha = hashlib.sha256(vtt_bytes).hexdigest()
    jsonld_sha = hashlib.sha256(jsonld_bytes).hexdigest()
    raw_sha = hashlib.sha256(raw_bytes).hexdigest()
    assert manifest["outputs"]["subtitles.vtt"]["sha256"] == vtt_sha
    assert manifest["outputs"]["timeline.jsonld"]["sha256"] == jsonld_sha
    assert manifest["outputs"]["alignment_raw.json"]["sha256"] == raw_sha

    # Verify manifest.json on disk
    manifest_disk = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_disk == manifest


def test_generate_manifest_missing_input_wav_cases(tmp_path: Path):
    """Verify FileNotFoundError when input audio path does not exist or is a directory."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "subtitles.vtt").write_text("vtt")
    (out_dir / "timeline.jsonld").write_text("jsonld")
    (out_dir / "alignment_raw.json").write_text("raw")

    # Case 1: Non-existent file
    with pytest.raises(FileNotFoundError, match="Input audio file not found"):
        generate_manifest(tmp_path / "ghost.wav", out_dir, [], {})

    # Case 2: Path is a directory
    dir_as_wav = tmp_path / "fake_dir_wav"
    dir_as_wav.mkdir()
    with pytest.raises(FileNotFoundError, match="Input audio file not found"):
        generate_manifest(dir_as_wav, out_dir, [], {})


@pytest.mark.parametrize("missing_file", ["subtitles.vtt", "timeline.jsonld", "alignment_raw.json"])
def test_generate_manifest_missing_each_output_artifact(tmp_path: Path, missing_file: str):
    """Verify FileNotFoundError if any single required output artifact is missing."""
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    artifacts = {
        "subtitles.vtt": "vtt",
        "timeline.jsonld": "jsonld",
        "alignment_raw.json": "raw",
    }
    for fname, content in artifacts.items():
        if fname != missing_file:
            (out_dir / fname).write_text(content)

    with pytest.raises(FileNotFoundError, match="Expected generated output file not found"):
        generate_manifest(audio_path, out_dir, [], {})


def test_generate_manifest_config_dataclass_and_dict(tmp_path: Path):
    """Verify dataclass, dict, and None configs in manifest serialization."""
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "subtitles.vtt").write_text("vtt")
    (out_dir / "timeline.jsonld").write_text("jsonld")
    (out_dir / "alignment_raw.json").write_text("raw")

    @dataclass
    class CustomConfig:
        engine: str
        chunk_len: float

    cfg_obj = CustomConfig(engine="ctc", chunk_len=30.0)
    m1 = generate_manifest(audio_path, out_dir, [], {}, config=cfg_obj)
    assert m1["config"] == {"engine": "ctc", "chunk_len": 30.0}

    m2 = generate_manifest(audio_path, out_dir, [], {}, config={"key": "val"})
    assert m2["config"] == {"key": "val"}

    m3 = generate_manifest(audio_path, out_dir, [], {}, config=None)
    assert m3["config"] == {}


def test_code_provenance_determinism_and_structure():
    """Verify code_provenance structure, determinism, and git integration."""
    p1 = code_provenance()
    p2 = code_provenance()

    assert p1["source_sha256"] == p2["source_sha256"]
    assert len(p1["source_sha256"]) == 64
    assert all(c in "0123456789abcdef" for c in p1["source_sha256"])

    if p1["git_revision"] is not None:
        assert len(p1["git_revision"]) == 40
        assert all(c in "0123456789abcdef" for c in p1["git_revision"])
    assert isinstance(p1["git_worktree_dirty"], (bool, type(None)))
