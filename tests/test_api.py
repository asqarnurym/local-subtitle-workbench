"""Unit and integration tests for FastAPI alignment microservice."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from subtitle_workbench import __version__
from subtitle_workbench.api import app

client = TestClient(app)


def _make_dummy_wav(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Create a valid in-memory PCM WAV header and silent audio."""
    import struct

    num_samples = int(duration_sec * sample_rate)
    data_size = num_samples * 2  # 16-bit = 2 bytes
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        data_size + 36,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM format
        1,  # mono
        sample_rate,
        sample_rate * 2,
        2,  # block align
        16,  # bits per sample
        b"data",
        data_size,
    )
    return header + (b"\x00" * data_size)


def test_api_health_check() -> None:
    """Verify GET /health returns 200 and status info."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "subtitle-workbench"
    assert data["version"] == __version__


def test_api_service_info() -> None:
    """Verify GET /info returns supported engines and constraints."""
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert "auto" in data["supported_engines"]
    assert "mfa" in data["supported_engines"]
    assert "ctc" in data["supported_engines"]
    assert data["constraints"]["max_chunk_sec"] == 30.0


def test_api_align_invalid_engine() -> None:
    """Verify POST /align-speech rejects unsupported engine with 422."""
    wav_bytes = _make_dummy_wav(1.0)
    response = client.post(
        "/align-speech",
        files={"audio": ("test.wav", io.BytesIO(wav_bytes), "audio/wav")},
        data={"engine": "invalid_engine_name"},
    )
    assert response.status_code == 422
    assert "input should be 'auto', 'mfa' or 'ctc'" in response.text.lower()


def test_api_align_negative_parameters() -> None:
    """Verify POST /align-speech rejects negative timing parameters with 400."""
    wav_bytes = _make_dummy_wav(1.0)
    response = client.post(
        "/align-speech",
        files={"audio": ("test.wav", io.BytesIO(wav_bytes), "audio/wav")},
        data={"max_chunk_sec": -10.0},
    )
    assert response.status_code == 400
    assert "Timing parameters must be strictly positive" in response.json()["detail"]


def test_api_align_corrupt_audio() -> None:
    """Verify POST /align-speech rejects non-WAV bytes with 400."""
    corrupt_bytes = b"NOT_A_WAV_HEADER_DATA"
    response = client.post(
        "/align-speech",
        files={"audio": ("corrupt.wav", io.BytesIO(corrupt_bytes), "audio/wav")},
        data={"engine": "auto"},
    )
    assert response.status_code == 400
    assert "Audio processing error" in response.json()["detail"]


@patch("subtitle_workbench.api.run_speech_pipeline")
def test_api_align_success_mocked(mock_pipeline: MagicMock, tmp_path: Path) -> None:
    """Verify POST /align-speech handles pipeline execution and returns formatted responses."""

    def mock_run(audio_path, output_dir, **kwargs):
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        vtt_text = "WEBVTT\n\n00:00.000 --> 00:01.000\nHello"
        jsonld_data = {"@context": "https://schema.org", "type": "MediaClip"}
        raw_data = [{"word": "Hello", "start": 0.0, "end": 1.0}]

        (out_p / "subtitles.vtt").write_text(vtt_text, encoding="utf-8")
        (out_p / "timeline.jsonld").write_text(json.dumps(jsonld_data), encoding="utf-8")
        (out_p / "alignment_raw.json").write_text(json.dumps(raw_data), encoding="utf-8")
        return {"pipeline": {"engine": "ctc"}, "metrics": {"duration": 1.0}}

    mock_pipeline.side_effect = mock_run

    wav_bytes = _make_dummy_wav(1.0)
    response = client.post(
        "/align-speech",
        files={"audio": ("lecture.wav", io.BytesIO(wav_bytes), "audio/wav")},
        data={"transcript": "Hello", "engine": "auto"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "lecture.wav"
    assert "WEBVTT" in data["subtitles_vtt"]
    assert data["timeline_jsonld"]["type"] == "MediaClip"
    assert len(data["alignment_raw"]) == 1
    assert data["alignment_raw"][0]["word"] == "Hello"


@patch("subtitle_workbench.api.run_speech_pipeline")
def test_api_internal_server_error(mock_pipeline: MagicMock) -> None:
    """Verify POST /align-speech handles unexpected pipeline crash with 500."""
    mock_pipeline.side_effect = RuntimeError("Fatal model crash")

    wav_bytes = _make_dummy_wav(1.0)
    response = client.post(
        "/align-speech",
        files={"audio": ("crash.wav", io.BytesIO(wav_bytes), "audio/wav")},
        data={"engine": "auto"},
    )
    assert response.status_code == 500
    assert "Internal alignment error" in response.json()["detail"]
