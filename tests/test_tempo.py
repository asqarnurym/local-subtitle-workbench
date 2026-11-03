"""Tests for the pitch-preserving tempo change used by S2 (scripts/tempo.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tempo import stretch_pcm16, time_stretch  # noqa: E402

SR = 16000


def _peak_hz(x: np.ndarray) -> float:
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return float(np.argmax(spec) * SR / len(x))


@pytest.mark.parametrize("rate", [0.8, 0.9, 1.1, 1.25])
def test_length_scales_and_pitch_is_kept(rate: float) -> None:
    t = np.arange(SR) / SR
    x = 0.5 * np.sin(2 * np.pi * 440 * t)
    y = time_stretch(x, rate)
    assert len(y) == round(SR / rate)
    assert abs(_peak_hz(y[1000:-1000]) - 440) < 3


def test_rate_one_is_near_identity() -> None:
    rng = np.random.default_rng(0)
    t = np.arange(SR) / SR
    x = (
        np.sin(2 * np.pi * 220 * t)
        + 0.5 * np.sin(2 * np.pi * 1330 * t)
        + 0.01 * rng.normal(size=SR)
    )
    y = time_stretch(x, 1.0)
    assert len(y) == len(x)
    assert np.corrcoef(x[600:-600], y[600:-600])[0, 1] > 0.99


def test_events_move_by_the_linear_time_map() -> None:
    # A click at 0.5 s must appear at 0.5 / rate s (within a few ms)
    x = np.zeros(SR)
    x[SR // 2 : SR // 2 + 40] = 1.0
    for rate in (0.8, 1.25):
        y = time_stretch(x, rate)
        energy = np.convolve(y**2, np.ones(64), "same")
        assert abs(np.argmax(energy) / SR - 0.5 / rate) < 0.008


def test_pcm16_round_trip_keeps_format() -> None:
    x = (8000 * np.sin(2 * np.pi * 300 * np.arange(SR) / SR)).astype("<i2").tobytes()
    out = stretch_pcm16(x, 1.25)
    assert len(out) == 2 * round(SR / 1.25)
