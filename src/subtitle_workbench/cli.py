"""Command line entry point."""

import argparse
import json
import sys
from pathlib import Path

from .models import Config
from .pipeline import align, run_speech_pipeline


class CLIArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser printing error: <message> without usage and exiting 2."""

    def error(self, message: str) -> None:
        print(f"error: {message}", file=sys.stderr)
        sys.exit(2)


def main(argv: list[str] | None = None) -> int:
    parser = CLIArgumentParser(
        prog="subtitle-workbench",
        description="Speech alignment and accessibility subtitle workbench.",
    )
    # Legacy root flags (DTW mode when no subcommand is specified)
    parser.add_argument(
        "--reference", type=Path, default=None, help="Reference PCM16 mono 16 kHz WAV"
    )
    parser.add_argument("--target", type=Path, default=None, help="Target PCM16 mono 16 kHz WAV")
    parser.add_argument("--cues", type=Path, default=None, help="Checked reference cue JSON")
    parser.add_argument("-o", "--output", type=Path, default=None, help="New output directory")
    parser.add_argument("--band-seconds", type=float, default=0.5)
    parser.add_argument("--spectral-weight", type=float, default=0.15)
    parser.add_argument("--max-frames", type=int, default=3000)
    parser.add_argument("--max-cells", type=int, default=2_000_000)

    subparsers = parser.add_subparsers(dest="subcommand")

    # align-speech subcommand
    speech_parser = subparsers.add_parser(
        "align-speech",
        help="Force-align speech audio with transcript to generate accessible subtitles.",
    )
    speech_parser.add_argument("audio_wav", type=Path, help="Audio PCM16 mono 16 kHz WAV file")
    speech_parser.add_argument("-o", "--output", required=True, type=Path, help="Output directory")
    speech_parser.add_argument(
        "--engine",
        choices=["mfa", "ctc"],
        default="mfa",
        help="Forced alignment engine (default: mfa; no implicit fallback)",
    )
    transcript_group = speech_parser.add_mutually_exclusive_group()
    transcript_group.add_argument(
        "--transcript-text",
        type=str,
        default=None,
        help="Known transcript as inline text (scenario A)",
    )
    transcript_group.add_argument(
        "--transcript-file",
        type=Path,
        default=None,
        help="Known transcript as UTF-8 text file (scenario A)",
    )
    speech_parser.add_argument(
        "--vad-silence-min-sec",
        type=float,
        default=0.4,
        help="Minimum VAD silence duration in seconds",
    )
    speech_parser.add_argument(
        "--max-chunk-sec",
        type=float,
        default=30.0,
        help="Maximum chunk duration in seconds",
    )
    speech_parser.add_argument(
        "--chunk-padding-sec",
        type=float,
        default=0.5,
        help="Chunk overlap padding in seconds",
    )

    # align-dtw subcommand
    dtw_parser = subparsers.add_parser(
        "align-dtw",
        help="Transfer subtitle timings between reference and target audio tracks via DTW.",
    )
    dtw_parser.add_argument("ref_wav", type=Path, help="Reference PCM16 mono 16 kHz WAV")
    dtw_parser.add_argument("target_wav", type=Path, help="Target PCM16 mono 16 kHz WAV")
    dtw_parser.add_argument("cues_json", type=Path, help="Checked reference cue JSON")
    dtw_parser.add_argument("-o", "--output", required=True, type=Path, help="Output directory")
    dtw_parser.add_argument("--band-seconds", type=float, default=0.5)
    dtw_parser.add_argument("--spectral-weight", type=float, default=0.15)
    dtw_parser.add_argument("--max-frames", type=int, default=3000)
    dtw_parser.add_argument("--max-cells", type=int, default=2_000_000)

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    try:
        if args.subcommand == "align-speech":
            manifest = run_speech_pipeline(
                audio_path=args.audio_wav,
                output_dir=args.output,
                transcript_text=args.transcript_text,
                transcript_path=args.transcript_file,
                engine=args.engine,
                vad_silence_min_sec=args.vad_silence_min_sec,
                max_chunk_sec=args.max_chunk_sec,
                chunk_padding_sec=args.chunk_padding_sec,
            )
        elif args.subcommand == "align-dtw":
            manifest = align(
                reference_path=args.ref_wav,
                target_path=args.target_wav,
                cues_path=args.cues_json,
                output_dir=args.output,
                config=Config(
                    band_seconds=args.band_seconds,
                    spectral_weight=args.spectral_weight,
                    max_frames=args.max_frames,
                    max_cells=args.max_cells,
                ),
            )
        else:
            if not (args.reference and args.target and args.cues and args.output):
                print(
                    "error: missing required arguments: --reference, --target, --cues, -o/--output "
                    "(or specify subcommand: align-speech, align-dtw)",
                    file=sys.stderr,
                )
                return 2
            manifest = align(
                reference_path=args.reference,
                target_path=args.target,
                cues_path=args.cues,
                output_dir=args.output,
                config=Config(
                    band_seconds=args.band_seconds,
                    spectral_weight=args.spectral_weight,
                    max_frames=args.max_frames,
                    max_cells=args.max_cells,
                ),
            )
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(json.dumps(manifest["metrics"], indent=2))
    return 0


__all__ = ["main"]
