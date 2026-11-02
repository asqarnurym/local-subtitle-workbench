"""BRQE sensitivity figure (EN/RU, 300-dpi PNG and vector PDF) from a verified summary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
ORDER = [
    "baseline",
    "epochs_6",
    "epochs_24",
    "window_50ms",
    "window_150ms",
    "hidden_64",
    "hidden_256",
    "cls_0.25",
    "cls_1.0",
]
SCENARIOS = {"A": ("#D55E00", "o"), "B": ("#0072B2", "s")}
TEXT = {
    "en": {
        "labels": {
            "baseline": "Baseline (12 ep., ±100 ms, 128, 0.5)",
            "epochs_6": "Epochs: 6",
            "epochs_24": "Epochs: 24",
            "window_50ms": "Window: ±50 ms",
            "window_150ms": "Window: ±150 ms",
            "hidden_64": "Hidden units: 64",
            "hidden_256": "Hidden units: 256",
            "cls_0.25": "Reliability loss weight: 0.25",
            "cls_1.0": "Reliability loss weight: 1.0",
        },
        "gain": "Word MAE reduction\nvs constant offset (ms)",
        "auc": "Reliability head\nROC-AUC (words)",
        "A": "A: known transcript",
        "B": "B: ASR transcript",
    },
    "ru": {
        "labels": {
            "baseline": "Базовая (12 эп., ±100 мс, 128, 0,5)",
            "epochs_6": "Эпохи: 6",
            "epochs_24": "Эпохи: 24",
            "window_50ms": "Окно: ±50 мс",
            "window_150ms": "Окно: ±150 мс",
            "hidden_64": "Скрытый слой: 64",
            "hidden_256": "Скрытый слой: 256",
            "cls_0.25": "Вес потерь надёжности: 0,25",
            "cls_1.0": "Вес потерь надёжности: 1,0",
        },
        "gain": "Снижение MAE слов\nотносительно константы, мс",
        "auc": "ROC-AUC головы\nнадёжности (слова)",
        "A": "A: известный текст",
        "B": "B: текст ASR",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(rows: dict, lang: str, out: Path) -> list[Path]:
    text = TEXT[lang]
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(7.4, 3.4), layout="constrained", sharey=True, width_ratios=(1.6, 1)
    )
    ys = list(range(len(ORDER)))[::-1]
    for scenario, (color, marker) in SCENARIOS.items():
        gains = [rows[n][f"gain_word_{scenario}_mae_ms_vs_const"] for n in ORDER]
        left.scatter(gains, ys, color=color, marker=marker, s=22, label=text[scenario], zorder=3)
        left.axvline(
            rows["baseline"][f"gain_word_{scenario}_mae_ms_vs_const"], color=color, lw=0.8, ls=":"
        )
    right.scatter([rows[n]["qe_roc_auc_word"] for n in ORDER], ys, color="#333333", s=18, zorder=3)
    right.axvline(rows["baseline"]["qe_roc_auc_word"], color="#333333", lw=0.8, ls=":")
    left.axvline(0, color="#999999", lw=0.8)
    left.set_xlim(left=0)
    left.set_yticks(ys, [text["labels"][n] for n in ORDER])
    left.set_xlabel(text["gain"])
    right.set_xlabel(text["auc"])
    left.legend(loc="lower left", frameon=False)
    for ax in (left, right):
        ax.grid(axis="x", alpha=0.2)
    paths = []
    for ext in ("png", "pdf"):
        path = out / f"brqe_sensitivity_{lang}.{ext}"
        fig.savefig(path, dpi=300, metadata={"CreationDate": None} if ext == "pdf" else None)
        paths.append(path)
    plt.close(fig)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", required=True)
    args = parser.parse_args()
    work = (ROOT / args.analysis_dir).resolve()
    verify = json.loads((work / "verify.json").read_text(encoding="utf-8"))
    if not verify["verified"]:
        raise SystemExit("summary is not verified; run brqe_sensitivity.py --verify first")
    summary_path = work / "summary.json"
    rows = json.loads(summary_path.read_text(encoding="utf-8"))["rows"]
    if sorted(rows) != sorted(ORDER):
        raise SystemExit(f"unexpected configurations: {sorted(rows)}")
    plt.rcParams.update(
        {
            "font.family": "DejaVu Serif",
            "font.size": 9,
            "axes.labelsize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "pdf.fonttype": 42,
        }
    )
    figdir = work / "figures"
    figdir.mkdir(exist_ok=True)
    files = [p for lang in TEXT for p in render(rows, lang, figdir)]
    manifest = {
        "source": {summary_path.relative_to(ROOT).as_posix(): sha256(summary_path)},
        "script": {"scripts/render_brqe_sensitivity.py": sha256(Path(__file__))},
        "matplotlib": matplotlib.__version__,
        "files": {p.relative_to(ROOT).as_posix(): sha256(p) for p in files},
    }
    (work / "figure_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[+] {len(files)} files in {figdir.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
