"""Train and cross-validate the BRQE refiner on a benchmark run over TRAIN speakers only.

Input is a run directory written by speech_benchmark.py (benchmark_predictions.json
and benchmark_results.json with config.sample) whose utterances all belong to the
train group of the speaker split. The script refuses a run that contains any test
speaker.

  --cv K      speaker-grouped K-fold cross-validation inside the train speakers:
              per-speaker word/phone MAE and Acc@20ms for none / const / brqe,
              paired Wilcoxon brqe vs const over speakers, QE ROC-AUC / PR-AUC.
  --final DIR train const and brqe on all train speakers and save them to DIR.

Example (docs/IMPROVEMENT_PLAN.md §6.5):
  python scripts/train_brqe.py --run reports/brqe_train_run \
      --split reports/buckeye_split_20260401.json --cv 5 --report reports/brqe_cv_20260401.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.speech_benchmark import (  # noqa: E402
    BenchmarkError,
    load_textgrid_utterances,
    load_utterance_sample,
    select_utterances,
)
from subtitle_workbench.metrics import paired_wilcoxon_test  # noqa: E402
from subtitle_workbench.models import PhonemeCue, WordToken  # noqa: E402
from subtitle_workbench.provenance import code_provenance, sha256  # noqa: E402
from subtitle_workbench.refiner import (  # noqa: E402
    ERROR_THRESHOLD_S,
    Boundary,
    BRQERefiner,
    ConstantRefiner,
    MelExtractor,
    TrainConfig,
    boundaries_for_utterance,
    pr_auc,
    read_wav_mono,
    roc_auc,
)

SCENARIO_MODES = {"A": "A2_proposed", "B": "B2_proposed"}


def load_training_boundaries(run: Path, split_path: Path) -> tuple[list[Boundary], dict, dict]:
    results = json.loads((run / "benchmark_results.json").read_text(encoding="utf-8"))
    preds = json.loads((run / "benchmark_predictions.json").read_text(encoding="utf-8"))
    sample_cfg = results["config"].get("sample")
    if not sample_cfg:
        raise BenchmarkError("Run has no config.sample; cannot verify its speakers")
    sample = load_utterance_sample(sample_cfg["path"])
    if sha256(sample_cfg["path"]) != sample_cfg["sha256"]:
        raise BenchmarkError("Sample file changed since the run")
    split = json.loads(split_path.read_text(encoding="utf-8"))
    train, test = set(split["train_speakers"]), set(split["test_speakers"])
    corpus = results["corpus"]
    utts = select_utterances(
        load_textgrid_utterances(Path(f"data/corpora/{corpus}"), corpus), sample["utterance_ids"]
    )
    leaked = {u.speaker_id for u in utts} & test
    if leaked:
        raise BenchmarkError(f"Run contains TEST speakers {sorted(leaked)}; refusing to train")
    if not {u.speaker_id for u in utts} <= train:
        raise BenchmarkError("Run contains speakers outside the train group")

    mel = MelExtractor()
    mels = {u.id: mel(read_wav_mono(u.wav_path)) for u in utts}
    bounds: list[Boundary] = []
    for scenario, mode in SCENARIO_MODES.items():
        for u in utts:
            p = preds["modes"][mode].get(u.id)
            if not p or p["status"] != "ok":
                continue
            words = [
                WordToken(f"w{i}", t, n, s, e, 1.0) for i, (t, n, s, e, *_) in enumerate(p["words"])
            ]
            phones = [PhonemeCue(ph, s, e, 1.0) for ph, s, e in (p["phones"] or [])]
            bounds += boundaries_for_utterance(
                u.id, scenario, words, phones, u.ref_words, u.ref_phones, u.speaker_id
            )
    meta = {
        "run": run.as_posix(),
        "sample": sample_cfg,
        "split": {"path": split_path.as_posix(), "sha256": sha256(split_path)},
        "run_code": json.loads((run / "manifest.json").read_text(encoding="utf-8"))["code"],
        "n_utterances": len(utts),
        "n_speakers": len({u.speaker_id for u in utts}),
    }
    return bounds, mels, meta


def _scores(bounds: list[Boundary], shift: np.ndarray) -> dict[str, Any]:
    """Per (tier, scenario): pooled MAE / Acc@20ms and per-speaker MAE."""
    out: dict[str, Any] = {}
    err = np.array([abs(b.ref - (b.time + d)) for b, d in zip(bounds, shift, strict=True)]) * 1000
    for tier in ("word", "phone"):
        for sc in ("A", "B"):
            idx = [i for i, b in enumerate(bounds) if b.kind.startswith(tier) and b.scenario == sc]
            if not idx:
                continue
            e = err[idx]
            per_spk: dict[str, list[float]] = {}
            for i in idx:
                per_spk.setdefault(bounds[i].speaker, []).append(err[i])
            out[f"{tier}_{sc}"] = {
                "mae_ms": round(float(e.mean()), 3),
                "acc_20ms": round(float(np.mean(e <= 20.0) * 100), 2),
                "n_boundaries": len(idx),
                "per_speaker_mae": {k: float(np.mean(v)) for k, v in sorted(per_spk.items())},
            }
    return out


def cross_validate(bounds, mels, k: int, cfg: TrainConfig) -> dict[str, Any]:
    matched = [b for b in bounds if b.ref is not None]
    speakers = sorted({b.speaker for b in matched})
    folds = [speakers[i::k] for i in range(k)]
    shifts = {m: np.zeros(len(matched)) for m in ("none", "const", "brqe")}
    probs = np.zeros(len(matched))
    fold_log = []
    for f, held in enumerate(folds):
        held_set = set(held)
        tr = [b for b in matched if b.speaker not in held_set]
        te_idx = [i for i, b in enumerate(matched) if b.speaker in held_set]
        te = [matched[i] for i in te_idx]
        t0 = time.perf_counter()
        const = ConstantRefiner().fit(tr)
        brqe = BRQERefiner(cfg).fit(tr, mels)
        shifts["const"][te_idx] = const.predict(te)[0]
        sh, pr = brqe.predict(te, mels)
        shifts["brqe"][te_idx] = sh
        probs[te_idx] = pr
        fold_log.append(
            {
                "fold": f,
                "held_out": held,
                "n_train": len(tr),
                "seconds": round(time.perf_counter() - t0, 1),
            }
        )
        print(f"[*] fold {f}: held out {held}, {fold_log[-1]['seconds']} s", flush=True)

    scores = {m: _scores(matched, s) for m, s in shifts.items()}
    tests = {}
    for key in scores["none"]:
        spk = sorted(scores["none"][key]["per_speaker_mae"])
        c = [scores["const"][key]["per_speaker_mae"][s] for s in spk]
        b = [scores["brqe"][key]["per_speaker_mae"][s] for s in spk]
        n = [scores["none"][key]["per_speaker_mae"][s] for s in spk]
        r_c, r_n = paired_wilcoxon_test(c, b), paired_wilcoxon_test(n, b)
        tests[key] = {
            "n_speakers": len(spk),
            "brqe_vs_const": {
                "p_value": r_c.p_value,
                "cliffs_delta": r_c.cliffs_delta,
                "speakers_improved": int(sum(x < y for x, y in zip(b, c, strict=True))),
            },
            "brqe_vs_none": {
                "p_value": r_n.p_value,
                "cliffs_delta": r_n.cliffs_delta,
                "speakers_improved": int(sum(x < y for x, y in zip(b, n, strict=True))),
            },
        }
    labels = np.array([abs(b.ref - b.time) > ERROR_THRESHOLD_S for b in matched])
    qe = {}
    for tier in ("word", "phone"):
        idx = [i for i, b in enumerate(matched) if b.kind.startswith(tier)]
        qe[tier] = {
            "roc_auc": roc_auc(labels[idx], probs[idx]),
            "pr_auc": pr_auc(labels[idx], probs[idx]),
            "positive_rate": float(labels[idx].mean()),
        }
    for m in scores:
        for v in scores[m].values():
            v.pop("per_speaker_mae")
    return {"folds": fold_log, "scores": scores, "tests": tests, "quality_estimation": qe}


def decide(cv: dict[str, Any]) -> dict[str, Any]:
    """Pre-registered rule (IMPROVEMENT_PLAN §6.5): refinement enters Proposed if BRQE lowers
    word MAE vs the constant refiner in both scenarios with p < 0.05 over train speakers."""
    ok = {}
    for sc in ("A", "B"):
        key = f"word_{sc}"
        t = cv["tests"].get(key)
        better = cv["scores"]["brqe"][key]["mae_ms"] < cv["scores"]["const"][key]["mae_ms"]
        ok[sc] = bool(t and better and t["brqe_vs_const"]["p_value"] < 0.05)
    return {"refinement_enters_proposed": all(ok.values()), "per_scenario": ok}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cross-validate or train BRQE on train speakers.")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--split", type=Path, required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--cv", type=int)
    g.add_argument("--final", type=Path)
    p.add_argument("--report", type=Path, default=None)
    p.add_argument("--epochs", type=int, default=TrainConfig.epochs)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = TrainConfig(epochs=args.epochs)
    t0 = time.perf_counter()
    try:
        bounds, mels, meta = load_training_boundaries(args.run, args.split)
    except BenchmarkError as err:
        sys.stderr.write(f"[-] BRQE Error: {err}\n")
        return 1
    n_matched = sum(b.ref is not None for b in bounds)
    print(
        f"[*] {len(bounds)} boundaries, {n_matched} matched, {meta['n_speakers']} speakers",
        flush=True,
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "created_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "code": code_provenance(),
        "input": meta,
        "config": cfg.__dict__,
        "n_boundaries": len(bounds),
        "n_matched": n_matched,
    }
    if args.cv:
        cv = cross_validate(bounds, mels, args.cv, cfg)
        report.update({"cv_k": args.cv, **cv, "decision": decide(cv)})
        for m, sc in cv["scores"].items():
            print(m, {k: (v["mae_ms"], v["acc_20ms"]) for k, v in sc.items()})
        print("QE", cv["quality_estimation"])
        print("decision", report["decision"])
    else:
        matched = [b for b in bounds if b.ref is not None]
        const = ConstantRefiner().fit(matched)
        brqe = BRQERefiner(cfg).fit(matched, mels)
        args.final.mkdir(parents=True, exist_ok=True)
        (args.final / "const_offsets.json").write_text(
            json.dumps({"offsets": const.offsets, "trained_on": meta}, indent=2) + "\n",
            encoding="utf-8",
        )
        report["weights_sha256"] = brqe.save(args.final / "brqe.pt", extra={"trained_on": meta})
        report["const_offsets"] = const.offsets
        print(f"[OK] saved to {args.final}")
    report["seconds"] = round(time.perf_counter() - t0, 1)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
