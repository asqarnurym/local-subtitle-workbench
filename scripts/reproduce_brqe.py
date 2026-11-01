"""R2: one control BRQE training run, followed by a separate saved-model checker."""

from __future__ import annotations

import argparse
import ast
import datetime
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.replay_frozen_metrics import write_json  # noqa: E402
from scripts.verify_frozen_evidence import (  # noqa: E402
    audit,
    digest,
    git,
    local_path,
    read_json,
    require,
    verify_reference_snapshot,
)
from subtitle_workbench.provenance import code_provenance  # noqa: E402
from subtitle_workbench.refiner import TrainConfig  # noqa: E402

BASELINE = "reports/frozen_evidence_audit_20261101.json"


def check_frozen_training_code(revision: str) -> dict:
    files = (
        "scripts/train_brqe.py",
        "src/subtitle_workbench/refiner.py",
        "src/subtitle_workbench/metrics.py",
        "src/subtitle_workbench/corpora.py",
        "src/subtitle_workbench/models.py",
        "src/subtitle_workbench/phone_sets.py",
        "src/subtitle_workbench/text_norm.py",
        "uv.lock",
        "pyproject.toml",
    )
    checks = {}
    for name in files:
        old = git("show", f"{revision}:{name}").replace(b"\r\n", b"\n")
        checks[name] = old == local_path(name).read_bytes().replace(b"\r\n", b"\n")
    # Other benchmark sections gained crash guards after the original training.
    # Compare the actual declarations imported by train_brqe.py as ASTs.
    name = "scripts/speech_benchmark.py"
    old_tree = ast.parse(git("show", f"{revision}:{name}").decode("utf-8"))
    new_tree = ast.parse(local_path(name).read_text(encoding="utf-8"))
    for symbol in (
        "BenchmarkUtterance",
        "get_audio_duration_seconds",
        "_speaker_from_stem",
        "load_textgrid_utterances",
        "load_utterance_sample",
        "select_utterances",
    ):
        old = next(node for node in old_tree.body if getattr(node, "name", None) == symbol)
        new = next(node for node in new_tree.body if getattr(node, "name", None) == symbol)
        checks[f"{name}:{symbol}"] = ast.dump(old) == ast.dump(new)
    require(
        all(checks.values()), "Frozen training code differs; refusing an uncontrolled reproduction"
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", required=True, help="Fresh ignored subdirectory of reports/"
    )
    args = parser.parse_args()
    destination = local_path(args.output_dir)
    require(
        destination.parent == ROOT / "reports" and not destination.exists(),
        "Choose a fresh directory directly under reports/",
    )
    started, started_utc = time.perf_counter(), datetime.datetime.now(datetime.UTC).isoformat()
    code = code_provenance()
    require(code["git_worktree_dirty"] is False, "Commit and test changes before training")
    original = read_json("reports/brqe_final_20260401.json")
    require(
        TrainConfig().__dict__ == original["config"],
        "Default training config differs from the frozen config",
    )
    checks = check_frozen_training_code(original["code"]["git_revision"])
    preflight = audit()
    verify_reference_snapshot(preflight, read_json(BASELINE))
    protected = {p: entry["sha256"] for p, entry in preflight["files"].items()}
    protected.update(preflight["reference_snapshot"]["files"])
    for uid, sha in read_json("reports/brqe_train_run/manifest.json")["inputs"][
        "audio_files"
    ].items():
        protected[f"data/corpora/buckeye/{uid}.wav"] = sha
    for p in [
        *sorted((ROOT / "scripts").glob("*.py")),
        *sorted((ROOT / "src/subtitle_workbench").glob("*.py")),
        ROOT / "uv.lock",
        ROOT / "pyproject.toml",
        local_path(BASELINE),
    ]:
        protected[p.relative_to(ROOT).as_posix()] = digest(p)
    require(
        all(digest(local_path(p)) == sha for p, sha in protected.items()),
        "Protected input mismatch",
    )
    destination.mkdir()
    write_json(destination / "integrity_preflight.json", preflight)
    torch_runtime = json.loads(
        subprocess.check_output(
            [
                sys.executable,
                "-c",
                "import json,torch; print(json.dumps({'version':torch.__version__,'num_threads':torch.get_num_threads(),'num_interop_threads':torch.get_num_interop_threads(),'deterministic_algorithms':torch.are_deterministic_algorithms_enabled(),'mkldnn_enabled':torch.backends.mkldnn.enabled,'build':torch.__config__.show()}))",
            ],
            cwd=ROOT,
            text=True,
        )
    )
    report = {
        "schema_version": 1,
        "check": "R2_BRQE_CONTROL_TRAINING",
        "status": "ERROR",
        "started_utc": started_utc,
        "code_start": code,
        "original_training_report": "reports/brqe_final_20260401.json",
        "original_training_dirty_flag": original["code"]["git_worktree_dirty"],
        "frozen_training_code_equal": checks,
        "config": original["config"],
        "baseline": BASELINE,
        "baseline_sha256": protected[BASELINE],
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {
                name: importlib.metadata.version(name) for name in ("numpy", "torch", "torchaudio")
            },
            "torch": torch_runtime,
            "thread_environment": {
                key: os.environ.get(key)
                for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
            },
        },
        "protected_files": protected,
        "criterion": "Exact tensor/buffer and forward-output equality; no tolerance, no model selection or replacement of frozen weights.",
    }
    try:
        train_cmd = [
            sys.executable,
            "-X",
            "faulthandler",
            "-u",
            "scripts/train_brqe.py",
            "--run",
            "reports/brqe_train_run",
            "--split",
            "reports/buckeye_split_20260401.json",
            "--final",
            (destination / "model").relative_to(ROOT).as_posix(),
            "--report",
            (destination / "training_report.json").relative_to(ROOT).as_posix(),
            "--epochs",
            str(original["config"]["epochs"]),
        ]
        report["training_command"] = train_cmd[1:]
        write_json(destination / "report.json", report)
        print(
            "[*] R2: starting one frozen-config training run; detailed output in training.log",
            flush=True,
        )
        with (destination / "training.log").open("w", encoding="utf-8") as log:
            trained = subprocess.run(
                train_cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False
            )
        report["training_exit_code"] = trained.returncode
        require(trained.returncode == 0, "Control training failed; see training.log")
        result = read_json((destination / "training_report.json").relative_to(ROOT).as_posix())
        for key in ("config", "input", "n_boundaries", "n_matched", "const_offsets"):
            require(result[key] == original[key], f"Control training metadata differs: {key}")
        require(
            result["code"]["git_worktree_dirty"] is False,
            "Control training report records a dirty tree",
        )
        require(
            digest(destination / "model/brqe.pt") == result["weights_sha256"],
            "Control weights differ from their training report",
        )
        report["training_report"] = result
        write_json(destination / "report.json", report)
        print(
            "[*] R2: training finished; starting independent checkpoint and forward check",
            flush=True,
        )
        check_cmd = [
            sys.executable,
            "-X",
            "faulthandler",
            "-u",
            "scripts/check_brqe_reproduction.py",
            "--control-dir",
            (destination / "model").relative_to(ROOT).as_posix(),
            "--output",
            (destination / "independent_check.json").relative_to(ROOT).as_posix(),
        ]
        report["independent_command"] = check_cmd[1:]
        with (destination / "independent_check.log").open("w", encoding="utf-8") as log:
            checked = subprocess.run(
                check_cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False
            )
        report["independent_exit_code"] = checked.returncode
        independent = destination / "independent_check.json"
        if independent.exists():
            report["independent_check"] = read_json(independent.relative_to(ROOT).as_posix())
            report["status"] = report["independent_check"]["status"]
        require(
            checked.returncode == 0, "Independent verification did not match; see its report/log"
        )
    except Exception as err:
        report["error"] = f"{type(err).__name__}: {err}"
        if report["status"] != "MISMATCH":
            report["status"] = "ERROR"
    finally:
        report["protected_files_changed"] = [
            p
            for p, sha in protected.items()
            if not local_path(p).is_file() or digest(local_path(p)) != sha
        ]
        report["code_end"] = code_provenance()
        if report["protected_files_changed"] or report["code_end"] != code:
            report["status"] = "ERROR"
        report["outputs"] = {
            p.relative_to(ROOT).as_posix(): digest(p)
            for p in sorted(destination.rglob("*"))
            if p.is_file() and p != destination / "report.json"
        }
        report["seconds"] = round(time.perf_counter() - started, 3)
        report["finished_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
        write_json(destination / "report.json", report)
    print(
        f"[+] R2 {report['status']}: {destination.relative_to(ROOT).as_posix()}/report.json",
        flush=True,
    )
    return 0 if report["status"] == "EXACT_MATCH" and "error" not in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
