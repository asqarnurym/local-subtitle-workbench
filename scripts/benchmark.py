"""Compare exported cue boundaries with the synthetic timing oracle."""

import argparse
import json
from pathlib import Path

import numpy as np


def benchmark(oracle_path: Path, timeline_path: Path) -> dict:
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    clips = timeline["hasPart"]
    if len(clips) != len(oracle["cues"]):
        raise ValueError("oracle and timeline cue counts differ")
    errors = []
    for cue, clip in zip(oracle["cues"], clips, strict=True):
        if not clip["@id"].endswith("#cue-" + cue["id"]):
            raise ValueError("oracle and timeline cue IDs differ")
        errors.extend(
            [abs(clip["startOffset"] - cue["start"]), abs(clip["endOffset"] - cue["end"])]
        )
    return {
        "validation_kind": "synthetic_audio_time_transform",
        "boundaries": len(errors),
        "mean_absolute_error_ms": float(np.mean(errors) * 1000),
        "max_absolute_error_ms": float(np.max(errors) * 1000),
        "within_50ms_percent": float(np.mean(np.asarray(errors) <= 0.05) * 100),
        "speech_accuracy_claim": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle", required=True, type=Path)
    parser.add_argument("--timeline", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.oracle, args.timeline), indent=2))
