import copy
import wave

import numpy as np
import pytest

from subtitle_workbench.audio import load_wav
from subtitle_workbench.demo import write_wav
from subtitle_workbench.models import Config, validate_cues


def good_data():
    return {
        "language": "en",
        "cues": [
            {"id": "c1", "start": 0.1, "end": 0.4, "text": "First sentence."},
            {"id": "c2", "start": 0.5, "end": 0.8, "text": "Second sentence."},
        ],
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("start", float("nan")),
        ("start", True),
        ("end", float("inf")),
        ("start", -0.1),
        ("end", 1.1),
        ("end", 0.1),
        ("start", "0.1"),
        ("start", 10**1000),
        ("text", ""),
        ("text", "A\x00B"),
        ("text", "A\n\nB"),
        ("text", "\nHello"),
        ("text", "Hello\n"),
        ("text", "Hello\ud800"),
        ("id", "bad\nID"),
        ("id", "bad-->id"),
        ("id", ""),
    ],
)
def test_invalid_cue_fields(field, value):
    data = good_data()
    data["cues"][0][field] = value
    with pytest.raises(ValueError):
        validate_cues(data, 1.0)


def test_order_overlap_and_duplicate_ids():
    data = good_data()
    data["cues"].reverse()
    with pytest.raises(ValueError, match="ordered"):
        validate_cues(data, 1.0)
    data = good_data()
    data["cues"][1]["start"] = 0.3
    with pytest.raises(ValueError, match="overlapping"):
        validate_cues(data, 1.0)
    data = good_data()
    data["cues"][1]["id"] = "c1"
    with pytest.raises(ValueError, match="unique"):
        validate_cues(data, 1.0)


@pytest.mark.parametrize(
    "data", [[], {}, {"language": "ru", "cues": []}, {"language": "en", "cues": []}]
)
def test_shape_and_english_contract(data):
    with pytest.raises(ValueError):
        validate_cues(data, 1.0)


def test_missing_or_unknown_field_is_not_silently_ignored():
    data = good_data()
    other = copy.deepcopy(data)
    del data["cues"][0]["end"]
    other["cues"][0]["confidence"] = 0.8
    for invalid in (data, other):
        with pytest.raises(ValueError, match="exactly"):
            validate_cues(invalid, 1.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sample_rate": 8000},
        {"band_seconds": float("nan")},
        {"band_seconds": -1},
        {"max_cells": True},
        {"max_cells": 5_000_001},
        {"max_frames": 10001},
        {"window_seconds": 0.01, "hop_seconds": 0.02},
        {"spectral_weight": 2},
    ],
)
def test_configuration_bounds(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)


@pytest.mark.parametrize("rate,channels,width", [(8000, 1, 2), (16000, 2, 2), (16000, 1, 1)])
def test_unsupported_wav_format(tmp_path, rate, channels, width):
    path = tmp_path / "bad.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(b"\x01" * (rate * channels * width))
    with pytest.raises(ValueError, match="PCM16"):
        load_wav(path, Config())


@pytest.mark.parametrize("amplitude", [0.0, 0.00001])
def test_silent_and_very_quiet_inputs_are_rejected(tmp_path, amplitude):
    path = tmp_path / "quiet.wav"
    write_wav(path, np.ones(16000) * amplitude)
    with pytest.raises(ValueError, match="silent or too quiet"):
        load_wav(path, Config())


def test_frame_guard_runs_before_large_audio_read(tmp_path):
    path = tmp_path / "long.wav"
    write_wav(path, np.ones(16000) * 0.1)
    with pytest.raises(ValueError, match="max_frames"):
        load_wav(path, Config(max_frames=10))


def test_truncated_and_short_wav(tmp_path):
    path = tmp_path / "short.wav"
    write_wav(path, np.ones(100) * 0.1)
    with pytest.raises(ValueError, match="at least one feature window"):
        load_wav(path, Config())
    write_wav(path, np.ones(16000) * 0.1)
    path.write_bytes(path.read_bytes()[:-100])
    with pytest.raises(ValueError, match="truncated"):
        load_wav(path, Config())
