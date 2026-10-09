"""Command line entry point."""

import argparse
import json
import sys
import wave
from pathlib import Path

from .models import Config
from .pipeline import align


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Transfer checked English subtitle timings between local audio tracks."
    )
    parser.add_argument(
        "--reference", required=True, type=Path, help="Reference PCM16 mono 16 kHz WAV"
    )
    parser.add_argument("--target", required=True, type=Path, help="Target PCM16 mono 16 kHz WAV")
    parser.add_argument("--cues", required=True, type=Path, help="Checked reference cue JSON")
    parser.add_argument("--output", required=True, type=Path, help="New output directory")
    parser.add_argument("--band-seconds", type=float, default=0.5)
    parser.add_argument("--spectral-weight", type=float, default=0.15)
    parser.add_argument("--max-frames", type=int, default=3000)
    parser.add_argument("--max-cells", type=int, default=2_000_000)
    args = parser.parse_args(argv)
    try:
        manifest = align(
            args.reference,
            args.target,
            args.cues,
            args.output,
            Config(
                band_seconds=args.band_seconds,
                spectral_weight=args.spectral_weight,
                max_frames=args.max_frames,
                max_cells=args.max_cells,
            ),
        )
    except (OSError, ValueError, wave.Error, EOFError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(manifest["metrics"], indent=2))
    return 0
