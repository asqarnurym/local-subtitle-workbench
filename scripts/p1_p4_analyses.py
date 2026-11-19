"""P-1...P-4 exploratory analyses on saved predictions (docs/P1_P4_PROTOCOL.md).

No model is run. Frozen outputs are read-only; results go to reports/p1_p4_20261120/.

    python scripts/p1_p4_analyses.py p1|p2|p3|p4|all
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import speech_benchmark as benchmark  # noqa: E402
from scripts.s1_long_recordings import bootstrap_mean_ci, paired_test  # noqa: E402
from scripts.s2_s3_substudies import holm  # noqa: E402
from scripts.verify_frozen_evidence import local_path, read_json, require  # noqa: E402
from subtitle_workbench.metrics import _align_token_sequences  # noqa: E402
from subtitle_workbench.models import WordToken  # noqa: E402
from subtitle_workbench.provenance import code_provenance  # noqa: E402
from subtitle_workbench.refiner import pr_auc, read_wav_mono, roc_auc  # noqa: E402

OUT = ROOT / "reports" / "p1_p4_20261120"
S3_DIR = "reports/s3_asr_size_20261106/runs"
S3_MODELS = ["tiny", "base", "small", "medium", "large-v3-turbo"]
SEED, RESAMPLES = 42, 2000
SR, WIN, HOP, N_FFT, N_MELS = 16000, 400, 40, 512, 40
P2_GRID = [(w, a) for w in (0.010, 0.020, 0.030) for a in (0.5, 1.0)]
P2_MIN_TRAIN_GAIN_MS = 0.5
P1_DECISION_MS = 2.0

_CORPUS_CACHE: dict[str, dict[str, benchmark.BenchmarkUtterance]] = {}


# ------------------------------------------------------------------ loading
def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def corpus(name: str) -> dict[str, benchmark.BenchmarkUtterance]:
    if name not in _CORPUS_CACHE:
        utts = (
            benchmark.load_timit_utterances(local_path("data/corpora/timit"))
            if name == "timit"
            else benchmark.load_textgrid_utterances(local_path("data/corpora/buckeye"), "buckeye")
        )
        _CORPUS_CACHE[name] = {u.id: u for u in utts}
    return _CORPUS_CACHE[name]


def load_predictions(relative: str) -> dict[str, dict[str, list[WordToken] | str]]:
    """Word predictions per mode and clip (or the failure text); 4- or 5-field words."""
    payload = read_json(relative)
    require(payload["schema_version"] == 1, f"Unsupported prediction schema: {relative}")
    fields = payload["fields"]["word"].split(",")
    require(fields[:4] == ["text", "normalized", "start", "end"], f"Word fields: {relative}")
    out: dict[str, dict[str, Any]] = {}
    for mode, entries in payload["modes"].items():
        out[mode] = {}
        for uid, item in entries.items():
            if item["status"] != "ok":
                out[mode][uid] = item.get("error") or "failed"
                continue
            out[mode][uid] = [
                WordToken(
                    f"w{i}",
                    v[0],
                    v[1],
                    float(v[2]),
                    float(v[3]),
                    float(v[4]) if len(v) > 4 else 1.0,
                )
                for i, v in enumerate(item["words"])
            ]
    return out


def ok_clips(rows_relative: str) -> dict[str, set[str]]:
    """Clips scored successfully per mode, from the saved benchmark rows."""
    ok: dict[str, set[str]] = defaultdict(set)
    for r in read_json(rows_relative):
        if r["status"] == "ok":
            ok[r["mode"]].add(r["utterance"])
    return ok


def run_inputs(run: str) -> tuple[dict, dict, dict[str, set[str]], list[str]]:
    base = f"reports/{run}" if not run.startswith("reports/") else run
    results = read_json(f"{base}/benchmark_results.json")
    preds = load_predictions(f"{base}/benchmark_predictions.json")
    ok = ok_clips(f"{base}/benchmark_utterances.json")
    ids = list(read_json(f"{base}/manifest.json")["inputs"]["audio_files"])
    return results, preds, ok, ids


# ------------------------------------------------------------------ matching
def ref_matches(pred: list[WordToken], ref: list[WordToken]) -> dict[int, tuple[int, WordToken]]:
    """Reference index -> (prediction index, predicted word) for matched words."""
    pairs = _align_token_sequences(pred, ref)[0]
    pi = {id(t): i for i, t in enumerate(pred)}
    ri = {id(t): i for i, t in enumerate(ref)}
    return {ri[id(g)]: (pi[id(p)], p) for p, g in pairs}


def boundary_errors_ms(pred: list[WordToken], ref: list[WordToken]) -> list[float]:
    out: list[float] = []
    for r_i, (_, p) in ref_matches(pred, ref).items():
        g = ref[r_i]
        out += [abs(p.start - g.start) * 1000.0, abs(p.end - g.end) * 1000.0]
    return out


def speaker_pooled(errors_by_speaker: dict[str, list[float]]) -> dict[str, float]:
    return {s: float(np.mean(v)) for s, v in sorted(errors_by_speaker.items()) if v}


def mean_ci(values: list[float]) -> dict[str, Any]:
    return {"mean": float(np.mean(values)), "ci_95": bootstrap_mean_ci(list(values))}


def check_frozen_mae(label: str, errors: list[float], frozen_mae: float) -> dict[str, Any]:
    mae = float(np.mean(errors))
    require(
        abs(round(mae, 2) - frozen_mae) <= 0.011,
        f"Sanity check failed for {label}: {mae:.4f} vs frozen {frozen_mae}",
    )
    return {"label": label, "recomputed_mae_ms": round(mae, 4), "frozen_mae_ms": frozen_mae}


def frozen_word_mae(results: dict, mode: str) -> float:
    return float(results["modes"][mode]["word_metrics"]["mae_ms"])


def all_errors(preds, ok, utts, mode) -> list[float]:
    errs: list[float] = []
    for uid in sorted(ok[mode]):
        errs += boundary_errors_ms(preds[mode][uid], utts[uid].ref_words)
    return errs


# ------------------------------------------------------------------ statistics
def auc_fast(labels: np.ndarray, scores: np.ndarray) -> float | None:
    """ROC-AUC by the rank statistic with average ranks for ties (vectorized)."""
    labels = np.asarray(labels, dtype=bool)
    pos, neg = int(labels.sum()), int((~labels).sum())
    if pos == 0 or neg == 0:
        return None
    _, inverse, counts = np.unique(scores, return_inverse=True, return_counts=True)
    upper = np.cumsum(counts)
    avg_rank = upper - (counts - 1) / 2.0
    ranks = avg_rank[inverse]
    return float((ranks[labels].sum() - pos * (pos + 1) / 2.0) / (pos * neg))


def percentile_rank(values: np.ndarray) -> np.ndarray:
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    upper = np.cumsum(counts)
    return (upper - (counts - 1) / 2.0)[inverse] / len(values)


def speaker_bootstrap_auc_diff(
    labels: np.ndarray, a: np.ndarray, b: np.ndarray, speakers: np.ndarray
) -> list[float]:
    """95% CI of AUC(a) - AUC(b), resampling speakers with replacement."""
    names = sorted(set(speakers.tolist()))
    index = {s: np.flatnonzero(speakers == s) for s in names}
    rng = np.random.default_rng(SEED)
    diffs = []
    for _ in range(RESAMPLES):
        take = np.concatenate([index[names[k]] for k in rng.integers(0, len(names), len(names))])
        x, y = auc_fast(labels[take], a[take]), auc_fast(labels[take], b[take])
        if x is not None and y is not None:
            diffs.append(x - y)
    return np.percentile(diffs, [2.5, 97.5]).tolist()


# ------------------------------------------------------------------ P-1
def oracle_pair(utts, preds, ok, ctc_mode: str, mfa_mode: str) -> dict[str, Any]:
    by = {k: defaultdict(list) for k in ("mfa", "ctc", "oracle", "average")}
    n_mfa_boundaries = n_common = 0
    for uid in sorted(ok[ctc_mode] & ok[mfa_mode]):
        ref = utts[uid].ref_words
        spk = utts[uid].speaker_id
        m = ref_matches(preds[mfa_mode][uid], ref)
        c = ref_matches(preds[ctc_mode][uid], ref)
        n_mfa_boundaries += 2 * len(m)
        for r_i in sorted(m.keys() & c.keys()):
            g, pm, pc = ref[r_i], m[r_i][1], c[r_i][1]
            for kind in ("start", "end"):
                gm, gp, gc = getattr(g, kind), getattr(pm, kind), getattr(pc, kind)
                em, ec = abs(gp - gm) * 1000, abs(gc - gm) * 1000
                by["mfa"][spk].append(em)
                by["ctc"][spk].append(ec)
                by["oracle"][spk].append(min(em, ec))
                by["average"][spk].append(abs((gp + gc) / 2 - gm) * 1000)
                n_common += 1
    n_mfa_total = sum(
        2 * len(ref_matches(preds[mfa_mode][u], utts[u].ref_words)) for u in ok[mfa_mode]
    )
    spk = {k: speaker_pooled(v) for k, v in by.items()}
    gain = [spk["mfa"][s] - spk["oracle"][s] for s in spk["mfa"]]
    avg_gain = [spk["mfa"][s] - spk["average"][s] for s in spk["mfa"]]
    return {
        "pair": [ctc_mode, mfa_mode],
        "n_speakers": len(spk["mfa"]),
        "n_common_boundaries": n_common,
        "share_of_mfa_boundaries_in_common_set": n_common / n_mfa_total if n_mfa_total else None,
        "share_within_jointly_successful_clips": n_common / n_mfa_boundaries
        if n_mfa_boundaries
        else None,
        "speaker_mean_mae_ms": {k: float(np.mean(list(v.values()))) for k, v in spk.items()},
        "pooled_mae_ms": {
            k: float(np.mean([e for lst in v.values() for e in lst])) for k, v in by.items()
        },
        "oracle_gain_ms": mean_ci(gain),
        "average_fusion_gain_ms": mean_ci(avg_gain),
    }


def run_p1() -> dict[str, Any]:
    out: dict[str, Any] = {"corpora": {}, "sanity": []}
    for name in ("buckeye", "timit"):
        results, preds, ok, _ = run_inputs(name)
        utts = corpus(name)
        for mode in (
            "A1_ctc",
            "A2_proposed",
            "A2_brqe",
            "B1_whisper_ctc",
            "B2_proposed",
            "B2_brqe",
        ):
            out["sanity"].append(
                check_frozen_mae(
                    f"{name}/{mode}",
                    all_errors(preds, ok, utts, mode),
                    frozen_word_mae(results, mode),
                )
            )
        pairs = [
            ("A1_ctc", "A2_proposed"),
            ("A1_ctc", "A2_brqe"),
            ("B1_whisper_ctc", "B2_proposed"),
            ("B1_whisper_ctc", "B2_brqe"),
        ]
        out["corpora"][name] = {f"{c}+{m}": oracle_pair(utts, preds, ok, c, m) for c, m in pairs}
    bk = out["corpora"]["buckeye"]
    gains = {
        "A": bk["A1_ctc+A2_brqe"]["oracle_gain_ms"]["mean"],
        "B": bk["B1_whisper_ctc+B2_brqe"]["oracle_gain_ms"]["mean"],
    }
    out["decision"] = {
        "rule": f"oracle gain over MFA+BRQE (speaker mean, Buckeye) >= {P1_DECISION_MS} ms in any scenario keeps G-4",
        "oracle_gain_over_brqe_ms": gains,
        "g4_status": "stays a candidate"
        if any(v >= P1_DECISION_MS for v in gains.values())
        else "closed",
    }
    return out


# ------------------------------------------------------------------ P-2
def mel_filterbank() -> np.ndarray:
    def hz_to_mel(f):
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel_to_hz(m):
        return 700.0 * (10 ** (m / 2595.0) - 1.0)

    mels = np.linspace(hz_to_mel(0.0), hz_to_mel(SR / 2), N_MELS + 2)
    hz = mel_to_hz(mels)
    bins = np.fft.rfftfreq(N_FFT, 1.0 / SR)
    fb = np.zeros((N_MELS, len(bins)))
    for k in range(N_MELS):
        lo, mid, hi = hz[k], hz[k + 1], hz[k + 2]
        up = (bins - lo) / (mid - lo)
        down = (hi - bins) / (hi - mid)
        fb[k] = np.maximum(0.0, np.minimum(up, down))
    return fb


_FB = None


def spectral_flux(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Times (s) and positive log-mel flux between consecutive 25 ms frames, 2.5 ms hop."""
    global _FB
    if _FB is None:
        _FB = mel_filterbank()
    if len(x) < WIN + HOP:
        return np.zeros(0), np.zeros(0)
    n = 1 + (len(x) - WIN) // HOP
    idx = np.arange(WIN)[None, :] + HOP * np.arange(n)[:, None]
    frames = x[idx] * np.hanning(WIN)[None, :]
    power = np.abs(np.fft.rfft(frames, N_FFT, axis=1)) ** 2
    logmel = np.log(power @ _FB.T + 1e-10)
    flux = np.maximum(0.0, np.diff(logmel, axis=0)).sum(axis=1)
    centers = (np.arange(n) * HOP + WIN / 2) / SR
    times = centers[1:] - (HOP / SR) / 2
    return times, flux


def snap_words(
    words: list[WordToken], times: np.ndarray, flux: np.ndarray, window: float, alpha: float
) -> tuple[list[WordToken], int]:
    """Move each unique boundary toward the flux peak within +-window (protocol P-2)."""
    unique = sorted({round(w.start, 6) for w in words} | {round(w.end, 6) for w in words})
    new: dict[float, float] = {}
    prev, kept_for_order = -math.inf, 0
    for t in unique:
        cand = t
        lo = int(np.searchsorted(times, t - window, side="left"))
        hi = int(np.searchsorted(times, t + window, side="right"))
        if hi > lo:
            peak = float(times[lo + int(np.argmax(flux[lo:hi]))])
            cand = t + alpha * (peak - t)
        if cand <= prev + 0.001:
            cand = t
            kept_for_order += 1
        new[t] = cand
        prev = cand
    out = []
    for w in words:
        s, e = new[round(w.start, 6)], new[round(w.end, 6)]
        if s >= e:
            s, e = w.start, w.end
        out.append(WordToken(w.id, w.text, w.normalized, s, e, w.confidence))
    return out, kept_for_order


def snapped_speaker_mae(utts, preds, ok, mode, flux_cache, window, alpha) -> dict[str, float]:
    by: dict[str, list[float]] = defaultdict(list)
    for uid in sorted(ok[mode]):
        times, flux = flux_cache[uid]
        words = preds[mode][uid]
        if window > 0:
            words, _ = snap_words(words, times, flux, window, alpha)
        by[utts[uid].speaker_id] += boundary_errors_ms(words, utts[uid].ref_words)
    return speaker_pooled(by)


def flux_for(uids, utts) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    return {u: spectral_flux(read_wav_mono(utts[u].wav_path)) for u in sorted(uids)}


def run_p2() -> dict[str, Any]:
    utts = corpus("buckeye")
    out: dict[str, Any] = {"sanity": [], "train": {}, "test": {}}
    t_res, t_preds, t_ok, _ = run_inputs("brqe_train_run")
    for mode in ("A2_proposed", "B2_proposed"):
        out["sanity"].append(
            check_frozen_mae(
                f"brqe_train_run/{mode}",
                all_errors(t_preds, t_ok, utts, mode),
                frozen_word_mae(t_res, mode),
            )
        )
    t_flux = flux_for(t_ok["A2_proposed"] | t_ok["B2_proposed"], utts)
    chosen: dict[str, dict[str, Any]] = {}
    for mode in ("A2_proposed", "B2_proposed"):
        base = snapped_speaker_mae(utts, t_preds, t_ok, mode, t_flux, 0.0, 0.0)
        base_mean = float(np.mean(list(base.values())))
        grid = []
        for window, alpha in P2_GRID:
            spk = snapped_speaker_mae(utts, t_preds, t_ok, mode, t_flux, window, alpha)
            grid.append(
                {
                    "window_ms": round(window * 1000),
                    "alpha": alpha,
                    "speaker_mean_mae_ms": float(np.mean(list(spk.values()))),
                    "gain_ms": base_mean - float(np.mean(list(spk.values()))),
                }
            )
        best = min(grid, key=lambda g: g["speaker_mean_mae_ms"])
        passes = best["gain_ms"] >= P2_MIN_TRAIN_GAIN_MS
        out["train"][mode] = {
            "n_speakers": len(base),
            "mfa_speaker_mean_mae_ms": base_mean,
            "grid": grid,
            "selected": best,
            "goes_to_test": passes,
        }
        if passes:
            chosen[mode] = best
    if chosen:
        results, preds, ok, _ = run_inputs("buckeye")
        e_flux = flux_for(set().union(*(ok[m] for m in chosen)), utts)
        tests: dict[str, Any] = {}
        for mode, cfg in chosen.items():
            brqe = mode.replace("_proposed", "_brqe")
            snap = snapped_speaker_mae(
                utts, preds, ok, mode, e_flux, cfg["window_ms"] / 1000, cfg["alpha"]
            )
            mfa = snapped_speaker_mae(utts, preds, ok, mode, e_flux, 0.0, 0.0)
            by: dict[str, list[float]] = defaultdict(list)
            for uid in sorted(ok[brqe]):
                by[utts[uid].speaker_id] += boundary_errors_ms(
                    preds[brqe][uid], utts[uid].ref_words
                )
            brqe_spk = speaker_pooled(by)
            out["test"][mode] = {
                "config": cfg,
                "speaker_mean_mae_ms": {
                    "snap": float(np.mean(list(snap.values()))),
                    "mfa": float(np.mean(list(mfa.values()))),
                    "brqe": float(np.mean(list(brqe_spk.values()))),
                },
            }
            tests[f"{mode}: snap vs MFA"] = paired_test(mfa, snap)
            tests[f"{mode}: snap vs MFA+BRQE"] = paired_test(brqe_spk, snap)
        adj = holm({k: v.get("p_value_raw") for k, v in tests.items()})
        for k in tests:
            tests[k]["p_value_holm"] = adj[k]
        out["test"]["comparisons"] = tests
    return out


# ------------------------------------------------------------------ P-3
def run_p3() -> dict[str, Any]:
    utts = corpus("buckeye")
    f_res, f_preds, f_ok, f_ids = run_inputs("buckeye")
    out: dict[str, Any] = {"sanity": [], "modes": {}}
    for mode in ("B2_proposed", "B2_brqe"):
        conds, retained = {}, {}
        base_by_model = {}
        for model in S3_MODELS:
            run = f"{S3_DIR}/buckeye_{model}"
            m_res, m_preds, m_ok, _ = run_inputs(run)
            if mode == "B2_proposed":
                out["sanity"].append(
                    check_frozen_mae(
                        f"s3/{model}/{mode}",
                        all_errors(m_preds, m_ok, utts, mode),
                        frozen_word_mae(m_res, mode),
                    )
                )
            base_clips: dict[str, list[float]] = defaultdict(list)
            cond_clips: dict[str, list[float]] = defaultdict(list)
            kept = total = clips = 0
            for uid in sorted(f_ok[mode] & m_ok[mode]):
                ref = utts[uid].ref_words
                a = ref_matches(f_preds[mode][uid], ref)
                b = ref_matches(m_preds[mode][uid], ref)
                total += len(a)
                common = sorted(a.keys() & b.keys())
                if not common:
                    continue
                clips += 1
                kept += len(common)
                ea, eb = [], []
                for r_i in common:
                    g = ref[r_i]
                    for kind in ("start", "end"):
                        ea.append(abs(getattr(a[r_i][1], kind) - getattr(g, kind)) * 1000)
                        eb.append(abs(getattr(b[r_i][1], kind) - getattr(g, kind)) * 1000)
                spk = utts[uid].speaker_id
                base_clips[spk].append(float(np.mean(ea)))
                cond_clips[spk].append(float(np.mean(eb)))
            base_spk = {s: float(np.mean(v)) for s, v in base_clips.items()}
            cond_spk = {s: float(np.mean(v)) for s, v in cond_clips.items()}
            base_by_model[model] = base_spk
            conds[model] = paired_test(base_spk, cond_spk)
            conds[model]["speaker_mean_mae_ms"] = {
                "large-v3": float(np.mean(list(base_spk.values()))),
                model: float(np.mean(list(cond_spk.values()))),
            }
            retained[model] = {
                "share_of_large_v3_matched_words": kept / total if total else None,
                "clips": clips,
                "speakers": len(base_spk),
            }
        adj = holm({m: t.get("p_value_raw") for m, t in conds.items()})
        for m in conds:
            conds[m]["p_value_holm"] = adj[m]
        out["modes"][mode] = {"comparisons": conds, "retained": retained}
    return out


# ------------------------------------------------------------------ P-4
def detector_scenario(
    utts, preds, ok, base_mode, brqe_mode, ctc_mode, frozen_auc
) -> dict[str, Any]:
    full_labels, full_scores = [], []
    labels, s_brqe, s_dis, speakers = [], [], [], []
    for uid in sorted(ok[base_mode] & ok[brqe_mode]):
        ref = utts[uid].ref_words
        base, refined = preds[base_mode][uid], preds[brqe_mode][uid]
        ctc = preds[ctc_mode].get(uid)
        c = ref_matches(ctc, ref) if uid in ok[ctc_mode] and not isinstance(ctc, str) else {}
        for r_i, (b_i, bw) in ref_matches(base, ref).items():
            g = ref[r_i]
            y = max(abs(bw.start - g.start), abs(bw.end - g.end)) > 0.02
            sb = 1.0 - refined[b_i].confidence
            full_labels.append(y)
            full_scores.append(sb)
            if r_i in c:
                cw = c[r_i][1]
                labels.append(y)
                s_brqe.append(sb)
                s_dis.append(max(abs(cw.start - bw.start), abs(cw.end - bw.end)) * 1000)
                speakers.append(utts[uid].speaker_id)
    full_auc = roc_auc(np.array(full_labels), np.array(full_scores))
    require(
        abs(round(full_auc, 3) - round(frozen_auc, 3)) <= 0.001,
        f"Reliability AUC mismatch: {full_auc} vs {frozen_auc}",
    )
    y, b, d = np.array(labels), np.array(s_brqe), np.array(s_dis)
    comb = (percentile_rank(b) + percentile_rank(d)) / 2.0
    spk = np.array(speakers)
    require(abs(auc_fast(y, b) - roc_auc(y, b)) < 1e-9, "Fast AUC differs from reference AUC")
    ci_comb = speaker_bootstrap_auc_diff(y, comb, b, spk)
    return {
        "n_words_full": len(full_labels),
        "brqe_auc_full_recomputed": full_auc,
        "brqe_auc_full_frozen": frozen_auc,
        "n_words_evaluated": int(len(y)),
        "share_of_full": len(y) / len(full_labels),
        "positive_rate": float(y.mean()),
        "roc_auc": {
            "brqe": auc_fast(y, b),
            "disagreement": auc_fast(y, d),
            "combined": auc_fast(y, comb),
        },
        "pr_auc": {"brqe": pr_auc(y, b), "disagreement": pr_auc(y, d), "combined": pr_auc(y, comb)},
        "auc_combined_minus_brqe_ci_95": ci_comb,
        "auc_disagreement_minus_brqe_ci_95": speaker_bootstrap_auc_diff(y, d, b, spk),
        "complements_brqe": bool(ci_comb[0] > 0),
    }


def run_p4() -> dict[str, Any]:
    utts = corpus("buckeye")
    results, preds, ok, _ = run_inputs("buckeye")
    out: dict[str, Any] = {"scenarios": {}, "s1b": {}}
    for sc, base, brqe, ctc in (
        ("A", "A2_proposed", "A2_brqe", "A1_ctc"),
        ("B", "B2_proposed", "B2_brqe", "B1_whisper_ctc"),
    ):
        frozen = results["modes"][brqe]["quality_estimation"]["roc_auc"]
        out["scenarios"][sc] = detector_scenario(utts, preds, ok, base, brqe, ctc, frozen)
    for length in ("L01", "L05", "L10"):
        rows = read_json(
            f"reports/s1b_long_20261103/runs/{length}_anchored/benchmark_utterances.json"
        )
        status = {(r["mode"], r["utterance"]): r["status"] for r in rows}
        recs = sorted({r["utterance"] for r in rows})
        entry = {}
        for mfa, ctc in (("A2_proposed", "A1_ctc"), ("B2_proposed", "B1_whisper_ctc")):
            failed = [u for u in recs if status.get((mfa, u)) != "ok"]
            entry[mfa] = {
                "recordings": len(recs),
                "mfa_failed": len(failed),
                "mfa_failed_ctc_ok": sum(status.get((ctc, u)) == "ok" for u in failed),
            }
        out["s1b"][length] = entry
    return out


# ------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("analysis", choices=["p1", "p2", "p3", "p4", "all"])
    args = p.parse_args(argv)
    todo = ["p1", "p3", "p4", "p2"] if args.analysis == "all" else [args.analysis]
    funcs = {"p1": run_p1, "p2": run_p2, "p3": run_p3, "p4": run_p4}
    OUT.mkdir(parents=True, exist_ok=True)
    for name in todo:
        started = time.perf_counter()
        print(f"[*] {name} started", flush=True)
        result = funcs[name]()
        result["meta"] = {
            "protocol": "docs/P1_P4_PROTOCOL.md",
            "finished": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "seconds": round(time.perf_counter() - started, 1),
            "code": code_provenance(),
        }
        write_json(OUT / f"{name}.json", result)
        print(f"[+] {name} done in {result['meta']['seconds']} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
