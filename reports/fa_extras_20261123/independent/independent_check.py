"""Independent re-implementation of docs/FA_EXTRAS_PROTOCOL.md (does not use scripts/fa_extras.py)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from speech_benchmark import load_textgrid_utterances, load_timit_utterances  # noqa: E402
from verify_frozen_evidence import local_path  # noqa: E402
from subtitle_workbench.metrics import BOUNDARY_EPSILON_MS, _align_token_sequences  # noqa: E402
from subtitle_workbench.models import WordToken  # noqa: E402

MODES = ["B0_whisper", "B1_whisper_ctc", "B2_proposed", "B2_const", "B2_brqe",
         "A1_ctc", "A2_proposed", "A2_const", "A2_brqe"]
GROUPS = ["M2I", "M1I", "M0I", "M1B", "M0B", "M1E", "M0E"]
TOLS = list(range(10, 101, 10))
OUT = Path(__file__).resolve().parent


def ci(values):
    return [float(v) for v in np.percentile(values, [2.5, 97.5])]


def run_corpus(name):
    rep = ROOT / "reports" / name
    preds = json.loads((rep / "benchmark_predictions.json").read_text(encoding="utf-8"))["modes"]
    rows = json.loads((rep / "benchmark_utterances.json").read_text(encoding="utf-8"))
    row_status = {(r["mode"], r["utterance"]): r["status"] for r in rows}
    clips = list(json.loads((rep / "manifest.json").read_text(encoding="utf-8"))["inputs"]["audio_files"])
    if name == "timit":
        utts = load_timit_utterances(local_path("data/corpora/timit"))
    else:
        utts = load_textgrid_utterances(local_path("data/corpora/buckeye"), "buckeye")
    by_id = {u.id: u for u in utts}
    missing = [c for c in clips if c not in by_id]
    assert not missing, missing[:5]
    speakers = sorted({by_id[c].speaker_id for c in clips})
    S = len(speakers)
    spk_idx = {s: i for i, s in enumerate(speakers)}
    draws = np.random.default_rng(42).integers(0, S, (2000, S))
    counts = np.stack([np.bincount(d, minlength=S) for d in draws])  # (2000, S) multiplicities

    out = {}
    for mode in MODES:
        mp = preds[mode]
        n_failed = 0
        g_n = {g: 0 for g in GROUPS}
        g_hit = {g: 0 for g in GROUPS}
        g_err = {g: [] for g in GROUPS}
        # per speaker accumulators
        hits = np.zeros((len(TOLS), S))
        npred = np.zeros(S)
        nref = np.zeros(S)
        es_sum = np.zeros(S); ee_sum = np.zeros(S); ed_sum = np.zeros(S); nw = np.zeros(S)
        all_es, all_ee = [], []
        for clip in clips:
            u = by_id[clip]
            si = spk_idx[u.speaker_id]
            ref = u.ref_words
            R = len(ref)
            nref[si] += 2 * R
            p = mp.get(clip)
            ok = p is not None and p.get("status") == "ok" and row_status.get((mode, clip)) == "ok"
            match = {}  # ref index -> pred token
            if ok:
                ptoks = [WordToken(id=f"p{i}", text=w[0], normalized=w[1], start=float(w[2]),
                                   end=float(w[3]), confidence=float(w[4]) if len(w) > 4 else 1.0)
                         for i, w in enumerate(p["words"])]
                npred[si] += 2 * len(ptoks)
                rpos = {id(t): k for k, t in enumerate(ref)}
                pairs, _ = _align_token_sequences(ptoks, ref)
                for pt, rt in pairs:
                    match[rpos[id(rt)]] = pt
            else:
                n_failed += 1
            for r in range(R):
                pt = match.get(r)
                if pt is not None:
                    es = (pt.start - ref[r].start) * 1000.0
                    ee = (pt.end - ref[r].end) * 1000.0
                    es_sum[si] += es; ee_sum[si] += ee; ed_sum[si] += ee - es; nw[si] += 1
                    all_es.append(es); all_ee.append(ee)
                    for k, tau in enumerate(TOLS):
                        hits[k, si] += (abs(pt.start - ref[r].start) * 1000.0 <= tau + BOUNDARY_EPSILON_MS)
                        hits[k, si] += (abs(pt.end - ref[r].end) * 1000.0 <= tau + BOUNDARY_EPSILON_MS)
                for side in ("s", "e"):
                    nb = r - 1 if side == "s" else r + 1
                    own = pt is not None
                    if 0 <= nb < R:
                        nbm = nb in match
                        g = "M2I" if own and nbm else ("M0I" if not own and not nbm else "M1I")
                    else:
                        g = ("M1" if own else "M0") + ("B" if side == "s" else "E")
                    g_n[g] += 1
                    if own:
                        err = abs((pt.start - ref[r].start) if side == "s" else (pt.end - ref[r].end)) * 1000.0
                        g_err[g].append(err)
                        if err <= 20.0 + BOUNDARY_EPSILON_MS:
                            g_hit[g] += 1
        total = sum(g_n.values())
        assert total == nref.sum()
        groups = {}
        for g in GROUPS:
            n = g_n[g]
            groups[g] = {
                "n": n, "share": n / total, "recall20": (g_hit[g] / n) if n else None,
                "contribution20": g_hit[g] / total,
                "mae_ms_matched": float(np.mean(g_err[g])) if g_err[g] else None,
                "n_matched": len(g_err[g]),
            }
        sweep = {}
        for k, tau in enumerate(TOLS):
            H = hits[k].sum(); P = H / npred.sum(); Rr = H / nref.sum()
            f1 = 2 * P * Rr / (P + Rr) if P + Rr > 0 else 0.0
            bh = counts @ hits[k]; bp = counts @ npred; br = counts @ nref
            with np.errstate(invalid="ignore", divide="ignore"):
                pp = np.where(bp > 0, bh / bp, 0.0); rr = bh / br
                bf = np.where(pp + rr > 0, 2 * pp * rr / (pp + rr), 0.0)
            sweep[str(tau)] = {"precision": float(P), "recall": float(Rr), "f1": float(f1), "f1_ci_95": ci(bf)}
        N = nw.sum()
        bn = counts @ nw
        es_a = np.array(all_es); ee_a = np.array(all_ee)
        signed = {
            "n_words": int(N),
            "mean_signed_start_ms": float(es_sum.sum() / N),
            "mean_signed_start_ms_ci_95": ci((counts @ es_sum) / bn),
            "mean_signed_end_ms": float(ee_sum.sum() / N),
            "mean_signed_end_ms_ci_95": ci((counts @ ee_sum) / bn),
            "mean_signed_duration_ms": float(ed_sum.sum() / N),
            "mean_signed_duration_ms_ci_95": ci((counts @ ed_sum) / bn),
            "mean_abs_duration_ms": float(np.mean(np.abs(ee_a - es_a))),
            "boundary_mae_ms": float(np.mean(np.concatenate([np.abs(es_a), np.abs(ee_a)]))),
        }
        out[mode] = {"n_failed_clips": n_failed, "groups": groups, "f1_sweep": sweep, "signed": signed}
    return {"speakers": speakers, "n_clips": len(clips), "modes": out}


if __name__ == "__main__":
    res = {"corpora": {c: run_corpus(c) for c in ("buckeye", "timit")}}
    (OUT / "independent_check.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("done")
