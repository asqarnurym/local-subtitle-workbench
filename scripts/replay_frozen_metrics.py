"""R1: recompute frozen metrics from saved predictions, without running models.

Original outputs and the reference snapshot are read-only. A fresh ignored output
directory holds the replay, its exact comparisons, and the integrity-check record.
"""

from __future__ import annotations

import argparse
import datetime
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import speech_benchmark as benchmark  # noqa: E402
from scripts.verify_frozen_evidence import (  # noqa: E402
    audit,
    digest,
    local_path,
    read_json,
    require,
    verify_reference_snapshot,
)
from subtitle_workbench.models import PhonemeCue, WordToken  # noqa: E402
from subtitle_workbench.provenance import code_provenance  # noqa: E402

BASELINE = "reports/frozen_evidence_audit_20261101.json"


def write_json(path: Path, value: Any) -> None:
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8"))


def deserialize_predictions(payload: dict) -> dict:
    require(payload["schema_version"] == 1, "Unsupported prediction schema")
    require(
        payload["fields"]
        == {
            "word": "text,normalized,start,end,confidence",
            "phone": "phoneme,start,end",
        },
        "Replay requires the complete saved confidence field",
    )
    out = {}
    for mode, entries in payload["modes"].items():
        out[mode] = {}
        for uid, item in entries.items():
            if item["status"] == "failed":
                require(
                    isinstance(item.get("error"), str) and bool(item["error"]),
                    "Missing failure reason",
                )
                out[mode][uid] = item["error"]
            else:
                require(item["status"] == "ok", f"Unknown prediction status: {uid}")
                words = [WordToken(f"w{i}", *values) for i, values in enumerate(item["words"])]
                phones = item["phones"]
                out[mode][uid] = (
                    words,
                    None if phones is None else [PhonemeCue(*values, 1.0) for values in phones],
                )
    return out


def differences(expected: Any, actual: Any, path: str = "$") -> list[dict]:
    """Compare all saved fields exactly; no tolerance or selective field filtering."""
    out = []
    if type(expected) is not type(actual):
        return [{"path": path, "expected": expected, "actual": actual}]
    if isinstance(expected, dict):
        for key in sorted(expected.keys() | actual.keys()):
            if key not in expected or key not in actual:
                out.append(
                    {
                        "path": f"{path}.{key}",
                        "missing_from": "expected" if key not in expected else "actual",
                    }
                )
            else:
                out.extend(differences(expected[key], actual[key], f"{path}.{key}"))
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            out.append(
                {"path": path, "expected_length": len(expected), "actual_length": len(actual)}
            )
        for i, (left, right) in enumerate(zip(expected, actual, strict=False)):
            out.extend(differences(left, right, f"{path}[{i}]"))
    elif expected != actual:
        out.append({"path": path, "expected": expected, "actual": actual})
    return out


def replay_run(name: str, output_dir: Path) -> dict:
    started = time.perf_counter()
    base = f"reports/{name}"
    original = read_json(f"{base}/benchmark_results.json")
    manifest = read_json(f"{base}/manifest.json")
    all_utterances = (
        benchmark.load_timit_utterances(local_path("data/corpora/timit"))
        if name == "timit"
        else benchmark.load_textgrid_utterances(local_path("data/corpora/buckeye"), "buckeye")
    )
    ids = list(manifest["inputs"]["audio_files"])
    utterances = benchmark.select_utterances(all_utterances, ids)
    predictions = deserialize_predictions(read_json(f"{base}/benchmark_predictions.json"))
    modes, rows = {}, []
    for mode in original["config"]["modes"]:
        summary, per_clip = benchmark.evaluate_mode(
            mode,
            utterances,
            predictions[mode],
            original["config"]["ci_unit"],
            original["bootstrap_resamples"],
            original["seed"],
        )
        if benchmark.MODES[mode].refiner == "brqe":
            summary["quality_estimation"] = benchmark.quality_estimation(
                utterances, predictions[benchmark.MODES[mode].base], predictions[mode]
            )
        modes[mode] = summary
        rows.extend(per_clip)
        print(f"[*] {name}/{mode}: replayed", flush=True)
    comparisons = benchmark.compare_modes(rows, original["config"]["modes"], original["n_speakers"])
    recomputed = {"modes": modes, "statistical_significance": comparisons}
    expected = {key: original[key] for key in recomputed}
    deltas = {
        "summary": differences(expected, recomputed),
        "rows": differences(read_json(f"{base}/benchmark_utterances.json"), rows),
    }
    destination = output_dir / name
    destination.mkdir()
    write_json(destination / "recomputed_metrics.json", recomputed)
    write_json(destination / "recomputed_rows.json", rows)
    write_json(destination / "differences.json", deltas)
    result = {
        "status": "MATCH" if not any(deltas.values()) else "MISMATCH",
        "execution_git_revision": manifest["code"]["git_revision"],
        "n_utterances": len(utterances),
        "n_speakers": original["n_speakers"],
        "n_modes": len(modes),
        "n_rows": len(rows),
        "n_comparisons": len(comparisons),
        "seed": original["seed"],
        "bootstrap_resamples": original["bootstrap_resamples"],
        "summary_differences": len(deltas["summary"]),
        "row_differences": len(deltas["rows"]),
        "difference_examples": {key: values[:10] for key, values in deltas.items()},
        "recomputed_files": {
            p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(destination.iterdir())
        },
        "seconds": round(time.perf_counter() - started, 3),
    }
    print(f"[+] {name}: {result['status']}", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", required=True, help="Fresh ignored subdirectory of reports/"
    )
    args = parser.parse_args()
    destination = local_path(args.output_dir)
    require(destination.parent == ROOT / "reports", "Output must be directly under reports/")
    require(not destination.exists(), "Replay output directory already exists")
    started = time.perf_counter()
    code = code_provenance()
    require(code["git_worktree_dirty"] is False, "Commit changes before replaying frozen evidence")
    preflight = audit()
    verify_reference_snapshot(preflight, read_json(BASELINE))
    protected = {path: entry["sha256"] for path, entry in preflight["files"].items()}
    protected.update(preflight["reference_snapshot"]["files"])
    protected[BASELINE] = digest(local_path(BASELINE))
    evaluated_sources = [
        Path(__file__).resolve(),
        ROOT / "scripts/speech_benchmark.py",
        ROOT / "uv.lock",
        ROOT / "pyproject.toml",
        *sorted((ROOT / "src/subtitle_workbench").glob("*.py")),
    ]
    protected.update({p.relative_to(ROOT).as_posix(): digest(p) for p in evaluated_sources})
    destination.mkdir()
    write_json(destination / "integrity_preflight.json", preflight)
    report = {
        "schema_version": 1,
        "check": "R1_FROZEN_METRIC_REPLAY",
        "status": "ERROR",
        "started_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "code_start": code,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "baseline": BASELINE,
        "baseline_sha256": protected[BASELINE],
        "comparison": "Exact equality of all saved mode-summary fields, clip rows and clip-level statistical comparisons; original rounding and seed.",
        "protected_files": protected,
        "runs": {},
        "limitations": [
            "This replays the existing scoring implementation; it does not independently validate its statistical methodology.",
            "Agreement with current references cannot reconstruct their absent historical hashes.",
            "No ASR, forced alignment, BRQE inference, retraining or new speaker-level tests are performed.",
        ],
    }
    try:
        for name in ("timit", "buckeye"):
            report["runs"][name] = replay_run(name, destination)
            require(report["runs"][name]["status"] == "MATCH", f"Metric replay mismatch: {name}")
            write_json(destination / "report.json", report)
        report["status"] = "MATCH"
    except Exception as err:
        report["error"] = f"{type(err).__name__}: {err}"
    finally:
        changed = [
            path
            for path, expected in protected.items()
            if not local_path(path).is_file() or digest(local_path(path)) != expected
        ]
        report["protected_files_changed"] = changed
        report["code_end"] = code_provenance()
        if changed or report["code_end"] != code:
            report["status"] = "ERROR"
        report["seconds"] = round(time.perf_counter() - started, 3)
        report["finished_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
        write_json(destination / "report.json", report)
    print(f"[+] R1 {report['status']}: {destination.relative_to(ROOT).as_posix()}/report.json")
    return 0 if report["status"] == "MATCH" else 1


if __name__ == "__main__":
    raise SystemExit(main())
