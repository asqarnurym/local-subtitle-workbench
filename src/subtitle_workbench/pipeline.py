"""Offline alignment, audit manifest, and output publication."""

import hashlib
import json
import platform
import time
from dataclasses import asdict
from math import ceil
from pathlib import Path

import numpy as np

from . import __version__
from .audio import extract_features, load_wav
from .dtw import banded_dtw
from .export import jsonld, webvtt
from .models import Config, Cue, validate_cues
from .provenance import code_provenance, sha256

__all__ = [
    "align",
    "code_provenance",
    "sha256",
]


def align(
    reference_path: Path,
    target_path: Path,
    cues_path: Path,
    output_dir: Path,
    config: Config | None = None,
) -> dict:
    config = config or Config()
    started = time.perf_counter()
    paths = [Path(reference_path), Path(target_path), Path(cues_path)]
    output_dir = Path(output_dir)
    outputs = [
        output_dir / name
        for name in ("subtitles.vtt", "timeline.jsonld", "alignment-path.json", "manifest.json")
    ]
    if any(path.exists() for path in outputs):
        raise ValueError("output files already exist; choose a new output directory")
    if any(output.resolve() == source.resolve() for output in outputs for source in paths):
        raise ValueError("output may not overwrite an input")
    if paths[2].stat().st_size > 2_000_000:
        raise ValueError("cue JSON exceeds 2 MB limit")
    reference, target = (load_wav(path, config) for path in paths[:2])
    with paths[2].open(encoding="utf-8") as stream:
        try:
            cue_data = json.load(stream)
        except RecursionError as error:
            raise ValueError("cue JSON nesting exceeds parser limit") from error
        cues = validate_cues(cue_data, reference.duration)
    reference_times, reference_features = extract_features(reference, config)
    target_times, target_features = extract_features(target, config)
    result = banded_dtw(
        reference_features,
        target_features,
        ceil(config.band_seconds / config.hop_seconds),
        config.max_cells,
    )
    mapped = np.empty(len(reference_times))
    _, starts = np.unique(result.path[:, 0], return_index=True)
    ends = np.append(starts[1:], len(result.path))
    for index, (start, end) in enumerate(zip(starts, ends, strict=True)):
        mapped[index] = np.median(target_times[result.path[start:end, 1]])
    mapped = np.maximum.accumulate(mapped)
    # Audio endpoints anchor the full track; interior cues interpolate the observed path.
    knots = np.append(reference_times, reference.duration)
    values = np.append(mapped, target.duration)
    values[0] = 0.0
    aligned = [
        Cue(
            cue.id,
            float(np.interp(cue.start, knots, values)),
            float(np.interp(cue.end, knots, values)),
            cue.text,
        )
        for cue in cues
    ]
    validate_cues({"language": "en", "cues": [asdict(cue) for cue in aligned]}, target.duration)
    vtt = webvtt(aligned)
    target_hash = sha256(paths[1])
    timeline = jsonld(aligned, target.duration, f"urn:local-subtitle-workbench:video:{target_hash}")
    elapsed = time.perf_counter() - started
    path_data = {
        "columns": ["reference_frame", "target_frame"],
        "frame_hop_seconds": config.hop_seconds,
        "frame_time_origin_seconds": 0.0,
        "path": result.path.tolist(),
    }
    payloads = [
        vtt,
        json.dumps(timeline, ensure_ascii=False, indent=2) + "\n",
        json.dumps(path_data, indent=2) + "\n",
    ]
    manifest = {
        "schema_version": 1,
        "tool": {"name": "local-subtitle-workbench", "version": __version__},
        "code": code_provenance(),
        "inputs": {
            key: {"filename": path.name, "sha256": sha256(path)}
            for key, path in zip(
                ("reference_audio", "target_audio", "reference_cues"), paths, strict=True
            )
        },
        "config": asdict(config),
        "outputs": {
            path.name: {"sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest()}
            for path, payload in zip(outputs[:3], payloads, strict=True)
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "metrics": {
            "reference_duration_seconds": reference.duration,
            "target_duration_seconds": target.duration,
            "reference_frames": len(reference_times),
            "target_frames": len(target_times),
            "evaluated_cells": result.cells,
            "path_length": len(result.path),
            "mean_path_cost": result.cost / len(result.path),
            "cue_count": len(aligned),
            "alignment_elapsed_seconds": elapsed,
            "alignment_rtf": elapsed / target.duration,
        },
        "limitations": [
            "Reference cues must already be correctly timed and labelled English.",
            "Audio-to-audio timing transfer does not recognize or force-align text.",
            "Path cost is not speech recognition accuracy or timing error.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads.append(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    for path, payload in zip(outputs, payloads, strict=True):
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
    return manifest
