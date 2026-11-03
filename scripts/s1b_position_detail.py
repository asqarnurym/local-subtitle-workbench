"""Descriptive per-minute error detail of the 10-minute S1b runs (read-only, no models).

Added after the run: the protocol's position analysis has means only. Means here jump on
local failures, so this adds medians, tails and each speaker's mean per minute.

Run: uv run --locked --all-extras python scripts/s1b_position_detail.py
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import s1_long_recordings as s1  # noqa: E402

OUT = ROOT / "reports/s1b_long_20261103"
MODES = ("A2_proposed", "A2_brqe", "B2_proposed", "B2_brqe")


def minute_row(minute: int, speakers: dict) -> dict:
    vals: list[float] = []
    per: dict[str, dict] = {}
    for spk, words in speakers.items():
        v = [e for _, s, es, ee in words if 60 * minute <= s < 60 * (minute + 1) for e in (es, ee)]
        vals += v
        if v:
            per[spk] = {"n": len(v), "sum": float(np.sum(v)), "max": float(np.max(v))}
    a = np.asarray(vals)
    top = sorted(per.items(), key=lambda kv: -kv[1]["sum"])[:3]
    return {
        "minute": minute,
        "n": len(vals),
        "mean": float(a.mean()),
        "median": float(np.median(a)),
        "p95": float(np.percentile(a, 95)),
        "max": float(a.max()),
        "n_over_500ms": int((a > 500).sum()),
        "mean_without_top": float((a.sum() - top[0][1]["sum"]) / (len(a) - top[0][1]["n"])),
        "top": [(k, round(v["sum"] / v["n"], 1), v["n"], round(v["max"])) for k, v in top],
        "speaker_means": {k: round(v["sum"] / v["n"], 2) for k, v in per.items()},
    }


def main() -> int:
    data = s1.load_run(OUT, s1.check_build(OUT), "L10", "anchored")
    result = {}
    for mode in MODES:
        ok = {k: w for k, w in data[mode].items() if not isinstance(w, str)}
        result[mode] = {"n_speakers": len(ok), "minutes": [minute_row(m, ok) for m in range(10)]}
    text = json.dumps(result, ensure_ascii=False, indent=1)
    (OUT / "position_detail.json").write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
