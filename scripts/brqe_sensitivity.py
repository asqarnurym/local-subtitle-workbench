"""BRQE hyperparameter sensitivity on TRAIN speakers only (docs/BRQE_SENSITIVITY_PROTOCOL.md).

Runs the same speaker-grouped CV as ``train_brqe.py --cv`` for a fixed, pre-registered
list of one-at-a-time variations. Each configuration is written to its own file as
soon as it finishes; finished configurations are not recomputed. Frozen weights,
test runs and approved claims are never read or written.

  python scripts/brqe_sensitivity.py --output-dir reports/brqe_sensitivity_20261102
  python scripts/brqe_sensitivity.py --output-dir reports/brqe_sensitivity_20261102 --verify
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.train_brqe import cross_validate, decide, load_training_boundaries  # noqa: E402
from subtitle_workbench import refiner as refiner_mod  # noqa: E402
from subtitle_workbench.refiner import TrainConfig  # noqa: E402

SCHEMA_VERSION = 1
RUN = Path("reports/brqe_train_run")
SPLIT = Path("reports/buckeye_split_20260401.json")
ORIGINAL_CV = Path("reports/brqe_cv_20260401.json")
K_FOLDS = 5
DEFAULT_HALF_WINDOW = 20  # frames of 5 ms -> +-100 ms, as frozen in refiner.py

# name -> (TrainConfig overrides, half window in frames); the protocol's table
CONFIGS: dict[str, tuple[dict[str, Any], int]] = {
    "baseline": ({}, DEFAULT_HALF_WINDOW),
    "epochs_6": ({"epochs": 6}, DEFAULT_HALF_WINDOW),
    "epochs_24": ({"epochs": 24}, DEFAULT_HALF_WINDOW),
    "window_50ms": ({}, 10),
    "window_150ms": ({}, 30),
    "hidden_64": ({"hidden": 64}, DEFAULT_HALF_WINDOW),
    "hidden_256": ({"hidden": 256}, DEFAULT_HALF_WINDOW),
    "cls_0.25": ({"cls_weight": 0.25}, DEFAULT_HALF_WINDOW),
    "cls_1.0": ({"cls_weight": 1.0}, DEFAULT_HALF_WINDOW),
}
CODE_FILES = (
    "scripts/brqe_sensitivity.py",
    "scripts/train_brqe.py",
    "scripts/speech_benchmark.py",
    "src/subtitle_workbench/refiner.py",
    "src/subtitle_workbench/metrics.py",
    "uv.lock",
    "pyproject.toml",
)
TOLERANCE = 1e-9


class SensitivityError(RuntimeError):
    pass


@contextlib.contextmanager
def window_override(half_window: int) -> Iterator[None]:
    """Temporarily set refiner.HALF_WINDOW / WINDOW (read at call time by window_at,
    _build_net and BRQERefiner._tensors); always restores the frozen values."""
    old = (refiner_mod.HALF_WINDOW, refiner_mod.WINDOW)
    refiner_mod.HALF_WINDOW, refiner_mod.WINDOW = half_window, 2 * half_window + 1
    try:
        yield
    finally:
        refiner_mod.HALF_WINDOW, refiner_mod.WINDOW = old


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def git_state() -> dict[str, Any]:
    return {"revision": _git("rev-parse", "HEAD"), "dirty": bool(_git("status", "--porcelain"))}


def protocol_sha() -> str:
    spec = {k: [v[0], v[1]] for k, v in CONFIGS.items()}
    blob = json.dumps({"configs": spec, "k": K_FOLDS, "schema": SCHEMA_VERSION}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def input_hashes(meta: dict[str, Any], utterance_files: list[Path]) -> dict[str, Any]:
    """Run outputs, sample, split and the reference annotations of every training clip."""
    files = {
        p: _sha_file(PROJECT_ROOT / p)
        for p in (
            f"{RUN.as_posix()}/benchmark_predictions.json",
            f"{RUN.as_posix()}/benchmark_results.json",
            f"{RUN.as_posix()}/manifest.json",
            meta["sample"]["path"],
            SPLIT.as_posix(),
        )
    }
    per_file = hashlib.sha256()
    for f in sorted(utterance_files):
        per_file.update(f.as_posix().encode() + b"\0" + _sha_file(f).encode() + b"\n")
    return {
        "files": files,
        "train_audio_and_references": {
            "n_files": len(utterance_files),
            "sha256_of_sorted_file_hashes": per_file.hexdigest(),
        },
    }


def code_hashes() -> dict[str, str]:
    return {p: _sha_file(PROJECT_ROOT / p) for p in CODE_FILES}


def train_config(name: str) -> tuple[TrainConfig, int]:
    overrides, half = CONFIGS[name]
    return dataclasses.replace(TrainConfig(), **overrides), half


def run_config(name: str, bounds, mels) -> dict[str, Any]:
    cfg, half = train_config(name)
    t0 = time.perf_counter()
    with window_override(half):
        cv = cross_validate(bounds, mels, K_FOLDS, cfg)
    return {
        "name": name,
        "config": dataclasses.asdict(cfg),
        "half_window_frames": half,
        "window_ms": half * 5,
        "seconds": round(time.perf_counter() - t0, 1),
        **cv,
        "decision": decide(cv),
    }


def compare_with_original(baseline: dict[str, Any], original: dict[str, Any]) -> list[str]:
    """Differences between the baseline CV and the original CV report (empty = exact)."""
    diffs: list[str] = []

    def walk(a: Any, b: Any, path: str) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            for k in sorted(set(a) | set(b)):
                if k in ("seconds",):
                    continue
                if k not in a or k not in b:
                    diffs.append(f"{path}/{k}: missing")
                else:
                    walk(a[k], b[k], f"{path}/{k}")
        elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
            for i, (x, y) in enumerate(zip(a, b, strict=True)):
                walk(x, y, f"{path}[{i}]")
        elif isinstance(a, float) or isinstance(b, float):
            if a is None or b is None or abs(float(a) - float(b)) > TOLERANCE:
                diffs.append(f"{path}: {a} != {b}")
        elif a != b:
            diffs.append(f"{path}: {a!r} != {b!r}")

    for key in ("scores", "tests", "quality_estimation", "decision"):
        walk(baseline[key], original[key], key)
    walk(
        [{k: v for k, v in f.items() if k != "seconds"} for f in baseline["folds"]],
        [{k: v for k, v in f.items() if k != "seconds"} for f in original["folds"]],
        "folds",
    )
    return diffs


def summarize(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    base = results["baseline"]["scores"]["brqe"]
    rows = {}
    for name, r in results.items():
        brqe, const = r["scores"]["brqe"], r["scores"]["const"]
        rows[name] = {
            "window_ms": r["window_ms"],
            **{k: r["config"][k] for k in ("epochs", "hidden", "cls_weight")},
            **{
                f"{key}_mae_ms": brqe[key]["mae_ms"]
                for key in ("word_A", "word_B", "phone_A", "phone_B")
            },
            **{f"{key}_acc_20ms": brqe[key]["acc_20ms"] for key in ("word_A", "word_B")},
            **{
                f"delta_{key}_mae_ms_vs_baseline": round(
                    brqe[key]["mae_ms"] - base[key]["mae_ms"], 3
                )
                for key in ("word_A", "word_B")
            },
            **{
                f"gain_{key}_mae_ms_vs_const": round(const[key]["mae_ms"] - brqe[key]["mae_ms"], 3)
                for key in ("word_A", "word_B")
            },
            "p_brqe_vs_const_word_A": r["tests"]["word_A"]["brqe_vs_const"]["p_value"],
            "p_brqe_vs_const_word_B": r["tests"]["word_B"]["brqe_vs_const"]["p_value"],
            "qe_roc_auc_word": r["quality_estimation"]["word"]["roc_auc"],
            "rule_6_5_both_scenarios": r["decision"]["refinement_enters_proposed"],
            "seconds": r["seconds"],
        }
    deltas = [
        abs(v[f"delta_{k}_mae_ms_vs_baseline"]) for v in rows.values() for k in ("word_A", "word_B")
    ]
    return {
        "rows": rows,
        "max_abs_word_mae_delta_vs_baseline_ms": max(deltas),
        "rule_6_5_holds": f"{sum(v['rule_6_5_both_scenarios'] for v in rows.values())}/{len(rows)}",
    }


def _load_results(out: Path) -> dict[str, dict[str, Any]]:
    res = {}
    for name in CONFIGS:
        f = out / f"{name}.json"
        if f.is_file():
            res[name] = json.loads(f.read_text(encoding="utf-8"))
    return res


def run(out: Path) -> int:
    before = git_state()
    if before["dirty"]:
        raise SensitivityError("Worktree is dirty; commit first (protocol: clean tree only)")
    out.mkdir(parents=True, exist_ok=True)
    psha = protocol_sha()
    bounds, mels, meta = load_training_boundaries(RUN, SPLIT)
    utts = sorted({b.utt for b in bounds})
    corpus_dir = PROJECT_ROOT / "data/corpora/buckeye"
    utterance_files = [corpus_dir / f"{u}.{ext}" for u in utts for ext in ("wav", "TextGrid")]
    provenance = {
        "protocol": "docs/BRQE_SENSITIVITY_PROTOCOL.md",
        "protocol_sha256": psha,
        "git_before": before,
        "code": code_hashes(),
        "inputs": input_hashes(meta, utterance_files),
        "training_input": meta,
        "n_boundaries": len(bounds),
        "n_matched": sum(b.ref is not None for b in bounds),
    }
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(f"[*] {provenance['n_matched']} matched boundaries, protocol {psha[:12]}", flush=True)

    original = json.loads(ORIGINAL_CV.read_text(encoding="utf-8"))
    for name in CONFIGS:
        f = out / f"{name}.json"
        if f.is_file() and json.loads(f.read_text(encoding="utf-8")).get("protocol_sha256") == psha:
            print(f"[=] {name}: already done", flush=True)
            continue
        print(f"[*] {name}: start {datetime.datetime.now():%H:%M:%S}", flush=True)
        r = run_config(name, bounds, mels)
        r.update(
            protocol_sha256=psha, git_revision=before["revision"], schema_version=SCHEMA_VERSION
        )
        f.write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")
        brqe = r["scores"]["brqe"]
        print(
            f"[+] {name}: word MAE A {brqe['word_A']['mae_ms']} B {brqe['word_B']['mae_ms']}, "
            f"rule 6.5 {r['decision']['refinement_enters_proposed']}, {r['seconds']} s",
            flush=True,
        )
        if name == "baseline":
            diffs = compare_with_original(r, original)
            if diffs:
                raise SensitivityError(f"Baseline does not reproduce the original CV: {diffs[:10]}")
            print("[OK] baseline reproduces the original CV exactly", flush=True)

    results = _load_results(out)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "protocol_sha256": psha,
        "baseline_reproduces_original_cv": not compare_with_original(results["baseline"], original),
        **summarize(results),
        "git_before": before,
        "git_after": git_state(),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: summary[k] for k in ("max_abs_word_mae_delta_vs_baseline_ms", "rule_6_5_holds")}
        )
    )
    return 0


def verify(out: Path) -> int:
    """Independent re-check from the written files (run as a separate process)."""
    problems: list[str] = []
    prov = json.loads((out / "provenance.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    if prov["protocol_sha256"] != protocol_sha():
        problems.append("protocol changed since the run")
    for p, h in prov["code"].items():
        if p != "scripts/brqe_sensitivity.py" and _sha_file(PROJECT_ROOT / p) != h:
            problems.append(f"code changed: {p}")
    for p, h in prov["inputs"]["files"].items():
        if _sha_file(PROJECT_ROOT / p) != h:
            problems.append(f"input changed: {p}")
    results = _load_results(out)
    if set(results) != set(CONFIGS):
        problems.append(f"missing configurations: {sorted(set(CONFIGS) - set(results))}")
    for name, r in results.items():
        cfg, half = train_config(name)
        if r["config"] != dataclasses.asdict(cfg) or r["half_window_frames"] != half:
            problems.append(f"{name}: configuration differs from protocol")
        if r["decision"] != decide(r):
            problems.append(f"{name}: decision does not follow from its numbers")
        if r["protocol_sha256"] != prov["protocol_sha256"]:
            problems.append(f"{name}: written under another protocol")
    original = json.loads(ORIGINAL_CV.read_text(encoding="utf-8"))
    if compare_with_original(results["baseline"], original):
        problems.append("baseline does not reproduce the original CV")
    recomputed = summarize(results)
    for k in ("rows", "max_abs_word_mae_delta_vs_baseline_ms", "rule_6_5_holds"):
        if json.dumps(recomputed[k], sort_keys=True) != json.dumps(summary[k], sort_keys=True):
            problems.append(f"summary field {k} differs from recomputation")
    if summary["git_before"]["dirty"] or summary["git_after"]["dirty"]:
        problems.append("worktree was dirty before or after the run")
    verdict = {
        "verified": not problems,
        "problems": problems,
        "checked_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    (out / "verify.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdict, indent=2))
    return 0 if not problems else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--verify", action="store_true")
    args = p.parse_args(argv)
    try:
        return verify(args.output_dir) if args.verify else run(args.output_dir)
    except SensitivityError as err:
        sys.stderr.write(f"[-] Sensitivity Error: {err}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
