"""Strict PCM WAV input and deterministic feature extraction."""

import struct
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


def validate_wav(path: Path | str, sample_rate: int = 16000) -> None:
    """Accept uncompressed mono PCM16 WAV at specified rate; reject unsupported media."""
    if not isinstance(path, (str, Path)):
        raise TypeError(f"path must be a str or Path, got {type(path).__name__}")
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        with wave.open(str(path), "rb") as wav:
            if (
                wav.getnchannels() != 1
                or wav.getsampwidth() != 2
                or wav.getcomptype() != "NONE"
                or wav.getframerate() != sample_rate
            ):
                raise ValueError(f"audio must be uncompressed mono PCM16 WAV at {sample_rate} Hz")
            count = wav.getnframes()
            if count <= 0:
                raise ValueError("audio file contains no audio frames")
            # Verify EOF integrity using chunked reads to avoid allocating multi-hundred MBs
            bytes_to_read = 2 * count
            bytes_read = 0
            chunk_size = 65536
            while bytes_read < bytes_to_read:
                to_read_frames = min(chunk_size // 2, count - (bytes_read // 2))
                chunk = wav.readframes(to_read_frames)
                if not chunk:
                    break
                bytes_read += len(chunk)
            if bytes_read != bytes_to_read:
                raise ValueError("WAV data is truncated")
    except (wave.Error, EOFError, RuntimeError, struct.error) as err:
        raise ValueError(f"Corrupt or invalid WAV file: {err}") from err


def load_wav(path: Path, config: Config) -> Audio:
    """Accept PCM16 mono 16 kHz; reject unsupported media before allocation."""
    validate_wav(path, config.sample_rate)
    with wave.open(str(path), "rb") as wav:
        count = wav.getnframes()
        hop = round(config.hop_seconds * config.sample_rate)
        if count < round(config.window_seconds * config.sample_rate):
            raise ValueError("audio must contain at least one feature window")
        if (count + hop - 1) // hop > config.max_frames:
            raise ValueError("audio exceeds configured max_frames; use a shorter segment")
        raw = wav.readframes(count)
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


def slice_wav(
    source_path: Path | str,
    target_path: Path | str,
    start_sec: float,
    end_sec: float,
) -> None:
    """Extract an audio slice [start_sec, end_sec] from a mono PCM16 WAV into target_path."""
    source_path = Path(source_path)
    target_path = Path(target_path)
    validate_wav(source_path)
    with wave.open(str(source_path), "rb") as r:
        framerate = r.getframerate()
        nframes = r.getnframes()
        total_dur = nframes / framerate

        if start_sec >= total_dur:
            raise ValueError(
                f"start_sec ({start_sec}s) must be strictly less than "
                f"audio duration ({total_dur:.3f}s)"
            )
        if start_sec < 0.0:
            raise ValueError("start_sec must be non-negative")
        if end_sec <= start_sec:
            raise ValueError(
                f"end_sec ({end_sec}s) must be strictly greater than start_sec ({start_sec}s)"
            )

        start_frame = max(0, int(round(start_sec * framerate)))
        end_frame = min(nframes, int(round(end_sec * framerate)))
        if end_frame <= start_frame:
            end_frame = min(nframes, start_frame + int(round(0.01 * framerate)))

        r.setpos(start_frame)
        num_to_read = max(0, end_frame - start_frame)
        frames = r.readframes(num_to_read)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(frames)


def get_duration(path: Path | str) -> float:
    """Return the duration of a WAV file in seconds."""
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


__all__ = [
    "Audio",
    "extract_features",
    "get_duration",
    "load_wav",
    "slice_wav",
    "validate_wav",
]
