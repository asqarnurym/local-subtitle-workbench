"""Publication figures (EN/RU, 300-dpi PNG and vector PDF) from completed E1 data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.replay_frozen_metrics import write_json  # noqa: E402
from scripts.verify_frozen_evidence import digest, local_path, read_json, require  # noqa: E402
from subtitle_workbench.provenance import code_provenance  # noqa: E402

COLORS = {
    "B0_whisper": "#555555",
    "A1_ctc": "#0072B2",
    "B1_whisper_ctc": "#0072B2",
    "A2_proposed": "#D55E00",
    "B2_proposed": "#D55E00",
    "A2_brqe": "#009E73",
    "B2_brqe": "#009E73",
}
NAMES = {
    "B0_whisper": "Whisper",
    "A1_ctc": "CTC",
    "B1_whisper_ctc": "Whisper + CTC",
    "A2_proposed": "MFA",
    "B2_proposed": "Whisper + MFA",
    "A2_brqe": "MFA + BRQE",
    "B2_brqe": "Whisper + MFA + BRQE",
}
TEXT = {
    "en": {
        "error": "Word boundary error (ms)",
        "cdf": "Cumulative fraction",
        "known": "A: known transcript",
        "asr": "B: ASR transcript",
        "gain": "MAE reduction (ms)\nrelative to constant offset",
        "speaker": "Speaker",
        "mae": "MAE (ms)",
        "reject": "Rejected words (%)",
        "start": "Start",
        "end": "End",
        "duration": "Reference word duration (ms)",
        "vowel": "Vowel",
        "stop": "Stop",
        "affricate": "Affricate",
        "fricative": "Fricative",
        "nasal": "Nasal",
        "approximant": "Approximant",
        "other": "Other",
    },
    "ru": {
        "error": "Ошибка границы слова, мс",
        "cdf": "Накопленная доля",
        "known": "A: известный текст",
        "asr": "B: текст ASR",
        "gain": "Снижение MAE, мс\nотносительно константной поправки",
        "speaker": "Диктор",
        "mae": "MAE, мс",
        "reject": "Отбраковано слов, %",
        "start": "Начало",
        "end": "Конец",
        "duration": "Эталонная длительность слова, мс",
        "vowel": "Гласные",
        "stop": "Смычные",
        "affricate": "Аффрикаты",
        "fricative": "Щелевые",
        "nasal": "Носовые",
        "approximant": "Аппроксиманты",
        "other": "Прочие",
    },
}


def panels(corpora, text, height=5.8):
    fig, axes = plt.subplots(2, 2, figsize=(7.4, height), layout="constrained")
    for row, name in enumerate(corpora):
        for col, scenario in enumerate(("known", "asr")):
            ax = axes[row, col]
            ax.set_title(f"{name.upper() if name == 'timit' else 'Buckeye'} — {text[scenario]}")
            ax.grid(axis="y", alpha=0.2)
    return fig, axes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", required=True)
    parser.add_argument("--figure-dir", default="figures", help="Subdirectory for figure exports")
    args = parser.parse_args()
    work = local_path(args.analysis_dir)
    analysis = read_json((work / "analysis.json").relative_to(ROOT).as_posix())
    require(analysis["status"] == "COMPLETE", "Analysis is incomplete")
    figdir, tables = (work / args.figure_dir).resolve(), work / "tables"
    require(figdir.parent == work, "Figure directory must be directly under the analysis directory")
    figdir.mkdir(exist_ok=True)
    tables.mkdir(exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Serif",
            "font.size": 9,
            "axes.titlesize": 9,
            "axes.labelsize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "pdf.fonttype": 42,
            "mathtext.fontset": "dejavuserif",
        }
    )
    errors = {}
    for corpus, data in analysis["corpora"].items():
        per_mode = {}
        with local_path(data["ledger"]["path"]).open(encoding="utf-8") as stream:
            next(stream)
            for line in stream:
                row = json.loads(line)
                if row[3] == "word":
                    per_mode.setdefault(row[0], []).append(abs(row[-1]))
        errors[corpus] = {mode: np.sort(values) for mode, values in per_mode.items()}
    outputs = {}

    def save(fig, name, lang):
        for suffix in ("png", "pdf"):
            path = figdir / f"{name}_{lang}.{suffix}"
            metadata = (
                {"CreationDate": None, "ModDate": None}
                if suffix == "pdf"
                else {"Software": "local-subtitle-workbench E1"}
            )
            fig.savefig(path, dpi=300, metadata=metadata)
            outputs[path.relative_to(ROOT).as_posix()] = {
                "sha256": digest(path),
                "language": lang,
                "figure": name,
            }
        plt.close(fig)

    for lang, text in TEXT.items():
        fig, axes = panels(analysis["corpora"], text)
        for row, corpus in enumerate(analysis["corpora"]):
            for col, modes in enumerate(
                (
                    ("A1_ctc", "A2_proposed", "A2_brqe"),
                    ("B0_whisper", "B1_whisper_ctc", "B2_proposed", "B2_brqe"),
                )
            ):
                ax = axes[row, col]
                for mode in modes:
                    x = errors[corpus][mode]
                    ax.step(
                        x,
                        np.arange(1, len(x) + 1) / len(x),
                        where="post",
                        label=NAMES[mode],
                        color=COLORS[mode],
                        linewidth=1.1,
                    )
                ax.set_xscale("symlog", linthresh=1)
                ax.set_xlim(left=0)
                ax.axvline(20, color="black", linestyle=":", linewidth=0.8)
                ax.set_xlabel(text["error"])
                ax.set_ylabel(text["cdf"])
                ax.set_ylim(0, 1.02)
        handles, _ = axes[0, 1].get_legend_handles_labels()
        fig.legend(
            handles,
            ["Whisper", "CTC", "MFA", "MFA + BRQE"],
            loc="outside upper center",
            ncol=4,
            frameon=False,
        )
        save(fig, "word_error_ecdf", lang)

        fig, axes = panels(analysis["corpora"], text, height=8.4)
        for row, (_corpus, data) in enumerate(analysis["corpora"].items()):
            for col, key in enumerate(("A2brqe_vs_A2const", "B2brqe_vs_B2const")):
                ax, comparison = axes[row, col], data["speaker_comparisons"][key]
                pairs = comparison["speaker_pairs"]
                gain = [v["difference_ms"] for v in pairs]
                ax.scatter(
                    gain,
                    np.arange(len(pairs)),
                    c=["#009E73" if v >= 0 else "#D55E00" for v in gain],
                    s=16,
                )
                ax.set_yticks(np.arange(len(pairs)), [v["speaker"] for v in pairs])
                ax.axvline(0, color="black", linewidth=0.8)
                ax.set_xlabel(text["gain"])
                ax.set_ylabel(text["speaker"])
                ax.set_title(ax.get_title() + f"\nHolm p = {comparison['p_value_holm']:.3g}")
        save(fig, "speaker_brqe_gain", lang)

        fig, axes = plt.subplots(1, 2, figsize=(7.4, 4.1), layout="constrained")
        for ax, (corpus, data) in zip(axes, analysis["corpora"].items(), strict=True):
            modes = ("A2_proposed", "A2_brqe", "B2_proposed", "B2_brqe")
            x = np.arange(len(modes))
            for delta, kind, color in ((-0.19, "start", "#0072B2"), (0.19, "end", "#D55E00")):
                values = [
                    data["modes"][mode]["breakdowns"][f"word/{kind}"]["mae_ms"] for mode in modes
                ]
                ax.bar(x + delta, values, width=0.36, label=text[kind], color=color)
            ax.set_xticks(x, ["A2", "A2+BRQE", "B2", "B2+BRQE"], rotation=25, ha="right")
            ax.set_ylabel(text["mae"])
            ax.set_title(corpus.upper() if corpus == "timit" else "Buckeye")
            ax.grid(axis="y", alpha=0.2)
        handles, labels = axes[-1].get_legend_handles_labels()
        fig.legend(handles, labels, loc="outside upper center", ncol=2, frameon=False)
        save(fig, "word_start_end", lang)

        fig, axes = plt.subplots(1, 2, figsize=(7.4, 4.1), layout="constrained")
        for ax, (corpus, data) in zip(axes, analysis["corpora"].items(), strict=True):
            for mode, style in (("A2_brqe", "-o"), ("B2_brqe", "--s")):
                qe = data["modes"][mode]["quality_estimation"]
                levels = [0, 10, 20, 30, 50]
                ax.plot(
                    levels,
                    [qe["word_mae_after_rejection_ms"][f"reject_{lv}pct"] for lv in levels],
                    style,
                    label=mode.replace("_brqe", "+BRQE"),
                    markersize=4,
                )
            ax.set_xlabel(text["reject"])
            ax.set_ylabel(text["mae"])
            ax.set_xticks([0, 10, 20, 30, 50])
            ax.set_title(corpus.upper() if corpus == "timit" else "Buckeye")
            ax.legend(frameon=False)
            ax.grid(alpha=0.2)
        save(fig, "reliability_retention", lang)

        for figure in ("phone_group_mae", "word_duration_mae"):
            fig, axes = panels(analysis["corpora"], text, height=6.6)
            categories = (
                ("vowel", "stop", "affricate", "fricative", "nasal", "approximant", "other")
                if figure == "phone_group_mae"
                else ("<100", "100-200", "200-400", ">=400")
            )
            prefix = "phone/group/" if figure == "phone_group_mae" else "word/duration_ms/"
            for row, (_corpus, data) in enumerate(analysis["corpora"].items()):
                for col, modes in enumerate(
                    (("A2_proposed", "A2_brqe"), ("B2_proposed", "B2_brqe"))
                ):
                    ax = axes[row, col]
                    for index, mode in enumerate(modes):
                        values = [
                            data["modes"][mode]["breakdowns"]
                            .get(prefix + cat, {})
                            .get("mae_ms", np.nan)
                            for cat in categories
                        ]
                        values = [np.nan if v is None else v for v in values]
                        if figure == "phone_group_mae":
                            ax.bar(
                                np.arange(len(categories)) + (-0.19 if index == 0 else 0.19),
                                values,
                                width=0.36,
                                color=COLORS[mode],
                                label=NAMES[mode],
                            )
                        else:
                            ax.plot(
                                np.arange(len(categories)),
                                values,
                                "-o",
                                color=COLORS[mode],
                                label=NAMES[mode],
                                markersize=4,
                            )
                    ax.set_xticks(
                        np.arange(len(categories)),
                        [text[c] for c in categories]
                        if figure == "phone_group_mae"
                        else categories,
                        rotation=35 if figure == "phone_group_mae" else 0,
                        ha="right" if figure == "phone_group_mae" else "center",
                    )
                    ax.set_ylabel(text["mae"])
                    ax.set_ylim(bottom=0)
                    if figure == "word_duration_mae":
                        ax.set_xlabel(text["duration"])
            handles, _ = axes[-1, -1].get_legend_handles_labels()
            fig.legend(
                handles, ["MFA", "MFA + BRQE"], loc="outside upper center", ncol=2, frameon=False
            )
            save(fig, figure, lang)

    for corpus, data in analysis["corpora"].items():
        lines = [
            r"\begin{tabular}{lrrr}",
            r"\toprule",
            r"Comparison & Speakers & Improved & Exact Holm $p$ \\",
            r"\midrule",
        ]
        for key, item in data["speaker_comparisons"].items():
            label = key.replace("_vs_", " vs ").replace("const", " const").replace("brqe", "+BRQE")
            lines.append(
                f"{label} & {item['n_pairs']} & {item['n_speakers_improved']} & {item['p_value_holm']:.6g} "
                + r"\\"
            )
        lines.extend([r"\bottomrule", r"\end{tabular}"])
        (tables / f"speaker_tests_{corpus}.tex").write_bytes(("\n".join(lines) + "\n").encode())
    write_json(
        work / "figure_manifest.json",
        {
            "analysis_sha256": digest(work / "analysis.json"),
            "renderer_sha256": digest(Path(__file__).resolve()),
            "code": code_provenance(),
            "numpy": np.__version__,
            "matplotlib": matplotlib.__version__,
            "png_dpi": 300,
            "font": "DejaVu Serif, 9 pt",
            "files": outputs,
            "tables": {
                p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(tables.glob("*.tex"))
            },
        },
    )
    print(f"[+] Rendered {len(outputs)} figure files and two speaker tables", flush=True)


if __name__ == "__main__":
    main()
