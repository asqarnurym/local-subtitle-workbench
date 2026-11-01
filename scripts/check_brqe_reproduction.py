"""Independently read two saved BRQE models and compare states and forward outputs.

No training occurs here. Inference uses freshly reconstructed train-only features
and the saved networks directly, not BRQERefiner.predict or cached predictions.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.replay_frozen_metrics import write_json  # noqa: E402
from scripts.train_brqe import load_training_boundaries  # noqa: E402
from scripts.verify_frozen_evidence import (  # noqa: E402
    audit,
    digest,
    local_path,
    read_json,
    require,
    verify_reference_snapshot,
)
from subtitle_workbench.provenance import code_provenance  # noqa: E402
from subtitle_workbench.refiner import (  # noqa: E402
    BRQERefiner,
    scalar_features,
    window_at,
)


def compare_states(original: dict, control: dict) -> dict:
    """Include learned parameters and non-learned buffers; enforce exact equality."""
    result = {"keys_equal": original.keys() == control.keys(), "tensors": {}}
    for name in sorted(original.keys() & control.keys()):
        left, right = original[name], control[name]
        same_layout = left.shape == right.shape and left.dtype == right.dtype
        finite = bool(torch.isfinite(left).all() and torch.isfinite(right).all())
        result["tensors"][name] = {
            "shape": list(left.shape),
            "dtype": str(left.dtype),
            "same_shape_and_dtype": same_layout,
            "finite": finite,
            "equal": bool(same_layout and finite and torch.equal(left, right)),
            "max_absolute_difference": float((left.double() - right.double()).abs().max())
            if same_layout and finite
            else None,
        }
    result["equal"] = result["keys_equal"] and all(v["equal"] for v in result["tensors"].values())
    return result


def compare_outputs(original, control, boundaries, mels, batch_size: int = 1024) -> dict:
    require(batch_size > 0, "Invalid inference batch size")
    stats = {
        key: {"n_values": 0, "n_different": 0, "max_absolute_difference": 0.0}
        for key in ("shift_seconds", "error_probability")
    }
    hashes = {side: hashlib.sha256() for side in ("original", "control")}
    with torch.inference_mode():
        for first in range(0, len(boundaries), batch_size):
            batch = boundaries[first : first + batch_size]
            patches, scalars = [], []
            for boundary in batch:
                patch, offset = window_at(mels[boundary.utt], boundary.time)
                patches.append(patch)
                scalars.append(scalar_features(boundary, offset))
            x, s = torch.from_numpy(np.stack(patches)), torch.from_numpy(np.stack(scalars))
            original_shift, original_logit = original(x, s)
            control_shift, control_logit = control(x, s)
            pairs = (
                (original_shift, control_shift),
                (torch.sigmoid(original_logit), torch.sigmoid(control_logit)),
            )
            for (key, values), (left, right) in zip(stats.items(), pairs, strict=True):
                require(
                    bool(torch.isfinite(left).all() and torch.isfinite(right).all()),
                    f"Nonfinite {key}",
                )
                values["n_values"] += left.numel()
                values["n_different"] += int(torch.count_nonzero(left != right))
                values["max_absolute_difference"] = max(
                    values["max_absolute_difference"], float((left - right).abs().max())
                )
                for side, tensor in (("original", left), ("control", right)):
                    hashes[side].update(
                        key.encode() + b"\0" + tensor.numpy().astype("<f4", copy=False).tobytes()
                    )
            if first == 0 or first // batch_size % 100 == 0:
                print(
                    f"[*] independent forward check: {first + len(batch)}/{len(boundaries)} boundaries",
                    flush=True,
                )
    return {
        "equal": all(v["n_different"] == 0 for v in stats.values()),
        "batch_size": batch_size,
        "heads": stats,
        "prediction_sha256": {side: h.hexdigest() for side, h in hashes.items()},
        "hash_encoding": "Per batch: head name, NUL, float32 little-endian output bytes; shift then probability.",
    }


def check(original_dir: Path, control_dir: Path) -> dict:
    started = time.perf_counter()
    baseline_path = "reports/frozen_evidence_audit_20261101.json"
    preflight = audit()
    verify_reference_snapshot(preflight, read_json(baseline_path))
    original_meta = read_json((original_dir / "brqe.json").relative_to(ROOT).as_posix())
    control_meta = read_json((control_dir / "brqe.json").relative_to(ROOT).as_posix())
    metadata_equal = {
        key: original_meta[key] == control_meta[key] for key in ("config", "features", "trained_on")
    }
    require(
        all(metadata_equal.values()), "Model configurations, features or training inputs differ"
    )
    old_state = torch.load(original_dir / "brqe.pt", map_location="cpu", weights_only=True)
    new_state = torch.load(control_dir / "brqe.pt", map_location="cpu", weights_only=True)
    states = compare_states(old_state, new_state)
    constant_equal = read_json(
        (original_dir / "const_offsets.json").relative_to(ROOT).as_posix()
    ) == read_json((control_dir / "const_offsets.json").relative_to(ROOT).as_posix())
    original, control = (
        BRQERefiner.load(original_dir / "brqe.pt"),
        BRQERefiner.load(control_dir / "brqe.pt"),
    )
    training = original_meta["trained_on"]
    boundaries, mels, meta = load_training_boundaries(
        local_path(training["run"]), local_path(training["split"]["path"])
    )
    # Only the SHA and sample metadata are compared here: the checker resolves
    # paths absolutely while the original CLI records repository-relative paths.
    require(
        meta["sample"] == training["sample"]
        and meta["split"]["sha256"] == training["split"]["sha256"],
        "Independent checker training inputs changed",
    )
    final = read_json("reports/brqe_final_20260401.json")
    require(len(boundaries) == final["n_boundaries"], "Independent boundary count differs")
    require(
        sum(b.ref is not None for b in boundaries) == final["n_matched"],
        "Independent matched boundary count differs",
    )
    require(
        meta["n_speakers"] == 20 and meta["n_utterances"] == 3000,
        "Independent train sample count differs",
    )
    outputs = compare_outputs(original.net, control.net, boundaries, mels)
    status = (
        "EXACT_MATCH" if states["equal"] and constant_equal and outputs["equal"] else "MISMATCH"
    )
    return {
        "schema_version": 1,
        "check": "R2_INDEPENDENT_SAVED_MODEL_CHECK",
        "status": status,
        "checked_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "code": code_provenance(),
        "integrity_preflight_status": preflight["status"],
        "baseline_sha256": digest(local_path(baseline_path)),
        "metadata_equal": metadata_equal,
        "state_comparison": states,
        "constant_refiner_equal": constant_equal,
        "forward_comparison": outputs,
        "n_boundaries": len(boundaries),
        "n_matched": sum(b.ref is not None for b in boundaries),
        "n_utterances": meta["n_utterances"],
        "n_speakers": meta["n_speakers"],
        "checkpoint_sha256": {
            "original": digest(original_dir / "brqe.pt"),
            "control": digest(control_dir / "brqe.pt"),
        },
        "seconds": round(time.perf_counter() - started, 3),
        "scope": "Independent process; freshly loaded checkpoints and train-only features; exact tensor/buffer equality and direct forward calls. No fitting, parameter search, or test-speaker data.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-dir", default="models/brqe")
    parser.add_argument("--control-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = local_path(args.output)
    require(
        output.is_relative_to(ROOT / "reports") and not output.exists(),
        "Check output must be a fresh report under reports/",
    )
    require(
        code_provenance()["git_worktree_dirty"] is False, "Commit changes before model verification"
    )
    result = check(local_path(args.original_dir), local_path(args.control_dir))
    write_json(output, result)
    print(f"[+] independent saved-model check: {result['status']}", flush=True)
    return 0 if result["status"] == "EXACT_MATCH" else 1


if __name__ == "__main__":
    raise SystemExit(main())
