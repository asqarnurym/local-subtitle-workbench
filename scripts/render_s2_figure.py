"""S2 figure: word error on the original speech scale by tempo (no models are run).

Input: reports/s2_tempo_20261103/scaled_detail.json (scripts/s2_scaled_detail.py).
Run: uv run --no-project --with matplotlib==3.11.2 python scripts/render_s2_figure.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reports/s2_tempo_20261103"
RATES = [("r0.80", 0.8), ("r0.90", 0.9), ("r1.00", 1.0), ("r1.10", 1.1), ("r1.25", 1.25)]
SERIES = (
    ("A2_proposed", "A2", "#1f77b4", "o", "-"),
    ("A2_brqe", "A2+BRQE", "#1f77b4", "s", "--"),
    ("B2_proposed", "B2", "#ff7f0e", "o", "-"),
    ("B2_brqe", "B2+BRQE", "#ff7f0e", "s", "--"),
)
TEXT = {
    "ru": {"x": "Темп записи", "y": "MAE слов в масштабе исходной речи, мс", "sep": ","},
    "en": {"x": "Recording tempo", "y": "Word MAE on the original speech scale, ms", "sep": "."},
}


def render(detail: dict, lang: str) -> None:
    text = TEXT[lang]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.3), sharey=True)
    for ax, corpus, title in ((axes[0], "timit", "TIMIT"), (axes[1], "buckeye", "Buckeye")):
        for mode, label, color, marker, ls in SERIES:
            means = detail[corpus][mode]["scaled_mean_ms"]
            ax.plot(
                [r for _, r in RATES],
                [means[k] for k, _ in RATES],
                color=color,
                marker=marker,
                ms=4,
                ls=ls,
                lw=1.8,
                label=label,
            )
        ax.axvline(1.0, color="#999999", lw=0.8, ls=":")
        ax.set_xticks([r for _, r in RATES])
        ax.set_xticklabels([f"{r:g}".replace(".", text["sep"]) for _, r in RATES])
        ax.set_ylim(10, 35)
        ax.set_xlabel(text["x"])
        ax.set_title(title, fontsize=9)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel(text["y"])
    axes[1].legend(frameon=False, ncols=2, loc="upper right", fontsize=8)
    fig.tight_layout()
    path = BASE / "figures" / f"s2_tempo_{lang}"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path.with_suffix(".png"), dpi=300)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def main() -> int:
    detail = json.loads((BASE / "scaled_detail.json").read_text(encoding="utf-8"))
    plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 9, "pdf.fonttype": 42})
    for lang in TEXT:
        render(detail, lang)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
