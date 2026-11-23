"""Figure: boundary F1 against tolerance on Buckeye (docs/FA_EXTRAS_PROTOCOL.md §2).

uv run --no-project --with matplotlib==3.11.2 python scripts/render_fa_extras.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "reports" / "fa_extras_20261123"
SERIES = [
    ("B0_whisper", "B0 Whisper timestamps", "#7f7f7f", ":"),
    ("B1_whisper_ctc", "B1 Whisper + CTC", "#d62728", "--"),
    ("B2_proposed", "B2 Whisper + MFA", "#1f77b4", "--"),
    ("B2_brqe", "B2 + BRQE", "#1f77b4", "-"),
    ("A1_ctc", "A1 known text + CTC", "#ff7f0e", "--"),
    ("A2_proposed", "A2 known text + MFA", "#2ca02c", "--"),
    ("A2_brqe", "A2 + BRQE", "#2ca02c", "-"),
]


def main() -> None:
    data = json.loads((DIR / "fa_extras.json").read_text(encoding="utf-8"))
    plt.rcParams.update(
        {
            "font.family": "DejaVu Serif",
            "font.size": 9,
            "axes.titlesize": 9,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "pdf.fonttype": 42,
            "mathtext.fontset": "dejavuserif",
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.2), layout="constrained", sharey=True)
    for ax, corpus, title in zip(
        axes, ("buckeye", "timit"), ("Buckeye (spontaneous)", "TIMIT (read)"), strict=True
    ):
        modes = data["corpora"][corpus]["modes"]
        for mode, label, color, style in SERIES:
            sweep = modes[mode]["f1_sweep"]
            tols = [int(t) for t in sweep]
            f1 = [sweep[t]["f1"] for t in sweep]
            lo = [sweep[t]["f1_ci_95"][0] for t in sweep]
            hi = [sweep[t]["f1_ci_95"][1] for t in sweep]
            ax.plot(tols, f1, style, color=color, label=label, linewidth=1.4)
            ax.fill_between(tols, lo, hi, color=color, alpha=0.12, linewidth=0)
        ax.set_title(title)
        ax.set_xlabel("Tolerance (ms)")
        ax.set_xlim(10, 100)
        ax.set_ylim(0, 1)
        ax.grid(alpha=0.3, linewidth=0.5)
    axes[0].set_ylabel("Boundary F1")
    axes[1].legend(loc="lower right", frameon=False)
    for ext in ("pdf", "png"):
        fig.savefig(DIR / f"f1_tolerance_en.{ext}", dpi=300)
    print("saved", DIR / "f1_tolerance_en.pdf")


if __name__ == "__main__":
    main()
