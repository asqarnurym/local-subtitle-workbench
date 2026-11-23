"""Independent re-implementation of docs/F1_PROTOCOL.md (boundary F1 with misses/insertions).

Written from the protocol text only; does not import scripts/f1_analysis.py.
Run: .venv\\Scripts\\python.exe reports\\f1_20261123\\independent\\independent_check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from speech_benchmark import load_textgrid_utterances, load_timit_utterances  # noqa: E402
from subtitle_workbench.metrics import BOUNDARY_EPSILON_MS, _align_token_sequences  # noqa: E402
from subtitle_workbench.models import WordToken  # noqa: E402

OUT = Path(__file__).resolve().parent
MODES = [
    "B0_whisper", "B1_whisper_ctc", "B2_proposed", "B2_const", "B2_brqe",
    "A1_ctc", "A2_proposed", "A2_const", "A2_brqe",
]
PAIRS = [
    ("A2_proposed", "B2_proposed"),
    ("B2_brqe", "B2_const"),
    ("A2_brqe", "A2_const"),
    ("A2_proposed", "A1_ctc"),
    ("B2_proposed", "B1_whisper_ctc"),
]
METRICS = {"edge20": (20.0, False), "edge50": (50.0, False), "ctx20": (20.0, True)}
N_BOOT = 2000
SEED = 42


def local_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    assert path.is_relative_to(ROOT), relative
    return path


def read_json(relative: str):
    return json.loads(local_path(relative).read_text(encoding="utf-8"))


def load_refs(corpus: str, ids: list[str]) -> dict:
    data_dir = local_path(f"data/corpora/{corpus}")
    if corpus == "timit":
        utts = load_timit_utterances(data_dir)
    else:
        # Load only the needed clips through the project loader by pointing it at a
        # filtered view would require copying; instead load all and filter by id.
        utts = load_textgrid_utterances(data_dir, corpus)
    wanted = set(ids)
    by_id: dict = {}
    for u in utts:
        if u.id in wanted:
            assert u.id not in by_id, f"duplicate reference id {u.id}"
            by_id[u.id] = u
    missing = wanted - by_id.keys()
    assert not missing, f"missing references: {sorted(missing)[:5]}"
    return by_id


def pred_tokens(words) -> list[WordToken]:
    toks = []
    for k, w in enumerate(words):
        text, norm, start, end = w[0], w[1], float(w[2]), float(w[3])
        conf = float(w[4]) if len(w) > 4 else 1.0
        toks.append(WordToken(id=f"p{k}", text=text, normalized=norm, start=start, end=end,
                              confidence=conf))
    return toks


def clip_counts(pred: list[WordToken], ref: list[WordToken]) -> dict:
    """Hits per metric plus denominators and matched-boundary stats for one clip."""
    res = {"n_pred_b": 2 * len(pred), "n_ref_b": 2 * len(ref), "matched_words": 0,
           "acc20_hits": 0}
    for m in METRICS:
        res[m] = 0
    if not pred or not ref:
        return res
    pairs, _ = _align_token_sequences(pred, ref)
    pidx = {id(t): i for i, t in enumerate(pred)}
    ridx = {id(t): j for j, t in enumerate(ref)}
    p2r = {pidx[id(p)]: ridx[id(r)] for p, r in pairs}
    res["matched_words"] = len(pairs)
    np_, nr = len(pred), len(ref)
    for p, r in pairs:
        i, j = pidx[id(p)], ridx[id(r)]
        es = abs(p.start - r.start) * 1000.0
        ee = abs(p.end - r.end) * 1000.0
        res["acc20_hits"] += (es <= 20 + BOUNDARY_EPSILON_MS) + (ee <= 20 + BOUNDARY_EPSILON_MS)
        ctx_s = (i == 0 and j == 0) or (i > 0 and j > 0 and p2r.get(i - 1) == j - 1)
        ctx_e = (i == np_ - 1 and j == nr - 1) or (p2r.get(i + 1) == j + 1 and i + 1 < np_)
        for m, (tau, ctx) in METRICS.items():
            hs = es <= tau + BOUNDARY_EPSILON_MS
            he = ee <= tau + BOUNDARY_EPSILON_MS
            if ctx:
                hs, he = hs and ctx_s, he and ctx_e
            res[m] += int(hs) + int(he)
    return res


def prf(hits, npb, nrb):
    p = hits / npb if npb else 0.0
    r = hits / nrb if nrb else 0.0
    f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f


def exact_wilcoxon(diffs) -> dict:
    d = np.round(np.asarray(diffs, dtype=float), 12)
    d = d[d != 0]
    n = len(d)
    if n == 0:
        return {"p": 1.0, "n_nonzero": 0, "w": 0.0}
    a = np.abs(d)
    order = np.argsort(a, kind="stable")
    ranks2 = np.empty(n, dtype=np.int64)  # doubled mid-ranks (integers)
    k = 0
    while k < n:
        e = k + 1
        while e < n and a[order[e]] == a[order[k]]:
            e += 1
        ranks2[order[k:e]] = (k + 1) + e  # 2 * mean(k+1..e)
        k = e
    wplus = int(ranks2[d > 0].sum())
    total = int(ranks2.sum())
    # exact null distribution of doubled W+ by DP over sign assignments
    dist = np.zeros(total + 1, dtype=object)
    dist[0] = 1
    for rk in ranks2:
        new = dist.copy()
        new[rk:] = new[rk:] + dist[: total + 1 - rk]
        dist = new
    w = min(wplus, total - wplus)
    tail = sum(dist[: w + 1])
    p = min(1.0, 2 * tail / 2**n)
    return {"p": float(p), "n_nonzero": n, "w": w / 2}


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out, running = {}, 0.0
    for k, (key, p) in enumerate(items):
        running = max(running, min(1.0, (m - k) * p))
        out[key] = running
    return out


def run_corpus(corpus: str) -> dict:
    base = f"reports/{corpus}"
    manifest = read_json(f"{base}/manifest.json")
    preds = read_json(f"{base}/benchmark_predictions.json")["modes"]
    rows = read_json(f"{base}/benchmark_utterances.json")
    frozen = read_json(f"{base}/benchmark_results.json")["modes"]
    row_status = {(r["mode"], r["utterance"]): r["status"] for r in rows}
    ids = sorted(manifest["inputs"]["audio_files"])
    refs = load_refs(corpus, ids)
    speakers = sorted({refs[u].speaker_id for u in ids})
    spk_index = {s: k for k, s in enumerate(speakers)}
    rng_draw = np.random.default_rng(SEED).integers(0, len(speakers), size=(N_BOOT, len(speakers)))

    out = {"n_clips": len(ids), "n_speakers": len(speakers), "modes": {}, "sanity": {}}
    spk_f1 = {}
    for mode in MODES:
        per_spk = {m: np.zeros((len(speakers), 3)) for m in METRICS}  # hits, npb, nrb
        n_failed, matched, acc_hits = 0, 0, 0
        for u in ids:
            ref = refs[u].ref_words
            entry = preds.get(mode, {}).get(u)
            ok = (entry is not None and entry.get("status") == "ok"
                  and row_status.get((mode, u)) == "ok")
            if ok:
                c = clip_counts(pred_tokens(entry["words"]), ref)
            else:
                n_failed += 1
                c = clip_counts([], ref)
            matched += c["matched_words"]
            acc_hits += c["acc20_hits"]
            s = spk_index[refs[u].speaker_id]
            for m in METRICS:
                per_spk[m][s] += (c[m], c["n_pred_b"], c["n_ref_b"])
        mres = {"n_failed_clips": n_failed}
        for m in METRICS:
            tot = per_spk[m].sum(axis=0)
            p, r, f = prf(*tot)
            boot = []
            for row in rng_draw:
                t = per_spk[m][row].sum(axis=0)
                boot.append(prf(*t)[2])
            ci = np.percentile(boot, [2.5, 97.5]).tolist()
            mres[m] = {"precision": p, "recall": r, "f1": f, "f1_ci_95": ci,
                       "hits": int(tot[0]), "pred_boundaries": int(tot[1]),
                       "ref_boundaries": int(tot[2])}
        sf = {spk: prf(*per_spk["edge20"][k])[2] for k, spk in enumerate(speakers)}
        mres["speaker_f1_edge20"] = sf
        spk_f1[mode] = sf
        fw = frozen[mode]["word_metrics"]
        acc_re = 100.0 * acc_hits / (2 * matched) if matched else 0.0
        out["sanity"][mode] = {
            "acc20_recomputed": acc_re, "acc20_frozen": fw["acc_20ms"],
            "acc_ok": abs(acc_re - fw["acc_20ms"]) <= 0.01 + 1e-9,
            "num_matched_recomputed": matched, "num_matched_frozen": fw["num_matched"],
        }
        mres["unmatched_cost_acc20_minus_recall20"] = fw["acc_20ms"] / 100 - mres["edge20"]["recall"]
        out["modes"][mode] = mres

    tests = {}
    for cond, basem in PAIRS:
        diffs = [spk_f1[cond][s] - spk_f1[basem][s] for s in speakers]
        w = exact_wilcoxon(diffs)
        tests[f"{cond} - {basem}"] = {
            "mean_difference": float(np.mean(diffs)),
            "median_difference": float(np.median(diffs)),
            "w": w["w"], "n_nonzero": w["n_nonzero"], "p_value_raw": w["p"],
        }
    adj = holm({k: v["p_value_raw"] for k, v in tests.items()})
    for k in tests:
        tests[k]["p_value_holm"] = adj[k]
    out["tests_edge20"] = tests
    return out


def main() -> None:
    result = {"protocol": "docs/F1_PROTOCOL.md", "note": "independent re-implementation",
              "corpora": {c: run_corpus(c) for c in ("buckeye", "timit")}}
    (OUT / "independent_check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for c, r in result["corpora"].items():
        bad = [m for m, s in r["sanity"].items()
               if not s["acc_ok"] or s["num_matched_recomputed"] != s["num_matched_frozen"]]
        print(c, "sanity failures:", bad)


if __name__ == "__main__":
    main()
