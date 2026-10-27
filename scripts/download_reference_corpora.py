"""Stage reference (gold) speech corpora with manual word/phone boundaries.

Corpora
  synthetic     10 generated utterances for offline plumbing tests (never citable)
  timit-sample  NLTK TIMIT sample: 160 utterances, 16 speakers, hand-labelled word and
                phone boundaries (CC BY-NC-SA, Linguistic Data Consortium). Downloaded
                automatically from the NLTK data repository.
  timit         Full TIMIT (LDC93S1, licensed): unpack it yourself into <target>/timit.
  buckeye       Buckeye Speech Corpus (free for non-commercial use after registration at
                https://buckeyecorpus.osu.edu). Point --buckeye-source at the downloaded
                speaker zips (s01.zip ... s40.zip) or extracted tracks; every track is cut
                into evaluation clips (<clip>.wav + .TextGrid + .txt).
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

from subtitle_workbench.buckeye import stage_track
from subtitle_workbench.corpora import stage_synthetic_benchmark

TIMIT_SAMPLE_URL = (
    "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/timit.zip"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage reference speech corpora.")
    parser.add_argument("--target-dir", type=Path, default=Path("data/corpora"))
    parser.add_argument(
        "--offline-synthetic",
        action="store_true",
        default=False,
        help="Generate 10 offline synthetic utterances with exact ground-truth boundaries",
    )
    parser.add_argument(
        "--corpus",
        choices=["synthetic", "timit-sample", "timit", "buckeye"],
        default="synthetic",
    )
    parser.add_argument(
        "--buckeye-source",
        type=Path,
        default=None,
        help="Directory with Buckeye speaker zips (sNN.zip) or extracted track files",
    )
    return parser.parse_args(argv)


def stage_timit_sample(target: Path) -> int:
    """Download the NLTK TIMIT sample into <target>/<speaker-dir>/<utt>.{wav,wrd,phn,txt}."""
    target.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(TIMIT_SAMPLE_URL, timeout=120) as resp:  # noqa: S310
        payload = resp.read()
    count = 0
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for name in zf.namelist():
            parts = Path(name).parts
            if len(parts) != 3 or not parts[1].startswith("dr"):
                if name.endswith("README"):
                    (target / "README").write_bytes(zf.read(name))
                continue
            if Path(name).suffix not in (".wav", ".wrd", ".phn", ".txt"):
                continue
            dest = target / parts[1] / parts[2]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(name))
            count += Path(name).suffix == ".wav"
    return count


def _iter_buckeye_tracks(source: Path, scratch: Path) -> list[tuple[Path, Path, Path]]:
    """Find (wav, words, phones) triples; unpacks nested speaker/track zips into scratch."""
    for outer in sorted(source.glob("s[0-9][0-9].zip")):
        with zipfile.ZipFile(outer) as zf:
            zf.extractall(scratch / outer.stem)
    for inner in sorted(scratch.glob("**/s[0-9][0-9][0-9][0-9]*.zip")):
        with zipfile.ZipFile(inner) as zf:
            zf.extractall(inner.parent / inner.stem)
    tracks = []
    for root in (source, scratch):
        for words in sorted(root.glob("**/*.words")):
            wav, phones = words.with_suffix(".wav"), words.with_suffix(".phones")
            if wav.is_file() and phones.is_file():
                tracks.append((wav, words, phones))
    unique = {t[0].name: t for t in tracks}
    return [unique[k] for k in sorted(unique)]


def stage_buckeye(source: Path, target: Path) -> dict[str, int]:
    scratch = target / "_unpacked"
    target.mkdir(parents=True, exist_ok=True)
    totals = {"tracks": 0, "clips": 0, "runs": 0, "too_short": 0, "too_long": 0}
    try:
        for wav, words, phones in _iter_buckeye_tracks(source, scratch):
            clips, stats = stage_track(wav, words, phones, target)
            totals["tracks"] += 1
            totals["clips"] += len(clips)
            for k in ("runs", "too_short", "too_long"):
                totals[k] += stats[k]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    (target / "staging_stats.json").write_text(json.dumps(totals, indent=2) + "\n")
    return totals


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target_dir: Path = args.target_dir
    print(f"[*] Target directory: {target_dir}; corpus: {args.corpus}")

    if args.offline_synthetic or args.corpus == "synthetic":
        stage_synthetic_benchmark(target_dir)
        print(f"[+] Successfully staged 10 synthetic utterances in: {target_dir}")
        return 0

    if args.corpus == "timit-sample":
        dest = target_dir / "timit"
        n = stage_timit_sample(dest)
        print(f"[+] Staged NLTK TIMIT sample: {n} utterances in {dest} (CC BY-NC-SA)")
        return 0

    if args.corpus == "timit":
        dest = target_dir / "timit"
        n = len(list(dest.glob("**/*.wrd"))) + len(list(dest.glob("**/*.WRD")))
        if n:
            print(f"[+] Found {n} TIMIT utterances in {dest}")
            return 0
        print(f"[-] Full TIMIT (LDC93S1) is licensed; unpack it into {dest}")
        print("[*] Or use --corpus timit-sample for the free 160-utterance sample.")
        return 1

    # buckeye
    if args.buckeye_source is None or not args.buckeye_source.is_dir():
        print("[-] --buckeye-source must point to the downloaded Buckeye zips/tracks.")
        print("[*] Register at https://buckeyecorpus.osu.edu (free, non-commercial).")
        return 1
    totals = stage_buckeye(args.buckeye_source, target_dir / "buckeye")
    print(f"[+] Buckeye: {totals['clips']} clips from {totals['tracks']} tracks; {totals}")
    return 0 if totals["clips"] else 1


if __name__ == "__main__":
    sys.exit(main())
