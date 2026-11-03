"""Russian and English S1b figures from stored analysis files (no models are run).

Inputs:
- reports/s1b_long_20261103/analysis.json (failed recordings per run);
- reports/s1b_long_20261103/position_detail.json (scripts/s1b_position_detail.py);
- failed-chunk counts from docs/MFA_FAILURE_BACKLOG.md, section 1.

Run: uv run --no-project --with matplotlib==3.11.2 python scripts/render_s1b_figures.py
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BLUE, ORANGE, GREY = "#1f77b4", "#ff7f0e", "#555555"
LENGTHS = ["L01", "L05", "L10"]
# failed / total chunks, docs/MFA_FAILURE_BACKLOG.md section 1
CHUNKS = {"A": [(0, 62), (4, 269), (7, 533)], "B": [(3, 62), (10, 257), (23, 501)]}
TEXT = {
    "ru": {
        "decimal": ",",
        "minute": "Минута записи",
        "ms": "Ошибка границ слов, мс (лог. шкала)",
        "mean": "среднее",
        "median": "медиана",
        "panel_a": "Известный текст (A2), {n} записей из 20",
        "panel_b": "Текст Whisper (B2), {n} записей из 20",
        "lengths": ["1 мин", "5 мин", "10 мин"],
        "failed": "Записи со сбоем, из 20",
        "share": "Доля невыровненных чанков, %",
        "series": ["A2, с якорями", "B2, с якорями", "A2, без якорей"],
        "chunk_series": ["A2, с якорями", "B2, с якорями"],
    },
    "en": {
        "decimal": ".",
        "minute": "Minute of recording",
        "ms": "Word boundary error, ms (log scale)",
        "mean": "mean",
        "median": "median",
        "panel_a": "Known text (A2), {n} of 20 recordings",
        "panel_b": "Whisper text (B2), {n} of 20 recordings",
        "lengths": ["1 min", "5 min", "10 min"],
        "failed": "Failed recordings, of 20",
        "share": "Unaligned chunks, %",
        "series": ["A2, anchored", "B2, anchored", "A2, no anchors"],
        "chunk_series": ["A2, anchored", "B2, anchored"],
    },
}


def position(detail: dict, text: dict, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.3), sharey=True)
    for ax, mode, color, title in (
        (axes[0], "A2_proposed", BLUE, "panel_a"),
        (axes[1], "B2_proposed", ORANGE, "panel_b"),
    ):
        rows = detail[mode]["minutes"]
        x = [r["minute"] + 1 for r in rows]
        ax.plot(
            x, [r["mean"] for r in rows], color=color, lw=1.8, marker="o", ms=4, label=text["mean"]
        )
        ax.plot(
            x,
            [r["median"] for r in rows],
            color=GREY,
            lw=1.8,
            ls="--",
            marker="s",
            ms=4,
            label=text["median"],
        )
        ax.set_yscale("log")
        ax.set_ylim(5, 200)
        ax.set_yticks([5, 10, 20, 50, 100, 200])
        ax.set_yticklabels(["5", "10", "20", "50", "100", "200"])
        ax.minorticks_off()
        ax.set_xticks(range(1, 11))
        ax.set_xlabel(text["minute"])
        ax.set_title(text[title].format(n=detail[mode]["n_speakers"]), fontsize=9)
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, loc="upper left")
    axes[0].set_ylabel(text["ms"])
    save(fig, path)


def failures(analysis: dict, text: dict, path: Path) -> None:
    runs = analysis["runs"]
    series = [
        [runs[f"{L}_anchored"]["modes"]["A2_proposed"]["failed"] for L in LENGTHS],
        [runs[f"{L}_anchored"]["modes"]["B2_proposed"]["failed"] for L in LENGTHS],
        [runs[f"{L}_noanchor"]["modes"]["A2_proposed"]["failed"] for L in LENGTHS],
    ]
    fig, (left, right) = plt.subplots(1, 2, figsize=(7.4, 3.2))
    width = 0.26
    for k, (vals, color, hatch) in enumerate(
        zip(series, (BLUE, ORANGE, "#bbbbbb"), ("", "", "//"), strict=True)
    ):
        xs = [i + (k - 1) * width for i in range(3)]
        bars = left.bar(
            xs,
            vals,
            width * 0.92,
            color=color,
            hatch=hatch,
            edgecolor="white",
            label=text["series"][k],
        )
        left.bar_label(bars, padding=1, fontsize=8)
    left.set_xticks(range(3), text["lengths"])
    left.set_ylim(0, 25)
    left.set_ylabel(text["failed"])
    left.legend(frameon=False, loc="upper left", ncols=2, fontsize=8)
    left.grid(axis="y", alpha=0.25)
    for key, color, marker, ls, label in (
        ("A", BLUE, "o", "-", text["chunk_series"][0]),
        ("B", ORANGE, "s", "--", text["chunk_series"][1]),
    ):
        vals = [100 * f / n for f, n in CHUNKS[key]]
        right.plot(
            range(3), vals, color=color, marker=marker, ls=ls, lw=1.8, label=label, clip_on=False
        )
        for i, v in enumerate(vals):
            label_v = f"{v:.1f}".replace(".", text["decimal"])
            right.annotate(
                label_v, (i, v), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8
            )
    right.set_xticks(range(3), text["lengths"])
    right.set_xlim(-0.3, 2.3)
    right.set_ylim(0, 8)
    right.set_ylabel(text["share"])
    right.legend(frameon=False, loc="upper left", fontsize=8)
    right.grid(alpha=0.25)
    save(fig, path)


def save(fig, path: Path) -> None:
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path.with_suffix(".png"), dpi=300)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args()
    base = args.root / "reports/s1b_long_20261103"
    analysis = json.loads((base / "analysis.json").read_text(encoding="utf-8"))
    detail = json.loads((base / "position_detail.json").read_text(encoding="utf-8"))
    plt.rcParams.update(
        {"font.family": "DejaVu Serif", "font.size": 9, "legend.fontsize": 9, "pdf.fonttype": 42}
    )
    for lang, text in TEXT.items():
        position(detail, text, base / "figures" / f"s1b_position_{lang}")
        failures(analysis, text, base / "figures" / f"s1b_failures_{lang}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
