"""Shared test fixtures.

The reference pipeline always runs Silero-VAD and Whisper (also when a transcript is
given, because Whisper supplies the anchors). Unit tests must never download or load
real neural models, so pipeline-level model entry points are replaced by small,
deterministic fakes here. Tests that exercise the real ASR/VAD code import it from
``subtitle_workbench.asr`` directly and are unaffected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from subtitle_workbench.audio import get_duration
from subtitle_workbench.models import ASRSegment, WordToken


class FakeWhisperTranscriber:
    """Deterministic stand-in for WhisperTranscriber used by pipeline tests."""

    instances: list[FakeWhisperTranscriber] = []

    def __init__(self, *args, **kwargs) -> None:
        self.model_size_or_path = "fake-whisper"
        self.device = "cpu"
        self.compute_type = "int8"
        self.transcribe_calls = 0
        self.unload_calls = 0
        FakeWhisperTranscriber.instances.append(self)

    def transcribe(self, audio_path: Path | str, **kwargs) -> list[ASRSegment]:
        self.transcribe_calls += 1
        duration = get_duration(audio_path)
        end = round(max(0.02, duration * 0.9), 4)
        start = round(min(0.05, end / 4), 4)
        word = WordToken(
            id="seg_0_w_0",
            text="speech",
            normalized="speech",
            start=start,
            end=end,
            confidence=0.9,
        )
        return [ASRSegment(id="seg_0", start=start, end=end, text="speech", words=[word])]

    def unload(self) -> None:
        self.unload_calls += 1


def fake_vad_silences(*args, **kwargs) -> list[tuple[float, float]]:
    return []


@pytest.fixture(autouse=True)
def _no_real_models_in_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeWhisperTranscriber.instances = []
    monkeypatch.setattr("subtitle_workbench.pipeline.WhisperTranscriber", FakeWhisperTranscriber)
    monkeypatch.setattr("subtitle_workbench.pipeline.extract_vad_silences", fake_vad_silences)
