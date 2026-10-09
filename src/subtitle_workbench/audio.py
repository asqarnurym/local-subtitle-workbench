"""Strict PCM WAV input and deterministic feature extraction."""

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from .models import Config


@dataclass(frozen=True)
class Audio:
    samples: NDArray[np.float64]
    sample_rate: int

    @property
    def duration(self) -> float:
        return len(self.samples) / self.sample_rate


def load_wav(path: Path, config: Config) -> Audio:
    """Accept PCM16 mono 16 kHz; reject unsupported media before allocation."""
    with wave.open(str(path), "rb") as wav:
        if (
            wav.getnchannels() != 1
            or wav.getsampwidth() != 2
            or wav.getcomptype() != "NONE"
            or wav.getframerate() != config.sample_rate
        ):
            raise ValueError("audio must be uncompressed mono PCM16 WAV at 16000 Hz")
        count = wav.getnframes()
        hop = round(config.hop_seconds * config.sample_rate)
        if count < round(config.window_seconds * config.sample_rate):
            raise ValueError("audio must contain at least one feature window")
        if (count + hop - 1) // hop > config.max_frames:
            raise ValueError("audio exceeds configured max_frames; use a shorter segment")
        raw = wav.readframes(count)
        if len(raw) != 2 * count:
            raise ValueError("WAV data is truncated")
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if np.sqrt(np.mean(samples * samples)) < 1e-4:
        raise ValueError("audio is silent or too quiet for reliable alignment")
    return Audio(samples, config.sample_rate)


def extract_features(audio: Audio, config: Config) -> tuple[NDArray, NDArray]:
    """Return frame centres and [standardised log RMS, weighted centroid]."""
    hop = round(config.hop_seconds * audio.sample_rate)
    width = round(config.window_seconds * audio.sample_rate)
    centres = np.arange(0, len(audio.samples), hop, dtype=np.int64)
    energy = np.empty(len(centres))
    spectral = np.empty(len(centres))
    taper = np.hanning(width)
    frequencies = np.fft.rfftfreq(width, 1 / audio.sample_rate)
    padded = np.pad(audio.samples, (width // 2, width))
    for index, centre in enumerate(centres):
        frame = padded[centre : centre + width]
        energy[index] = np.log(max(float(np.sqrt(np.mean(frame * frame))), 1e-5))
        spectrum = np.abs(np.fft.rfft(frame * taper))
        spectral[index] = np.dot(spectrum, frequencies) / max(float(spectrum.sum()), 1e-12)
    scale = max(float(energy.std()), 0.1)
    rms = (energy - energy.mean()) / scale
    centroid = spectral / (audio.sample_rate / 2) * config.spectral_weight
    features = np.column_stack((rms, centroid))
    return centres / audio.sample_rate, features
