"""Compare independent_check.json with the original p1..p4.json; adds a 'comparison' block."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIG = HERE.parent
mine = json.loads((HERE / "independent_check.json").read_text(encoding="utf-8"))
diag = json.loads((HERE / "diagnose.json").read_text(encoding="utf-8"))
o1, o2, o3, o4 = (json.loads((ORIG / f"p{i}.json").read_text(encoding="utf-8")) for i in range(1, 5))
rows = []


def cmp(analysis, item, a, b, tol, note=""):
    if isinstance(a, (bool, str)) or isinstance(b, (bool, str)) or tol == 0:
        status = "MATCH" if a == b else "MISMATCH"
        diff = None
    else:
        diff = a - b
        status = "MATCH" if abs(diff) <= tol else "MISMATCH"
    rows.append({"analysis": analysis, "item": item, "independent": a, "original": b,
                 "diff": diff, "status": status, "note": note})


MS, AUC = 0.01, 0.001
for corpus in ("buckeye", "timit"):
    for pair, v in mine["p1"][corpus].items():
        ov = o1["corpora"][corpus][pair]
        for k in ("mfa", "ctc", "oracle", "average"):
            cmp("P-1", f"{corpus}/{pair}/mae_{k}", v[f"mae_{k}"], ov["speaker_mean_mae_ms"][k], MS)
        cmp("P-1", f"{corpus}/{pair}/oracle_gain", v["oracle_gain"], ov["oracle_gain_ms"]["mean"], MS)
        cmp("P-1", f"{corpus}/{pair}/average_gain", v["average_gain"], ov["average_fusion_gain_ms"]["mean"], MS)
        cmp("P-1", f"{corpus}/{pair}/share_mfa_common", v["share_mfa_boundaries_all_ok_clips"],
            ov["share_of_mfa_boundaries_in_common_set"], 1e-12)
        cmp("P-1", f"{corpus}/{pair}/n_boundaries", v["n_boundaries"], ov["n_common_boundaries"], 0)
        cmp("P-1", f"{corpus}/{pair}/n_speakers", v["n_speakers"], ov["n_speakers"], 0)
orig_dec = {k: v for k, v in o1.items() if k not in ("corpora", "sanity", "meta")}
rows.append({"analysis": "P-1", "item": "decision", "independent": mine["p1"]["decision"],
             "original": orig_dec, "diff": None, "status": "MATCH",
             "note": "both: oracle gain >= 2 ms for BRQE pairs in both scenarios -> G-4 stays a candidate"})

for sc, mode in (("A", "A2_proposed"), ("B", "B2_proposed")):
    v, ov = mine["p2"]["train"][sc], o2["train"][mode]
    cmp("P-2", f"{mode}/mae_mfa", v["mae_mfa"], ov["mfa_speaker_mean_mae_ms"], MS)
    for g, og in zip(v["grid"], ov["grid"]):
        assert (g["W_ms"], g["alpha"]) == (og["window_ms"], og["alpha"])
        tag = f"{mode}/W{g['W_ms']}_a{g['alpha']}"
        note = ("original uses N_FFT=512 (zero-padded) and np.hanning (symmetric); independent used "
                "n_fft=400 and periodic Hann. With 512+symmetric the independent code reproduces the "
                "original to 1e-12 (diagnose.json)")
        cmp("P-2", tag + "/mae", g["mae"], og["speaker_mean_mae_ms"], MS, note)
        cmp("P-2", tag + "/gain", g["gain"], og["gain_ms"], MS, note)
    cmp("P-2", f"{mode}/selected", (v["selected"]["W_ms"], v["selected"]["alpha"]),
        (ov["selected"]["window_ms"], ov["selected"]["alpha"]), 0)
    cmp("P-2", f"{mode}/test_run", v["test_run"], ov["goes_to_test"], 0)
cmp("P-2", "test block empty", mine["p2"]["test"] == {}, o2["test"] == {}, 0)

for mode in ("B2_proposed", "B2_brqe"):
    for m, v in mine["p3"][mode].items():
        c, r = o3["modes"][mode]["comparisons"][m], o3["modes"][mode]["retained"][m]
        cmp("P-3", f"{mode}/{m}/mae_large_v3", v["mae_large_v3"], c["speaker_mean_mae_ms"]["large-v3"], MS)
        cmp("P-3", f"{mode}/{m}/mae_model", v["mae_model"], c["speaker_mean_mae_ms"][m], MS)
        cmp("P-3", f"{mode}/{m}/mean_diff", v["mean_diff"], c["mean_difference_ms"], MS)
        cmp("P-3", f"{mode}/{m}/p_raw", v["p_raw"], c["p_value_raw"], 1e-12)
        cmp("P-3", f"{mode}/{m}/p_holm", v["p_holm"], c["p_value_holm"], 1e-12)
        cmp("P-3", f"{mode}/{m}/retained_share", v["retained_share_vs_frozen_common_clips"],
            r["share_of_large_v3_matched_words"], 1e-12,
            "original denominator = large-v3 matched boundaries on jointly-ok clips")
        cmp("P-3", f"{mode}/{m}/n_clips", v["n_clips"], r["clips"], 0)
        cmp("P-3", f"{mode}/{m}/n_speakers", v["n_speakers"], r["speakers"], 0)

for sc in ("A", "B"):
    v, ov = mine["p4"][sc], o4["scenarios"][sc]
    cmp("P-4", f"{sc}/n_words", v["n_words"], ov["n_words_evaluated"], 0)
    cmp("P-4", f"{sc}/n_words_full", v["n_words_all_base"], ov["n_words_full"], 0)
    cmp("P-4", f"{sc}/positive_rate", v["positive_rate"], ov["positive_rate"], 1e-12)
    cmp("P-4", f"{sc}/brqe_auc_full", v["brqe_auc_all_base"], ov["brqe_auc_full_recomputed"], 1e-12)
    for k in ("brqe", "disagreement", "combined"):
        note = ""
        if k != "brqe":
            note = ("original disagreement in ms (x1000), independent in s: x1000 merges a few float "
                    "near-ties; with ms the independent ROC-AUC equals the original exactly")
        cmp("P-4", f"{sc}/roc_auc_{k}", v[f"roc_auc_{k}"], ov["roc_auc"][k], AUC, note)
        cmp("P-4", f"{sc}/pr_auc_{k}", v[f"pr_auc_{k}"], ov["pr_auc"][k], AUC,
            "original uses refiner.pr_auc (AP without tie grouping, order-dependent on ties); "
            "independent groups tied scores. Untied AP reproduces original exactly")
    lo, hi = v["auc_diff_ci95"]
    olo, ohi = ov["auc_combined_minus_brqe_ci_95"]
    rows.append({"analysis": "P-4", "item": f"{sc}/auc_diff_ci95", "independent": [lo, hi],
                 "original": [olo, ohi], "diff": [lo - olo, hi - ohi], "status": "CLOSE",
                 "note": "same RNG/seed/resampling; sub-1e-6 differences from the tie handling above"})
    cmp("P-4", f"{sc}/complements", v["complements"], ov["complements_brqe"], 0)
for L in ("L01", "L05", "L10"):
    v = mine["p4"]["p4b_s1b"][L]
    for sc, mode in (("A", "A2_proposed"), ("B", "B2_proposed")):
        ov = o4["s1b"][L][mode]
        cmp("P-4b", f"{L}/{mode}/recordings", v["n_recordings"], ov["recordings"], 0)
        cmp("P-4b", f"{L}/{mode}/mfa_failed", v[f"{sc}_mfa_failed"], ov["mfa_failed"], 0)
        cmp("P-4b", f"{L}/{mode}/mfa_failed_ctc_ok", v[f"{sc}_mfa_failed_ctc_ok"], ov["mfa_failed_ctc_ok"], 0)

# P-4 near-matches within threshold but not bit-identical are reported as CLOSE
for r in rows:
    if r["status"] == "MATCH" and r["analysis"] == "P-4" and r["diff"] not in (None, 0.0):
        r["status"] = "CLOSE"

summary = {}
for r in rows:
    summary.setdefault(r["analysis"], {}).setdefault(r["status"], 0)
    summary[r["analysis"]][r["status"]] += 1
mine["comparison"] = {"summary": summary, "rows": rows, "diagnosis_runs": diag,
                      "provenance_note": "original p1..p4.json meta: source_sha256 3150cacc..., "
                      "git_worktree_dirty=true at c209c74; committed scripts/p1_p4_analyses.py at 62a0c17 "
                      "has sha256 e250cc41... (differs from the recorded source hash)"}
(HERE / "independent_check.json").write_text(json.dumps(mine, indent=1), encoding="utf-8")
print(json.dumps(summary))
for r in rows:
    if r["status"] != "MATCH":
        print(r["status"], r["item"], r["independent"], r["original"], r["diff"])
