"""Independent re-implementation of P-1..P-4 from docs/P1_P4_PROTOCOL.md only.

Written without reading scripts/p1_p4_analyses.py, its tests, or the original outputs.
Reuses only: corpus loaders, _align_token_sequences, WordToken, read_wav_mono.
Run from the repo root:  .venv/Scripts/python.exe reports/p1_p4_20261120/independent/independent_check.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]

from speech_benchmark import load_textgrid_utterances, load_timit_utterances  # noqa: E402

from subtitle_workbench.metrics import _align_token_sequences  # noqa: E402
from subtitle_workbench.models import WordToken  # noqa: E402
from subtitle_workbench.refiner import read_wav_mono  # noqa: E402

OUT = Path(__file__).resolve().parent / "independent_check.json"
S3_MODELS = ["tiny", "base", "small", "medium", "large-v3-turbo"]

# ---------------------------------------------------------------- loading


def load_run(run: str) -> dict:
    d = ROOT / "reports" / run
    preds = json.loads((d / "benchmark_predictions.json").read_text(encoding="utf-8"))
    assert preds["schema_version"] == 1
    fields = preds["fields"]["word"].split(",")
    rows = json.loads((d / "benchmark_utterances.json").read_text(encoding="utf-8"))
    clips = list(json.loads((d / "manifest.json").read_text(encoding="utf-8"))["inputs"]["audio_files"])
    clipset = set(clips)
    ok: dict[str, set] = {}
    speaker: dict[str, str] = {}
    for r in rows:
        speaker[r["utterance"]] = r["speaker"]
        if r["status"] == "ok" and r["utterance"] in clipset:
            ok.setdefault(r["mode"], set()).add(r["utterance"])
    words: dict[str, dict[str, list]] = {}
    for mode, per in preds["modes"].items():
        words[mode] = {}
        for cid, rec in per.items():
            if rec.get("status") != "ok" or cid not in ok.get(mode, set()):
                continue
            toks = []
            for i, w in enumerate(rec["words"]):
                conf = float(w[4]) if len(fields) >= 5 and len(w) >= 5 else 1.0
                toks.append(WordToken(id=f"w{i}", text=w[0], normalized=w[1], start=float(w[2]),
                                      end=float(w[3]), confidence=conf))
            words[mode][cid] = toks
        ok[mode] = {c for c in ok.get(mode, set()) if c in words[mode]}
    results = None
    if (d / "benchmark_results.json").exists():
        results = json.loads((d / "benchmark_results.json").read_text(encoding="utf-8"))
    return {"run": run, "clips": clips, "ok": ok, "words": words, "speaker": speaker, "results": results}


_ALIGN_CACHE: dict = {}


def match(run: dict, mode: str, cid: str, ref: list) -> dict[int, tuple[int, WordToken]]:
    """ref index -> (pred index, pred word) for matched words."""
    key = (run["run"], mode, cid)
    if key in _ALIGN_CACHE:
        return _ALIGN_CACHE[key]
    toks = run["words"][mode][cid]
    out: dict[int, tuple[int, WordToken]] = {}
    if toks and ref:
        ridx = {id(w): i for i, w in enumerate(ref)}
        pidx = {id(w): i for i, w in enumerate(toks)}
        for p, r in _align_token_sequences(toks, ref)[0]:
            out[ridx[id(r)]] = (pidx[id(p)], p)
    _ALIGN_CACHE[key] = out
    return out


def bnd_errors(p, r) -> tuple[float, float]:
    return abs(p.start - r.start) * 1000.0, abs(p.end - r.end) * 1000.0


# ---------------------------------------------------------------- stats


def speaker_mean(per_spk: dict[str, list[float]]) -> float:
    vals = [float(np.mean(v)) for v in per_spk.values() if len(v)]
    return float(np.mean(vals))


def pooled_mae(run: dict, mode: str, refs: dict) -> float:
    errs = []
    for cid in run["ok"][mode]:
        ref = refs[cid].ref_words
        for ri, (_, p) in match(run, mode, cid, ref).items():
            errs.extend(bnd_errors(p, ref[ri]))
    return float(np.mean(errs))


def rankdata(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="mergesort")
    xs = x[order]
    ranks = np.empty(len(x))
    i = 0
    n = len(x)
    while i < n:
        j = i
        while j + 1 < n and xs[j + 1] == xs[i]:
            j += 1
        ranks[order[i : j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return ranks


def roc_auc(y: np.ndarray, s: np.ndarray) -> float:
    y = np.asarray(y, dtype=bool)
    r = rankdata(s)
    n1 = int(y.sum())
    n0 = len(y) - n1
    return float((r[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def average_precision(y: np.ndarray, s: np.ndarray) -> float:
    y = np.asarray(y, dtype=bool)
    s = np.asarray(s, dtype=float)
    order = np.argsort(-s, kind="mergesort")
    ys, ss = y[order], s[order]
    tp = np.cumsum(ys)
    k = np.arange(1, len(ys) + 1)
    last = np.r_[ss[1:] != ss[:-1], True]  # last index of each distinct threshold
    tp_t, k_t = tp[last], k[last]
    prec = tp_t / k_t
    rec = tp_t / ys.sum()
    rec_prev = np.r_[0.0, rec[:-1]]
    return float(np.sum((rec - rec_prev) * prec))


def wilcoxon_exact(d: list[float]) -> float:
    """Exact two-sided signed-rank p; zero differences dropped; tie-aware via doubled ranks."""
    d = np.asarray([x for x in d if x != 0.0], dtype=float)
    n = len(d)
    if n == 0:
        return 1.0
    r2 = np.rint(rankdata(np.abs(d)) * 2).astype(int)
    tplus = int(r2[d > 0].sum())
    total = int(r2.sum())
    dist = np.zeros(total + 1, dtype=np.float64)
    dist[0] = 1.0
    for v in r2:
        new = dist.copy()
        new[v:] += dist[: total + 1 - v]
        dist = new
    dist /= dist.sum()
    lo = dist[: tplus + 1].sum()
    hi = dist[tplus:].sum()
    return float(min(1.0, 2.0 * min(lo, hi)))


def holm(ps: list[float]) -> list[float]:
    m = len(ps)
    order = np.argsort(ps, kind="mergesort")
    adj = [0.0] * m
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * ps[i]))
        adj[i] = run
    return adj


# ---------------------------------------------------------------- P-1


def p1(runs: dict, refs: dict) -> dict:
    pairs = [("A1_ctc", "A2_proposed"), ("A1_ctc", "A2_brqe"),
             ("B1_whisper_ctc", "B2_proposed"), ("B1_whisper_ctc", "B2_brqe")]
    out = {}
    for corpus in ("buckeye", "timit"):
        run, ref = runs[corpus], refs[corpus]
        out[corpus] = {}
        for ctc, mfa in pairs:
            clips = sorted(run["ok"][ctc] & run["ok"][mfa])
            E = {k: {} for k in ("mfa", "ctc", "oracle", "average")}
            n_common = 0
            for cid in clips:
                rw = ref[cid].ref_words
                mc, mm = match(run, ctc, cid, rw), match(run, mfa, cid, rw)
                spk = run["speaker"][cid]
                for ri in sorted(set(mc) & set(mm)):
                    pc, pm, r = mc[ri][1], mm[ri][1], rw[ri]
                    for a, b, t in ((pc.start, pm.start, r.start), (pc.end, pm.end, r.end)):
                        ec, em = abs(a - t) * 1000, abs(b - t) * 1000
                        ea = abs(0.5 * (a + b) - t) * 1000
                        for k, v in (("mfa", em), ("ctc", ec), ("oracle", min(ec, em)), ("average", ea)):
                            E[k].setdefault(spk, []).append(v)
                        n_common += 1
            n_mfa_all = sum(2 * len(match(run, mfa, c, ref[c].ref_words)) for c in run["ok"][mfa])
            n_mfa_common_clips = sum(2 * len(match(run, mfa, c, ref[c].ref_words)) for c in clips)
            sm = {k: speaker_mean(v) for k, v in E.items()}
            out[corpus][f"{ctc}+{mfa}"] = {
                "n_clips": len(clips), "n_speakers": len(E["mfa"]), "n_boundaries": n_common,
                "mae_mfa": sm["mfa"], "mae_ctc": sm["ctc"], "mae_oracle": sm["oracle"],
                "mae_average": sm["average"],
                "oracle_gain": sm["mfa"] - sm["oracle"], "average_gain": sm["mfa"] - sm["average"],
                "share_mfa_boundaries_all_ok_clips": n_common / n_mfa_all,
                "share_mfa_boundaries_common_clips": n_common / n_mfa_common_clips,
            }
    g = [out["buckeye"][k]["oracle_gain"] for k in ("A1_ctc+A2_brqe", "B1_whisper_ctc+B2_brqe")]
    out["decision"] = "G-4 stays candidate" if max(g) >= 2.0 else "G-4 closed"
    out["decision_gains_buckeye_brqe"] = g
    return out


# ---------------------------------------------------------------- P-2

SR = 16000
WIN = 400
HOP = 40
N_MELS = 40


def mel_fb() -> np.ndarray:
    def hz2mel(f):
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel2hz(m):
        return 700.0 * (10 ** (m / 2595.0) - 1.0)

    freqs = np.linspace(0, SR / 2, WIN // 2 + 1)
    pts = mel2hz(np.linspace(hz2mel(0.0), hz2mel(8000.0), N_MELS + 2))
    fb = np.zeros((N_MELS, len(freqs)))
    for m in range(N_MELS):
        lo, c, hi = pts[m], pts[m + 1], pts[m + 2]
        up = (freqs - lo) / (c - lo)
        down = (hi - freqs) / (hi - c)
        fb[m] = np.maximum(0.0, np.minimum(up, down))
    return fb


FB = mel_fb()
HANN = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(WIN) / WIN)


def flux(wav: Path) -> tuple[np.ndarray, np.ndarray]:
    x = read_wav_mono(wav).astype(np.float64)
    if len(x) < WIN + HOP:
        return np.zeros(0), np.zeros(0)
    nfr = 1 + (len(x) - WIN) // HOP
    idx = np.arange(WIN)[None, :] + HOP * np.arange(nfr)[:, None]
    spec = np.abs(np.fft.rfft(x[idx] * HANN, n=WIN, axis=1)) ** 2
    logmel = np.log(spec @ FB.T + 1e-10)
    f = np.maximum(0.0, np.diff(logmel, axis=0)).sum(axis=1)
    centers = (np.arange(nfr) * HOP + WIN / 2) / SR
    t = 0.5 * (centers[1:] + centers[:-1])
    return t, f


def shift_words(toks: list, ft: np.ndarray, fv: np.ndarray, W: float, alpha: float) -> list[tuple[float, float]]:
    times = sorted({w.start for w in toks} | {w.end for w in toks})
    new = {}
    prev = -np.inf
    for t in times:
        sel = np.nonzero((ft >= t - W - 1e-9) & (ft <= t + W + 1e-9))[0]
        nt = t
        if len(sel):
            pk = ft[sel[int(np.argmax(fv[sel]))]]
            nt = t + alpha * (pk - t)
        if nt <= prev + 0.001:
            nt = t
        new[t] = nt
        prev = nt
    out = []
    for w in toks:
        s, e = new[w.start], new[w.end]
        if s >= e:
            s, e = w.start, w.end
        out.append((s, e))
    return out


def shifted_speaker_errors(run, mode, ref, fluxes, W, alpha, clips) -> dict[str, list[float]]:
    per: dict[str, list[float]] = {}
    for cid in clips:
        toks = run["words"][mode][cid]
        rw = ref[cid].ref_words
        ft, fv = fluxes[cid]
        nb = shift_words(toks, ft, fv, W, alpha)
        spk = run["speaker"][cid]
        for ri, (pi, _) in match(run, mode, cid, rw).items():
            s, e = nb[pi]
            per.setdefault(spk, []).extend([abs(s - rw[ri].start) * 1000, abs(e - rw[ri].end) * 1000])
    return per


def base_speaker_errors(run, mode, ref, clips) -> dict[str, list[float]]:
    per: dict[str, list[float]] = {}
    for cid in clips:
        rw = ref[cid].ref_words
        spk = run["speaker"][cid]
        for ri, (_, p) in match(run, mode, cid, rw).items():
            per.setdefault(spk, []).extend(bnd_errors(p, rw[ri]))
    return per


def p2(runs: dict, refs: dict) -> dict:
    tr, ref = runs["brqe_train_run"], refs["buckeye"]
    needed = sorted(tr["ok"]["A2_proposed"] | tr["ok"]["B2_proposed"])
    t0 = time.time()
    fluxes = {c: flux(ref[c].wav_path) for c in needed}
    print(f"P-2 flux for {len(fluxes)} train clips in {time.time() - t0:.1f}s", flush=True)
    out = {"train": {}, "test": {}}
    tests = []
    for sc, mode in (("A", "A2_proposed"), ("B", "B2_proposed")):
        clips = sorted(tr["ok"][mode])
        base = speaker_mean(base_speaker_errors(tr, mode, ref, clips))
        grid = []
        for W in (0.010, 0.020, 0.030):
            for a in (0.5, 1.0):
                m = speaker_mean(shifted_speaker_errors(tr, mode, ref, fluxes, W, a, clips))
                grid.append({"W_ms": round(W * 1000), "alpha": a, "mae": m, "gain": base - m})
        best = min(grid, key=lambda g: g["mae"])
        out["train"][sc] = {"mode": mode, "n_clips": len(clips), "mae_mfa": base, "grid": grid,
                            "selected": {"W_ms": best["W_ms"], "alpha": best["alpha"]},
                            "selected_gain": best["gain"], "test_run": best["gain"] >= 0.5}
        if best["gain"] >= 0.5:
            tests.append((sc, mode, best))
    if tests:
        bk = runs["buckeye"]
        for sc, mode, best in tests:
            brqe = mode.replace("proposed", "brqe")
            clips = sorted(bk["ok"][mode])
            for c in clips:
                if c not in fluxes:
                    fluxes[c] = flux(ref[c].wav_path)
            sh = shifted_speaker_errors(bk, mode, ref, fluxes, best["W_ms"] / 1000, best["alpha"], clips)
            for other, oclips in ((mode, clips), (brqe, sorted(bk["ok"][brqe]))):
                ob = base_speaker_errors(bk, other, ref, oclips)
                spk = sorted(set(sh) & set(ob))
                d = [float(np.mean(sh[s]) - np.mean(ob[s])) for s in spk]
                out["test"][f"{sc}: shift vs {other}"] = {
                    "mae_shift": float(np.mean([np.mean(sh[s]) for s in spk])),
                    "mae_other": float(np.mean([np.mean(ob[s]) for s in spk])),
                    "mean_diff": float(np.mean(d)), "p_raw": wilcoxon_exact(d), "n_speakers": len(spk)}
        keys = list(out["test"])
        for k, h in zip(keys, holm([out["test"][k]["p_raw"] for k in keys])):
            out["test"][k]["p_holm"] = h
    return out


# ---------------------------------------------------------------- P-3


def p3(runs: dict, refs: dict) -> dict:
    bk, ref = runs["buckeye"], refs["buckeye"]
    out = {}
    for mode in ("B2_proposed", "B2_brqe"):
        out[mode] = {}
        for model in S3_MODELS:
            s3 = runs[f"s3_{model}"]
            clips = sorted(bk["ok"][mode] & s3["ok"][mode])
            cm_b: dict[str, list] = {}
            cm_s: dict[str, list] = {}
            n_int, n_clips_kept = 0, 0
            for cid in clips:
                rw = ref[cid].ref_words
                mb, ms = match(bk, mode, cid, rw), match(s3, mode, cid, rw)
                inter = sorted(set(mb) & set(ms))
                if not inter:
                    continue
                eb, es = [], []
                for ri in inter:
                    eb.extend(bnd_errors(mb[ri][1], rw[ri]))
                    es.extend(bnd_errors(ms[ri][1], rw[ri]))
                spk = bk["speaker"][cid]
                cm_b.setdefault(spk, []).append(np.mean(eb))
                cm_s.setdefault(spk, []).append(np.mean(es))
                n_int += 2 * len(inter)
                n_clips_kept += 1
            spk = sorted(cm_b)
            vb = [float(np.mean(cm_b[s])) for s in spk]
            vs = [float(np.mean(cm_s[s])) for s in spk]
            d = [a - b for a, b in zip(vs, vb)]
            nb_all = sum(2 * len(match(bk, mode, c, ref[c].ref_words)) for c in bk["ok"][mode])
            ns_all = sum(2 * len(match(s3, mode, c, ref[c].ref_words)) for c in s3["ok"][mode])
            nb_common = sum(2 * len(match(bk, mode, c, ref[c].ref_words)) for c in clips)
            spk_all = {bk["speaker"][c] for c in bk["ok"][mode]}
            out[mode][model] = {
                "n_clips_ok_both": len(clips), "n_clips": n_clips_kept, "n_speakers": len(spk),
                "n_boundaries": n_int,
                "mae_large_v3": float(np.mean(vb)), "mae_model": float(np.mean(vs)),
                "mean_diff": float(np.mean(d)), "p_raw": wilcoxon_exact(d),
                "retained_share_vs_frozen_all_ok": n_int / nb_all,
                "retained_share_vs_model_all_ok": n_int / ns_all,
                "retained_share_vs_frozen_common_clips": nb_common and n_int / nb_common,
                "clip_share_vs_frozen_ok": n_clips_kept / len(bk["ok"][mode]),
                "speaker_share": len(spk) / len(spk_all),
            }
        hs = holm([out[mode][m]["p_raw"] for m in S3_MODELS])
        for m, h in zip(S3_MODELS, hs):
            out[mode][m]["p_holm"] = h
    return out


# ---------------------------------------------------------------- P-4


def p4(runs: dict, refs: dict) -> dict:
    bk, ref = runs["buckeye"], refs["buckeye"]
    out = {}
    for sc, base, brqe, ctc in (("A", "A2_proposed", "A2_brqe", "A1_ctc"),
                                ("B", "B2_proposed", "B2_brqe", "B1_whisper_ctc")):
        all_y, all_b = [], []
        Y, SB, SD, SPK = [], [], [], []
        for cid in sorted(bk["ok"][base] & bk["ok"][brqe]):
            rw = ref[cid].ref_words
            rb = bk["words"][brqe][cid]
            mb = match(bk, base, cid, rw)
            mc = match(bk, ctc, cid, rw) if cid in bk["ok"][ctc] else {}
            for ri, (pi, p) in mb.items():
                y = max(abs(p.start - rw[ri].start), abs(p.end - rw[ri].end)) * 1000 > 20.0
                b = 1.0 - rb[pi].confidence
                all_y.append(y)
                all_b.append(b)
                if ri in mc:
                    c = mc[ri][1]
                    Y.append(y)
                    SB.append(b)
                    SD.append(max(abs(p.start - c.start), abs(p.end - c.end)))
                    SPK.append(bk["speaker"][cid])
        Y, SB, SD, SPK = np.array(Y), np.array(SB), np.array(SD), np.array(SPK)
        n = len(Y)
        SC = 0.5 * (rankdata(SB) / n + rankdata(SD) / n)
        scores = {"brqe": SB, "disagreement": SD, "combined": SC}
        res = {"n_words_all_base": len(all_y), "brqe_auc_all_base": roc_auc(np.array(all_y), np.array(all_b)),
               "brqe_prauc_all_base": average_precision(np.array(all_y), np.array(all_b)),
               "frozen_brqe_auc": bk["results"]["modes"][brqe]["quality_estimation"]["roc_auc"],
               "frozen_brqe_prauc": bk["results"]["modes"][brqe]["quality_estimation"]["pr_auc"],
               "n_words": n, "positive_rate": float(Y.mean()), "n_speakers": len(set(SPK))}
        for k, s in scores.items():
            res[f"roc_auc_{k}"] = roc_auc(Y, s)
            res[f"pr_auc_{k}"] = average_precision(Y, s)
        diff = res["roc_auc_combined"] - res["roc_auc_brqe"]
        spks = sorted(set(SPK))
        idx = {s: np.nonzero(SPK == s)[0] for s in spks}
        rng = np.random.default_rng(42)
        boots = []
        for _ in range(2000):
            pick = rng.integers(0, len(spks), len(spks))
            ii = np.concatenate([idx[spks[j]] for j in pick])
            boots.append(roc_auc(Y[ii], SC[ii]) - roc_auc(Y[ii], SB[ii]))
        lo, hi = np.percentile(boots, [2.5, 97.5])
        res.update({"auc_diff_combined_minus_brqe": diff, "auc_diff_ci95": [float(lo), float(hi)],
                    "complements": bool(lo > 0)})
        out[sc] = res
    s1b = {}
    for L in ("L01", "L05", "L10"):
        rows = json.loads((ROOT / f"reports/s1b_long_20261103/runs/{L}_anchored/benchmark_utterances.json")
                          .read_text(encoding="utf-8"))
        st = {(r["mode"], r["utterance"]): r["status"] for r in rows}
        utts = sorted({r["utterance"] for r in rows})
        rec = {"n_recordings": len(utts)}
        for sc, mfa, ctc in (("A", "A2_proposed", "A1_ctc"), ("B", "B2_proposed", "B1_whisper_ctc")):
            rec[f"{sc}_mfa_failed"] = sum(st.get((mfa, u)) != "ok" for u in utts)
            rec[f"{sc}_ctc_ok"] = sum(st.get((ctc, u)) == "ok" for u in utts)
            rec[f"{sc}_mfa_failed_ctc_ok"] = sum(st.get((mfa, u)) != "ok" and st.get((ctc, u)) == "ok" for u in utts)
        s1b[L] = rec
    out["p4b_s1b"] = s1b
    return out


# ---------------------------------------------------------------- main


def main() -> None:
    t0 = time.time()
    bk_utts = load_textgrid_utterances(ROOT / "data/corpora/buckeye", "buckeye")
    tm_utts = load_timit_utterances(ROOT / "data/corpora/timit")
    refs = {"buckeye": {u.id: u for u in bk_utts}, "timit": {u.id: u for u in tm_utts}}
    print(f"corpora loaded {time.time() - t0:.1f}s", flush=True)
    runs = {"buckeye": load_run("buckeye"), "timit": load_run("timit"),
            "brqe_train_run": load_run("brqe_train_run")}
    for m in S3_MODELS:
        runs[f"s3_{m}"] = load_run(f"s3_asr_size_20261106/runs/buckeye_{m}")
    # speaker sanity: row speaker == corpus speaker
    sanity = {}
    for name, run in runs.items():
        corpus = "timit" if name == "timit" else "buckeye"
        for cid in run["clips"]:
            assert cid in refs[corpus], (name, cid)
        modes = [m for m in run["ok"] if m in run["words"]]
        if name.startswith("s3_"):
            modes = ["B2_proposed", "B2_brqe"]
        for mode in modes:
            mine = pooled_mae(run, mode, refs[corpus])
            frozen = run["results"]["modes"][mode]["word_metrics"]["mae_ms"]
            sanity[f"{name}:{mode}"] = {"mine": mine, "frozen": frozen, "ok": abs(round(mine, 2) - frozen) <= 0.01}
    print("sanity", all(v["ok"] for v in sanity.values()), flush=True)
    out = {"sanity_pooled_mae": sanity}
    out["p1"] = p1(runs, refs)
    print("P-1 done", flush=True)
    out["p3"] = p3(runs, refs)
    print("P-3 done", flush=True)
    out["p4"] = p4(runs, refs)
    print("P-4 done", flush=True)
    out["p2"] = p2(runs, refs)
    print(f"P-2 done; total {time.time() - t0:.1f}s", flush=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
