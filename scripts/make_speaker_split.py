"""Split a corpus's speakers into disjoint test and train groups (seeded) and save as JSON.

The test group is the only source of reported benchmark numbers; the train group is
used only to train the BRQE refiner. Speakers are sorted before drawing, so the same
corpus and seed always give the same split. An existing output file is never
overwritten: the split is part of the frozen benchmark.

Example (docs/IMPROVEMENT_PLAN.md, decision D6):
  python scripts/make_speaker_split.py --corpus buckeye --n-test 20 --seed 20260401 \
      --output reports/buckeye_split_20260401.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.speech_benchmark import BenchmarkError, _speaker_from_stem  # noqa: E402

SPLIT_SCHEMA_VERSION = 1


def split_speakers(speakers: list[str], n_test: int, seed: int) -> tuple[list[str], list[str]]:
    """Uniformly draw ``n_test`` speakers for the test group; the rest form the train group."""
    pool = sorted(set(speakers))
    if not 1 <= n_test < len(pool):
        raise BenchmarkError(f"n_test must be in 1..{len(pool) - 1}, got {n_test}")
    if seed < 0:
        raise BenchmarkError(f"Random seed must be non-negative, got {seed}")
    picked = set(np.random.default_rng(seed).choice(len(pool), size=n_test, replace=False))
    test = [s for i, s in enumerate(pool) if i in picked]
    train = [s for i, s in enumerate(pool) if i not in picked]
    return test, train


def corpus_speakers(data_dir: Path, corpus: str) -> list[str]:
    stems = [p.stem for p in data_dir.glob("**/*.TextGrid")]
    return sorted({_speaker_from_stem(s, corpus) for s in stems})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seeded test/train speaker split.")
    parser.add_argument("--corpus", choices=["buckeye", "librispeech", "l2arctic"], required=True)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--n-test", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_dir = args.data_dir or Path(f"data/corpora/{args.corpus}")
    try:
        if args.output.exists():
            raise BenchmarkError(f"Output exists, refusing to overwrite: {args.output}")
        if not data_dir.is_dir():
            raise BenchmarkError(f"Corpus directory not found: {data_dir}")
        speakers = corpus_speakers(data_dir, args.corpus)
        test, train = split_speakers(speakers, args.n_test, args.seed)
    except BenchmarkError as err:
        sys.stderr.write(f"[-] Split Error: {err}\n")
        return 1
    split = {
        "schema_version": SPLIT_SCHEMA_VERSION,
        "corpus": args.corpus,
        "data_dir": data_dir.as_posix(),
        "seed": args.seed,
        "method": "speakers sorted; numpy default_rng(seed).choice(n_test, no replacement)",
        "stratified": False,
        "n_speakers": len(speakers),
        "test_speakers": test,
        "train_speakers": train,
        "created_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(split, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] {len(test)} test / {len(train)} train speakers written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
