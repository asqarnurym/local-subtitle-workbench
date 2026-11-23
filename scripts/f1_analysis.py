"""Boundary F1 that charges missed and inserted words (docs/F1_PROTOCOL.md).

No model is run. Frozen E1 predictions are read-only; results go to reports/f1_20261123/.

    python scripts/f1_analysis.py
"""

from __future__ import annotations

import datetime
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.p1_p4_analyses import corpus, ref_matches, run_inputs  # noqa: E402
from scripts.s1_long_recordings import paired_test  # noqa: E402
from scripts.s2_s3_substudies import holm  # noqa: E402
from scripts.verify_frozen_evidence import require  # noqa: E402
from subtitle_workbench.metrics import BOUNDARY_EPSILON_MS  # noqa: E402
from subtitle_workbench.models import WordToken  # noqa: E402
from subtitle_workbench.provenance import code_provenance  # noqa: E402

OUT = ROOT / "reports" / "f1_20261123"
SEED, RESAMPLES = 42, 2000
MODES = [
    "B0_whisper",
    "B1_whisper_ctc",
    "B2_proposed",
    "B2_const",
    "B2_brqe",
    "A1_ctc",
    "A2_proposed",
    "A2_const",
    "A2_brqe",
]
# (base, condition): the difference is condition - base, higher F1 is better.
PAIRS = [
    ("B2_proposed", "A2_proposed"),
    ("B2_const", "B2_brqe"),
    ("A2_const", "A2_brqe"),
    ("A1_ctc", "A2_proposed"),
    ("B1_whisper_ctc", "B2_proposed"),
]
COUNT_KEYS = ("hits_edge20", "hits_edge50", "hits_ctx20", "n_pred_bd", "n_ref_bd")


def within(err_ms: float, tol_ms: float) -> bool:
    return err_ms <= tol_ms + BOUNDARY_EPSILON_MS


def clip_counts(pred: list[WordToken] | None, ref: list[WordToken]) -> dict[str, int]:
    """Boundary hits and denominators of one clip; pred None means the mode failed."""
    out = {k: 0 for k in COUNT_KEYS}
    out["n_ref_bd"] = 2 * len(ref)
    if not pred:
        return out
    out["n_pred_bd"] = 2 * len(pred)
    matches = ref_matches(pred, ref)  # ref index -> (pred index, pred word)
    r_of_p = {p_i: r_i for r_i, (p_i, _) in matches.items()}
    last_r, last_p = len(ref) - 1, len(pred) - 1
    for r_i, (p_i, p) in matches.items():
        g = ref[r_i]
        e_start = abs(p.start - g.start) * 1000.0
        e_end = abs(p.end - g.end) * 1000.0
        start_ctx = (r_i == 0 and p_i == 0) or (
            r_i > 0 and p_i > 0 and r_of_p.get(p_i - 1) == r_i - 1
        )
        end_ctx = (r_i == last_r and p_i == last_p) or (
            r_i < last_r and p_i < last_p and r_of_p.get(p_i + 1) == r_i + 1
        )
        for err, ctx in ((e_start, start_ctx), (e_end, end_ctx)):
            if within(err, 20.0):
                out["hits_edge20"] += 1
                if ctx:
                    out["hits_ctx20"] += 1
            if within(err, 50.0):
                out["hits_edge50"] += 1
    return out


def f1_from(c: dict[str, int], hits_key: str) -> dict[str, float | None]:
    h, n_pred, n_ref = c[hits_key], c["n_pred_bd"], c["n_ref_bd"]
    p = h / n_pred if n_pred else None
    r = h / n_ref if n_ref else None
    f = None
    if n_pred and n_ref:
        f = 0.0 if h == 0 else 2.0 * p * r / (p + r)
    return {"precision": p, "recall": r, "f1": f}


def add(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    return {k: a.get(k, 0) + b[k] for k in COUNT_KEYS}


def speaker_bootstrap_f1(by_spk: dict[str, dict[str, int]], hits_key: str) -> list[float]:
    names = sorted(by_spk)
    mat = np.array(
        [[by_spk[s][hits_key], by_spk[s]["n_pred_bd"], by_spk[s]["n_ref_bd"]] for s in names]
    )
    rng = np.random.default_rng(SEED)
    vals = []
    for _ in range(RESAMPLES):
        h, n_p, n_r = mat[rng.integers(0, len(names), len(names))].sum(axis=0)
        vals.append(0.0 if h == 0 else 2.0 * h / (n_p + n_r))
    return np.percentile(vals, [2.5, 97.5]).tolist()


def sanity(results: dict, mode: str, per_clip: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Matched-word Acc@20 and matched count must equal the frozen values."""
    matched = sum(v["n_matched"] for v in per_clip.values() if v["ok"])
    hits = sum(v["hits_edge20"] for v in per_clip.values() if v["ok"])
    acc = 100.0 * hits / (2 * matched) if matched else float("nan")
    wm = results["modes"][mode]["word_metrics"]
    ok = abs(acc - wm["acc_20ms"]) <= 0.01 and matched == wm["num_matched"]
    return {
        "mode": mode,
        "acc20_matched_recomputed": acc,
        "acc20_frozen": wm["acc_20ms"],
        "num_matched_recomputed": matched,
        "num_matched_frozen": wm["num_matched"],
        "pass": ok,
    }


def analyze_corpus(name: str) -> dict[str, Any]:
    results, preds, ok, ids = run_inputs(name)
    utts = corpus(name)
    require(len(ids) == results["n_utterances"], f"{name}: manifest and results disagree")
    out: dict[str, Any] = {"n_clips": len(ids), "modes": {}, "sanity": []}
    spk_values: dict[str, dict[str, dict[str, float | None]]] = {}
    for mode in MODES:
        per_clip: dict[str, dict[str, Any]] = {}
        by_spk: dict[str, dict[str, int]] = defaultdict(dict)
        total: dict[str, int] = {}
        n_failed = 0
        for uid in sorted(ids):
            ref = utts[uid].ref_words
            item = preds[mode].get(uid)
            is_ok = uid in ok[mode] and isinstance(item, list)
            n_failed += not is_ok
            c = clip_counts(item if is_ok else None, ref)
            n_matched = len(ref_matches(item, ref)) if is_ok and item else 0
            per_clip[uid] = {**c, "ok": is_ok, "n_matched": n_matched}
            spk = utts[uid].speaker_id
            by_spk[spk] = add(by_spk[spk], c)
            total = add(total, c)
        out["sanity"].append(sanity(results, mode, per_clip))
        frozen_acc = results["modes"][mode]["word_metrics"]["acc_20ms"] / 100.0
        edge20 = f1_from(total, "hits_edge20")
        out["modes"][mode] = {
            "n_failed_clips": n_failed,
            "counts": total,
            "edge20": {**edge20, "f1_ci_95": speaker_bootstrap_f1(by_spk, "hits_edge20")},
            "edge50": {
                **f1_from(total, "hits_edge50"),
                "f1_ci_95": speaker_bootstrap_f1(by_spk, "hits_edge50"),
            },
            "ctx20": {
                **f1_from(total, "hits_ctx20"),
                "f1_ci_95": speaker_bootstrap_f1(by_spk, "hits_ctx20"),
            },
            "frozen_acc20_matched": frozen_acc,
            "unmatched_cost_acc20_minus_recall20": frozen_acc - edge20["recall"],
            "speaker_f1_edge20": {
                s: f1_from(c, "hits_edge20")["f1"] for s, c in sorted(by_spk.items())
            },
        }
        spk_values[mode] = out["modes"][mode]["speaker_f1_edge20"]
    tests = {f"{c} - {b}": paired_test(spk_values[b], spk_values[c]) for b, c in PAIRS}
    adj = holm({k: v["p_value_raw"] for k, v in tests.items()})
    for k in tests:
        tests[k]["p_value_holm"] = adj[k]
        tests[k]["note"] = "difference is condition - base in F1 units (paired_test labels it _ms)"
    out["tests_edge20"] = tests
    return out


def main() -> int:
    started = time.time()
    payload: dict[str, Any] = {
        "protocol": "docs/F1_PROTOCOL.md",
        "created_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "provenance": code_provenance(),
        "corpora": {name: analyze_corpus(name) for name in ("buckeye", "timit")},
    }
    failed = [s for c in payload["corpora"].values() for s in c["sanity"] if not s["pass"]]
    payload["sanity_pass"] = not failed
    payload["runtime_s"] = round(time.time() - started, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "f1_results.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    if failed:
        print("SANITY FAILED:", json.dumps(failed, indent=2))
        return 1
    print(f"done in {payload['runtime_s']} s -> {OUT / 'f1_results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
