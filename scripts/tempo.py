"""Tempo change without pitch change (S2): phase vocoder with identity phase locking.

Analysis frames are taken at input sample ``round(k * hop * rate)`` and written at output
sample ``k * hop``, so the time map is linear (t_out = t_in / rate) up to half a sample.
That keeps reference boundaries exact under the same map, unlike WSOLA, whose frame
positions drift by up to its tolerance. Identity phase locking (Laroche & Dolson, 1999)
keeps each non-peak bin's phase relative to its nearest spectral peak, which reduces the
"phasy" sound of the plain vocoder. numpy only; no new dependency.
"""

from __future__ import annotations

import numpy as np

N_FFT = 512  # 32 ms at 16 kHz
HOP = 128  # synthesis hop (75 % overlap)


def _peaks(mag: np.ndarray) -> np.ndarray:
    """Index of the nearest local magnitude maximum for every bin."""
    is_peak = np.zeros(mag.shape, dtype=bool)
    is_peak[1:-1] = (mag[1:-1] > mag[:-2]) & (mag[1:-1] >= mag[2:])
    peaks = np.flatnonzero(is_peak)
    if peaks.size == 0:
        return np.arange(mag.size)
    bins = np.arange(mag.size)
    pos = np.clip(np.searchsorted(peaks, bins), 1, peaks.size - 1) if peaks.size > 1 else None
    if pos is None:
        return np.full(mag.size, peaks[0])
    left, right = peaks[pos - 1], peaks[pos]
    return np.where(bins - left <= right - bins, left, right)


def time_stretch(x: np.ndarray, rate: float) -> np.ndarray:
    """``x`` played ``rate`` times faster (rate > 1 shortens), same pitch; float in, float out."""
    if rate <= 0:
        raise ValueError("rate must be positive")
    x = np.asarray(x, dtype=np.float64)
    n_out = int(round(len(x) / rate))
    win = np.hanning(N_FFT + 1)[:-1]
    pad = np.concatenate([np.zeros(N_FFT), x, np.zeros(N_FFT + int(np.ceil(HOP * rate)) + 1)])
    omega = 2 * np.pi * np.arange(N_FFT // 2 + 1) / N_FFT
    n_frames = n_out // HOP + N_FFT // HOP + 2
    y = np.zeros(n_frames * HOP + N_FFT)
    norm = np.zeros_like(y)
    prev_phase = None
    phase = None
    prev_pos = 0
    for k in range(n_frames):
        pos = int(round(k * HOP * rate))
        if pos + N_FFT > len(pad):
            break
        spec = np.fft.rfft(pad[pos : pos + N_FFT] * win)
        mag, ph = np.abs(spec), np.angle(spec)
        if prev_phase is None:
            phase = ph.copy()
        else:
            ha = pos - prev_pos
            dphi = ph - prev_phase - omega * ha
            dphi -= 2 * np.pi * np.round(dphi / (2 * np.pi))
            inst = omega + dphi / max(ha, 1)
            peak_phase = phase + inst * HOP
            near = _peaks(mag)
            phase = peak_phase[near] + (ph - ph[near])
        prev_phase, prev_pos = ph, pos
        frame = np.fft.irfft(mag * np.exp(1j * phase), N_FFT) * win
        y[k * HOP : k * HOP + N_FFT] += frame
        norm[k * HOP : k * HOP + N_FFT] += win**2
    out = y / np.maximum(norm, 1e-8)
    return out[N_FFT : N_FFT + n_out]


def stretch_pcm16(frames: bytes, rate: float) -> bytes:
    """Mono PCM16 bytes in, mono PCM16 bytes out (clipped, rounded)."""
    x = np.frombuffer(frames, dtype="<i2").astype(np.float64)
    y = np.clip(np.round(time_stretch(x, rate)), -32768, 32767).astype("<i2")
    return y.tobytes()
