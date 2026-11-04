"""S2 errors on the original speech scale, with speaker-paired tests (no models are run).

The protocol's tests compare milliseconds of the stretched recording, and stretching alone
changes those: a recording played at rate r has every interval divided by r. The protocol
also asks for the error multiplied by the rate. This script adds speaker-paired tests of
that scaled error, Holm within each mode. They were added after the numbers were known.

Run: uv run --locked --all-extras python scripts/s2_scaled_detail.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import s1_long_recordings as s1  # noqa: E402
from scripts import s2_s3_substudies as sub  # noqa: E402

OUT = ROOT / "reports/s2_tempo_20261103"
MODES = ("A2_proposed", "A2_brqe", "B2_proposed", "B2_brqe")
RATES = (0.8, 0.9, 1.1, 1.25)


def scaled(run: dict, mode: str, rate: float) -> dict:
    return {s: v * rate for s, v in run[mode]["speaker_mae_ms"].items()}


def corpus_detail(runs: dict, corpus: str) -> dict:
    base_run = runs[f"{corpus}_r1.00"]
    result: dict = {}
    for mode in MODES:
        base = base_run[mode]["speaker_mae_ms"]
        tests = {}
        for rate in RATES:
            cond = scaled(runs[f"{corpus}_r{rate:.2f}"], mode, rate)
            tests[f"r{rate:.2f}"] = s1.paired_test(base, {s: cond.get(s) for s in base})
        adj = sub.holm({k: t.get("p_value_raw") for k, t in tests.items()})
        for k, t in tests.items():
            t["p_value_holm"] = adj[k]
            t.pop("per_speaker_difference_ms", None)
        means = {"r1.00": base_run[mode]["mean_speaker_mae_ms"]}
        for rate in RATES:
            r = runs[f"{corpus}_r{rate:.2f}"][mode]
            means[f"r{rate:.2f}"] = r["mean_speaker_mae_ms"] * rate
        result[mode] = {"scaled_mean_ms": means, "tests_vs_r1.00": tests}
    return result


def main() -> int:
    runs = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))["runs"]
    result = {c: corpus_detail(runs, c) for c in ("timit", "buckeye")}
    text = json.dumps(result, ensure_ascii=False, indent=1)
    (OUT / "scaled_detail.json").write_text(text, encoding="utf-8")
    for corpus, modes in result.items():
        for mode, r in modes.items():
            means = " ".join(f"{k}={v:.2f}" for k, v in sorted(r["scaled_mean_ms"].items()))
            print(corpus, mode, means)
            for k, t in r["tests_vs_r1.00"].items():
                ci = t.get("mean_difference_ci_95_ms") or [float("nan")] * 2
                print(
                    f"   {k}: n={t['n_pairs']} diff={t.get('mean_difference_ms', 0):+.2f} "
                    f"ci={ci[0]:+.2f}..{ci[1]:+.2f} worse={t.get('n_worse')} "
                    f"holm={t['p_value_holm']:.4g}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
