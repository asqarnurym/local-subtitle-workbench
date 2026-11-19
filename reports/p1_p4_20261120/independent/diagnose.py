"""Post-comparison diagnosis (written AFTER reading the original code).

Re-runs the independent P-2 grid and P-4 scores with the original's implementation choices
switched in one at a time, to confirm the cause of each small discrepancy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import independent_check as ic  # noqa: E402

OUT = Path(__file__).resolve().parent / "diagnose.json"


def flux_variant(n_fft: int, symmetric: bool):
    freqs = np.fft.rfftfreq(n_fft, 1.0 / ic.SR)

    def hz2mel(f):
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel2hz(m):
        return 700.0 * (10 ** (m / 2595.0) - 1.0)

    pts = mel2hz(np.linspace(hz2mel(0.0), hz2mel(8000.0), ic.N_MELS + 2))
    fb = np.zeros((ic.N_MELS, len(freqs)))
    for m in range(ic.N_MELS):
        lo, c, hi = pts[m], pts[m + 1], pts[m + 2]
        fb[m] = np.maximum(0.0, np.minimum((freqs - lo) / (c - lo), (hi - freqs) / (hi - c)))
    win = np.hanning(ic.WIN) if symmetric else ic.HANN

    def flux(wav):
        x = ic.read_wav_mono(wav).astype(np.float64)
        if len(x) < ic.WIN + ic.HOP:
            return np.zeros(0), np.zeros(0)
        nfr = 1 + (len(x) - ic.WIN) // ic.HOP
        idx = np.arange(ic.WIN)[None, :] + ic.HOP * np.arange(nfr)[:, None]
        spec = np.abs(np.fft.rfft(x[idx] * win, n=n_fft, axis=1)) ** 2
        logmel = np.log(spec @ fb.T + 1e-10)
        f = np.maximum(0.0, np.diff(logmel, axis=0)).sum(axis=1)
        centers = (np.arange(nfr) * ic.HOP + ic.WIN / 2) / ic.SR
        return 0.5 * (centers[1:] + centers[:-1]), f

    return flux


def ap_untied(y, s):
    order = np.argsort(-np.asarray(s), kind="mergesort")
    hits = np.asarray(y, dtype=bool)[order]
    prec = np.cumsum(hits) / np.arange(1, len(hits) + 1)
    return float((prec * hits).sum() / hits.sum())


def main():
    bk_utts = ic.load_textgrid_utterances(ic.ROOT / "data/corpora/buckeye", "buckeye")
    ref = {u.id: u for u in bk_utts}
    tr = ic.load_run("brqe_train_run")
    out = {"p2": {}, "p4": {}}
    clips_all = sorted(tr["ok"]["A2_proposed"] | tr["ok"]["B2_proposed"])
    for name, nfft, sym in (("nfft512_symhann", 512, True), ("nfft512_periodic", 512, False),
                            ("nfft400_symhann", 400, True)):
        fx = flux_variant(nfft, sym)
        fluxes = {c: fx(ref[c].wav_path) for c in clips_all}
        res = {}
        for mode in ("A2_proposed", "B2_proposed"):
            clips = sorted(tr["ok"][mode])
            res[mode] = [ic.speaker_mean(ic.shifted_speaker_errors(tr, mode, ref, fluxes, W, a, clips))
                         for W in (0.010, 0.020, 0.030) for a in (0.5, 1.0)]
        out["p2"][name] = res
        print(name, res, flush=True)
    bk = ic.load_run("buckeye")
    for sc, base, brqe, ctc in (("A", "A2_proposed", "A2_brqe", "A1_ctc"),
                                ("B", "B2_proposed", "B2_brqe", "B1_whisper_ctc")):
        Y, SB, SD = [], [], []
        for cid in sorted(bk["ok"][base] & bk["ok"][brqe]):
            rw = ref[cid].ref_words
            rb = bk["words"][brqe][cid]
            mc = ic.match(bk, ctc, cid, rw) if cid in bk["ok"][ctc] else {}
            for ri, (pi, p) in ic.match(bk, base, cid, rw).items():
                if ri in mc:
                    c = mc[ri][1]
                    Y.append(max(abs(p.start - rw[ri].start), abs(p.end - rw[ri].end)) > 0.02)
                    SB.append(1.0 - rb[pi].confidence)
                    SD.append(max(abs(c.start - p.start), abs(c.end - p.end)) * 1000)
        Y, SB, SD = np.array(Y), np.array(SB), np.array(SD)
        n = len(Y)
        SC = 0.5 * (ic.rankdata(SB) / n + ic.rankdata(SD) / n)
        out["p4"][sc] = {"roc_dis_ms": ic.roc_auc(Y, SD), "roc_comb_ms": ic.roc_auc(Y, SC),
                         "ap_untied_brqe": ap_untied(Y, SB), "ap_untied_dis_ms": ap_untied(Y, SD),
                         "ap_untied_comb_ms": ap_untied(Y, SC)}
        print(sc, out["p4"][sc], flush=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
