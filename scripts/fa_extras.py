"""Boundary groups, F1 tolerance sweep and duration error (docs/FA_EXTRAS_PROTOCOL.md).

No model is run. Frozen E1 predictions are read-only; results go to reports/fa_extras_20261123/.

    python scripts/fa_extras.py
"""

from __future__ import annotations

import datetime
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.f1_analysis import MODES  # noqa: E402
from scripts.p1_p4_analyses import corpus, ref_matches, run_inputs  # noqa: E402
from scripts.verify_frozen_evidence import read_json  # noqa: E402
from subtitle_workbench.metrics import BOUNDARY_EPSILON_MS  # noqa: E402
from subtitle_workbench.models import WordToken  # noqa: E402
from subtitle_workbench.provenance import code_provenance  # noqa: E402

OUT = ROOT / "reports" / "fa_extras_20261123"
SEED, RESAMPLES = 42, 2000
TOLS_MS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
GROUPS = ["M2I", "M1I", "M0I", "M1B", "M0B", "M1E", "M0E"]


# ------------------------------------------------------------------ per clip
def clip_boundaries(
    pred: list[WordToken] | None, ref: list[WordToken]
) -> tuple[list[tuple[str, float]], list[tuple[float, float, float]], int]:
    """Reference boundaries as (group, |error| ms or nan), matched words' signed
    (start, end, duration) errors in ms, and the number of predicted boundaries."""
    matches = ref_matches(pred, ref) if pred else {}
    last = len(ref) - 1
    bounds: list[tuple[str, float]] = []
    signed: list[tuple[float, float, float]] = []
    for r_i, g in enumerate(ref):
        own = r_i in matches
        p = matches[r_i][1] if own else None
        es = (p.start - g.start) * 1000.0 if own else float("nan")
        ee = (p.end - g.end) * 1000.0 if own else float("nan")
        if own:
            signed.append((es, ee, ee - es))
        for side, err, nb in (("start", es, r_i - 1), ("end", ee, r_i + 1)):
            edge = (side == "start" and r_i == 0) or (side == "end" and r_i == last)
            if edge:
                group = ("M1" if own else "M0") + ("B" if side == "start" else "E")
            else:
                n = int(own) + int(nb in matches)
                group = f"M{n}I"
            bounds.append((group, abs(err) if own else float("nan")))
    return bounds, signed, 2 * len(pred) if pred else 0


def within(err: np.ndarray, tol_ms: float) -> np.ndarray:
    return np.nan_to_num(err, nan=np.inf) <= tol_ms + BOUNDARY_EPSILON_MS


# ------------------------------------------------------------------ statistics
def draws(n_speakers: int) -> np.ndarray:
    return np.random.default_rng(SEED).integers(0, n_speakers, (RESAMPLES, n_speakers))


def ci(values: np.ndarray) -> list[float]:
    return np.percentile(values, [2.5, 97.5]).tolist()


def f1(h: float, n_pred: float, n_ref: float) -> float:
    return 0.0 if h == 0 else 2.0 * h / (n_pred + n_ref)


# ------------------------------------------------------------------ corpus
def collect(mode: str, preds, ok, ids, utts) -> dict[str, Any]:
    speakers = sorted({utts[u].speaker_id for u in ids})
    s_index = {s: i for i, s in enumerate(speakers)}
    grp, err, spk_b = [], [], []
    sgn, spk_w = [], []
    n_pred = np.zeros(len(speakers))
    n_failed = 0
    for uid in sorted(ids):
        item = preds[mode].get(uid)
        is_ok = uid in ok[mode] and isinstance(item, list)
        n_failed += not is_ok
        b, s, npb = clip_boundaries(item if is_ok else None, utts[uid].ref_words)
        si = s_index[utts[uid].speaker_id]
        n_pred[si] += npb
        grp += [g for g, _ in b]
        err += [e for _, e in b]
        spk_b += [si] * len(b)
        sgn += s
        spk_w += [si] * len(s)
    return {
        "speakers": speakers,
        "group": np.array(grp),
        "err": np.array(err, dtype=float),
        "spk_b": np.array(spk_b),
        "signed": np.array(sgn, dtype=float).reshape(-1, 3),
        "spk_w": np.array(spk_w),
        "n_pred": n_pred,
        "n_failed": n_failed,
    }


def groups_table(d: dict[str, Any]) -> dict[str, Any]:
    n = len(d["group"])
    out = {}
    for g in GROUPS:
        m = d["group"] == g
        e = d["err"][m]
        matched = e[~np.isnan(e)]
        out[g] = {
            "n": int(m.sum()),
            "share": float(m.sum() / n),
            "recall20": float(within(e, 20).mean()) if m.any() else None,
            "contribution20": float(within(e, 20).sum() / n),
            "mae_ms_matched": float(matched.mean()) if matched.size else None,
            "n_matched": int(matched.size),
        }
    return out


def sweep(d: dict[str, Any], dr: np.ndarray) -> dict[str, Any]:
    n_spk = len(d["speakers"])
    n_ref = np.bincount(d["spk_b"], minlength=n_spk).astype(float)
    out = {}
    for tol in TOLS_MS:
        hits = np.bincount(d["spk_b"], weights=within(d["err"], tol), minlength=n_spk)
        boot = [f1(hits[k].sum(), d["n_pred"][k].sum(), n_ref[k].sum()) for k in dr]
        h, npd, nr = hits.sum(), d["n_pred"].sum(), n_ref.sum()
        out[str(tol)] = {
            "precision": float(h / npd) if npd else None,
            "recall": float(h / nr),
            "f1": f1(h, npd, nr),
            "f1_ci_95": ci(np.array(boot)),
        }
    return out


def signed_errors(d: dict[str, Any], dr: np.ndarray) -> dict[str, Any]:
    n_spk = len(d["speakers"])
    sg, sw = d["signed"], d["spk_w"]
    cnt = np.bincount(sw, minlength=n_spk).astype(float)
    out: dict[str, Any] = {"n_words": int(len(sg))}
    for j, key in enumerate(("start", "end", "duration")):
        sums = np.bincount(sw, weights=sg[:, j], minlength=n_spk)
        boot = [sums[k].sum() / cnt[k].sum() for k in dr]
        out[f"mean_signed_{key}_ms"] = float(sg[:, j].mean())
        out[f"mean_signed_{key}_ms_ci_95"] = ci(np.array(boot))
    out["mean_abs_duration_ms"] = float(np.abs(sg[:, 2]).mean())
    out["boundary_mae_ms"] = float(np.abs(sg[:, :2]).mean())
    return out


def analyze_corpus(name: str) -> dict[str, Any]:
    _, preds, ok, ids = run_inputs(name)
    utts = corpus(name)
    f1_ref = read_json("reports/f1_20261123/f1_results.json")["corpora"][name]["modes"]
    e1 = read_json("reports/e1_analysis_20261102/analysis.json")["corpora"][name]["modes"]
    out: dict[str, Any] = {"modes": {}, "sanity": []}
    dr = None
    for mode in MODES:
        d = collect(mode, preds, ok, ids, utts)
        if dr is None:
            dr = draws(len(d["speakers"]))
        sw = sweep(d, dr)
        se = signed_errors(d, dr)
        for tol, key in ((20, "edge20"), (50, "edge50")):
            a, b = sw[str(tol)]["f1"], f1_ref[mode][key]["f1"]
            out["sanity"].append(
                {
                    "check": f"{mode} F1@{tol}",
                    "here": a,
                    "f1_results": b,
                    "pass": abs(a - b) <= 1e-9,
                }
            )
        for key in ("start", "end"):
            a = se[f"mean_signed_{key}_ms"]
            b = e1[mode]["breakdowns"][f"word/{key}"]["mean_signed_error_ms"]
            out["sanity"].append(
                {"check": f"{mode} signed {key}", "here": a, "e1": b, "pass": abs(a - b) <= 0.01}
            )
        out["modes"][mode] = {
            "n_failed_clips": d["n_failed"],
            "groups": groups_table(d),
            "f1_sweep": sw,
            "signed": se,
        }
    return out


def main() -> int:
    started = time.time()
    payload: dict[str, Any] = {
        "protocol": "docs/FA_EXTRAS_PROTOCOL.md",
        "created_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "provenance": code_provenance(),
        "corpora": {name: analyze_corpus(name) for name in ("buckeye", "timit")},
    }
    failed = [s for c in payload["corpora"].values() for s in c["sanity"] if not s["pass"]]
    payload["sanity_pass"] = not failed
    payload["runtime_s"] = round(time.time() - started, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fa_extras.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    if failed:
        print("SANITY FAILED:", json.dumps(failed, indent=2))
        return 1
    print(f"done in {payload['runtime_s']} s -> {OUT / 'fa_extras.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
