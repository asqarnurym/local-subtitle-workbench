import json
from pathlib import Path
D = Path(__file__).resolve().parent
mine = json.loads((D / "independent_check.json").read_text())["corpora"]
auth = json.loads((D.parent / "fa_extras.json").read_text())["corpora"]
recs = []
def cmp(path, a, b, ms):
    if a is None or b is None:
        st = "match" if a is None and b is None else "mismatch"; d = None
    else:
        d = abs(a - b)
        tol = 0.01 if ms else 0.005 * max(abs(a), abs(b), 1e-12)
        if not ms: tol = max(tol, 0.005) if False else tol
        st = "match" if d <= 1e-6 else ("close" if (d <= 0.01 if ms else (d <= 0.005 or d <= 0.005 * max(abs(a), abs(b)))) else "mismatch")
    recs.append({"path": path, "author": a, "independent": b, "abs_diff": d, "status": st})
for c in mine:
    for m, mv in mine[c]["modes"].items():
        av = auth[c]["modes"][m]
        for g, gv in mv["groups"].items():
            for k in ("n", "share", "recall20", "mae_ms_matched"):
                cmp(f"{c}.{m}.groups.{g}.{k}", av["groups"][g][k], gv[k], k.endswith("_ms_matched"))
        for t, tv in mv["f1_sweep"].items():
            for k in ("precision", "recall", "f1"):
                cmp(f"{c}.{m}.f1_sweep.{t}.{k}", av["f1_sweep"][t][k], tv[k], False)
            for i in (0, 1):
                cmp(f"{c}.{m}.f1_sweep.{t}.f1_ci_95[{i}]", av["f1_sweep"][t]["f1_ci_95"][i], tv["f1_ci_95"][i], False)
        for k in ("mean_signed_start_ms", "mean_signed_end_ms", "mean_signed_duration_ms"):
            cmp(f"{c}.{m}.signed.{k}", av["signed"][k], mv["signed"][k], True)
            for i in (0, 1):
                cmp(f"{c}.{m}.signed.{k}_ci_95[{i}]", av["signed"][k + "_ci_95"][i], mv["signed"][k + "_ci_95"][i], True)
        for k in ("mean_abs_duration_ms", "boundary_mae_ms"):
            cmp(f"{c}.{m}.signed.{k}", av["signed"][k], mv["signed"][k], True)
        cmp(f"{c}.{m}.n_failed_clips", av["n_failed_clips"], mv["n_failed_clips"], False)
summary = {s: sum(r["status"] == s for r in recs) for s in ("match", "close", "mismatch")}
(D / "compare.json").write_text(json.dumps({"summary": summary, "total": len(recs),
    "non_match": [r for r in recs if r["status"] != "match"], "all": recs}, indent=1))
print(summary, len(recs))
for r in recs:
    if r["status"] != "match": print(r)
