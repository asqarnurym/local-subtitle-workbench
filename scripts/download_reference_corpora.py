"""CLI tool to stage or download reference speech corpora for benchmark evaluation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from subtitle_workbench.corpora import stage_synthetic_benchmark


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage or download reference speech corpora for alignment benchmark."
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path("data/corpora"),
        help="Target directory to place reference or synthetic corpora (default: data/corpora)",
    )
    parser.add_argument(
        "--offline-synthetic",
        action="store_true",
        default=False,
        help="Generate 10 offline synthetic utterances with exact ground-truth boundaries",
    )
    parser.add_argument(
        "--corpus",
        choices=["synthetic", "timit", "buckeye", "all"],
        default="synthetic",
        help="Corpus type to stage or verify (default: synthetic)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target_dir: Path = args.target_dir

    print("[*] Reference Corpora Staging Utility")
    print(f"[*] Target directory: {target_dir}")
    print(f"[*] Selected corpus: {args.corpus}")

    if args.offline_synthetic or args.corpus in ("synthetic", "all"):
        print("[*] Generating offline synthetic benchmark dataset (10 utterances)...")
        synth_dir = target_dir if args.corpus == "synthetic" else target_dir / "synthetic"
        stage_synthetic_benchmark(synth_dir)
        print(f"[+] Successfully staged 10 synthetic utterances in: {synth_dir}")

    if args.corpus in ("timit", "all") and not args.offline_synthetic:
        timit_dir = target_dir if args.corpus == "timit" else target_dir / "timit"
        print(f"[*] Verifying TIMIT Core Test corpus at: {timit_dir}")
        if timit_dir.exists() and any(timit_dir.glob("**/*.phn")):
            phn_count = len(list(timit_dir.glob("**/*.phn")))
            print(f"[+] Found {phn_count} TIMIT .phn files in {timit_dir}")
        else:
            print("[-] TIMIT Core Test is an LDC licensed dataset (LDC93S1).")
            print(f"[-] Please unpack your licensed TIMIT distribution into: {timit_dir}")
            print("[*] For offline testing and CI, use --offline-synthetic instead.")

    if args.corpus in ("buckeye", "all") and not args.offline_synthetic:
        buckeye_dir = target_dir if args.corpus == "buckeye" else target_dir / "buckeye"
        print(f"[*] Verifying Buckeye Speech Corpus at: {buckeye_dir}")
        if buckeye_dir.exists() and any(buckeye_dir.glob("**/*.words")):
            wrd_count = len(list(buckeye_dir.glob("**/*.words")))
            print(f"[+] Found {wrd_count} Buckeye files in {buckeye_dir}")
        else:
            print(f"[-] Buckeye Speech Corpus files not found at: {buckeye_dir}")
            print(f"[-] Please download from https://buckeyeverse.osu.edu/ into: {buckeye_dir}")
            print("[*] For offline testing and CI, use --offline-synthetic instead.")

    print("[OK] Corpora staging and inspection completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
