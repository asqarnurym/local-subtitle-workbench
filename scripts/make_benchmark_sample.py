"""Draw a fixed, seeded per-speaker utterance sample and save it as JSON.

The file is the input of ``speech_benchmark.py --utterance-list``. Speakers and
utterance IDs are sorted before drawing, so the same corpus and seed always give
the same sample. An existing output file is never overwritten: a sample is part of
the frozen benchmark.

Examples (docs/RUNBOOK.md section 3a):
  python scripts/make_benchmark_sample.py --corpus buckeye --per-speaker 10 \
      --seed 20260401 --output reports/buckeye_sample_20260401.json
  python scripts/make_benchmark_sample.py --corpus timit --speakers 10 --per-speaker 1 \
      --seed 20260401 --output reports/timit_pilot_20260401.json
"""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.speech_benchmark import (  # noqa: E402
    SAMPLE_SCHEMA_VERSION,
    BenchmarkError,
    draw_speaker_sample,
    load_textgrid_utterances,
    load_timit_utterances,
)
from subtitle_workbench.provenance import sha256  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draw a seeded per-speaker benchmark sample.")
    parser.add_argument(
        "--corpus", choices=["timit", "buckeye", "librispeech", "l2arctic"], required=True
    )
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--per-speaker", type=int, required=True)
    parser.add_argument(
        "--speakers", type=int, default=None, help="Draw this many speakers first (default: all)"
    )
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--split", type=Path, default=None, help="Speaker split from make_speaker_split.py"
    )
    parser.add_argument(
        "--group", choices=["test", "train"], default=None, help="Split group to sample from"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_dir = args.data_dir or Path(f"data/corpora/{args.corpus}")
    try:
        if args.output.exists():
            raise BenchmarkError(f"Output exists, refusing to overwrite: {args.output}")
        if not data_dir.is_dir():
            raise BenchmarkError(f"Corpus directory not found: {data_dir}")
        if (args.split is None) != (args.group is None):
            raise BenchmarkError("--split and --group must be given together")
        group = None
        if args.split is not None:
            split = json.loads(args.split.read_text(encoding="utf-8"))
            if split.get("corpus") != args.corpus:
                raise BenchmarkError(f"Split is for corpus '{split.get('corpus')}'")
            group = set(split[f"{args.group}_speakers"])
        if args.corpus == "timit":
            utterances = load_timit_utterances(data_dir)
        else:
            utterances = load_textgrid_utterances(data_dir, args.corpus)
        if group is not None:
            utterances = [u for u in utterances if u.speaker_id in group]
            if {u.speaker_id for u in utterances} != group:
                raise BenchmarkError("Some split speakers have no utterances in the corpus")
        ids = draw_speaker_sample(utterances, args.per_speaker, args.seed, args.speakers)
    except BenchmarkError as err:
        sys.stderr.write(f"[-] Sample Error: {err}\n")
        return 1

    speaker_of = {u.id: u.speaker_id for u in utterances}
    per_spk = collections.Counter(speaker_of[i] for i in ids)
    sample = {
        "schema_version": SAMPLE_SCHEMA_VERSION,
        "corpus": args.corpus,
        "data_dir": data_dir.as_posix(),
        "seed": args.seed,
        "per_speaker": args.per_speaker,
        "n_speakers_requested": args.speakers,
        "method": (
            "speakers and IDs sorted; numpy default_rng(seed); optional uniform speaker "
            "subset, then per_speaker IDs per speaker uniformly without replacement"
        ),
        "split": (
            {"path": args.split.as_posix(), "sha256": sha256(args.split), "group": args.group}
            if args.split is not None
            else None
        ),
        "source_n_utterances": len(utterances),
        "source_n_speakers": len({u.speaker_id for u in utterances}),
        "n_speakers": len(per_spk),
        "n_utterances": len(ids),
        "created_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "utterance_ids": ids,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")
    print(
        f"[OK] {len(ids)} utterances from {len(per_spk)} speakers "
        f"(of {sample['source_n_utterances']}) written to {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
