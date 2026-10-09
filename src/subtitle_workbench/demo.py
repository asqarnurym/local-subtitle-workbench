"""Deterministic synthetic test signals with an explicit timing oracle."""

import argparse
import json
import wave
from pathlib import Path

import numpy as np

from .models import finite_number


def write_wav(path: Path, samples: np.ndarray, sample_rate: int = 16000) -> None:
    pcm = np.clip(np.rint(samples * 32767), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def generate(output: Path, shift: float = 0.24, stretch: float = 1.08) -> dict:
    """Generate six amplitude/frequency bursts; this is not a speech corpus."""
    shift = finite_number(shift, "shift")
    stretch = finite_number(stretch, "stretch")
    if not 0 <= shift <= 1 or not 0.8 <= stretch <= 1.2:
        raise ValueError("demo requires shift in [0, 1] and stretch in [0.8, 1.2]")
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("demo directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    rate = 16000
    duration = 6.5
    t = np.arange(round(duration * rate)) / rate
    signal = np.zeros_like(t)
    intervals = [(0.60, 1.12), (1.42, 2.06), (2.48, 3.10), (3.42, 4.06), (4.38, 4.94), (5.30, 5.92)]
    cues = []
    for index, (start, end) in enumerate(intervals):
        mask = (t >= start) & (t < end)
        local = t[mask] - start
        envelope = np.sin(np.pi * local / (end - start)) ** 0.7
        modulation = 0.6 + 0.4 * np.sin(2 * np.pi * (3 + index) * local) ** 2
        carrier = np.sin(2 * np.pi * (220 + 91 * index) * local)
        signal[mask] = 0.5 * envelope * modulation * carrier
        cues.append(
            {
                "id": f"cue-{index + 1}",
                "start": start + 0.06,
                "end": end - 0.06,
                "text": f"Synthetic English cue {index + 1}.",
            }
        )
    target_t = np.arange(round((shift + stretch * duration) * rate)) / rate
    target = np.interp((target_t - shift) / stretch, t, signal, left=0.0, right=0.0)
    write_wav(output / "reference.wav", signal)
    write_wav(output / "target.wav", target)
    data = {"language": "en", "cues": cues}
    (output / "cues.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    oracle = {
        "kind": "synthetic_audio_time_transform",
        "sample_rate": rate,
        "shift_seconds": shift,
        "stretch_factor": stretch,
        "boundary_formula": "target_time = shift_seconds + stretch_factor * reference_time",
        "cues": [
            {**cue, "start": shift + stretch * cue["start"], "end": shift + stretch * cue["end"]}
            for cue in cues
        ],
    }
    (output / "oracle.json").write_text(json.dumps(oracle, indent=2) + "\n", encoding="utf-8")
    return oracle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic audio DTW validation inputs")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shift", type=float, default=0.24)
    parser.add_argument("--stretch", type=float, default=1.08)
    args = parser.parse_args(argv)
    try:
        generate(args.output, args.shift, args.stretch)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Synthetic fixtures written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
