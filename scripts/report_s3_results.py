"""Build a results artifact from complete S3 evidence, never a manuscript draft."""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from scripts import experiment_safety as safety  # noqa: E402
from scripts import s2_s3_substudies as sub  # noqa: E402


def build(out: Path) -> dict:
    ids = safety.effective_sample_ids(ROOT, ROOT / sub.BUCKEYE_SAMPLE)
    analysis = safety.read(out / "analysis.json")
    detail = {}
    lines = [
        "# Результаты S3: размер Whisper",
        "",
        "Рабочий отчёт по существующему протоколу S2/S3. Это не рукопись статьи.",
        "",
        "999 клипов Buckeye, 20 тестовых дикторов; веса BRQE заморожены. "
        "large-v3 — сохранённый основной benchmark, без повторного запуска.",
        "",
        "MAE: среднее средних по дикторам. Acc@20: среднее по оцениваемым клипам. "
        "Покрытие — matched/reference из доступных строк, рядом обязательно число отказов.",
        "",
        "| Модель | Режим | MAE, мс | Acc@20, % | Покрытие, % | Отказы / 999 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for model in [*sub.S3_SIZES, "large-v3"]:
        if model == "large-v3":
            summary = analysis["frozen_large_v3"]
        else:
            run = out / "runs" / f"buckeye_{model}"
            safety.validate_complete(run, {"study": "S3", "asr_model": model}, ids, sub.S3_MODES)
            rows = safety.read(run / "benchmark_utterances.json")
            summary = analysis["runs"][f"buckeye_{model}"]
            record = safety.read(run / "run_record.json")
            detail[model] = {
                "mfa_retries": record["mfa_retries"],
                "seconds": record["seconds"],
                "failures": {
                    mode: dict(
                        collections.Counter(
                            row.get("error", "unspecified")
                            for row in rows
                            if row["mode"] == mode and row["status"] == "failed"
                        )
                    )
                    for mode in sub.S3_MODES
                },
            }
        for mode in sub.S3_MODES:
            row = summary[mode]

            def fmt(value, factor=1):
                return "NA" if value is None else f"{value * factor:.2f}"

            lines.append(
                f"| {model} | {mode} | {fmt(row['mean_speaker_mae_ms'])} | "
                f"{fmt(row['mean_acc20'])} | {fmt(row['word_coverage'], 100)} | {row['n_failed']} |"
            )
    lines += [
        "",
        "## Предрегистрированные сравнения с large-v3",
        "",
        "Положительная разница означает ухудшение. Интервал относится к среднему "
        "парных разностей, p — к знаковым рангам; их выводы могут различаться.",
        "",
        "| Режим | Модель | Пар дикторов | Разность MAE, мс | 95% CI | p Holm |",
        "|---|---|---:|---:|---|---:|",
    ]
    for mode, tests in analysis["tests_vs_large_v3"].items():
        for model, test in tests.items():
            difference = test.get("mean_difference_ms")
            interval = test.get("mean_difference_ci_95_ms")
            pvalue = test.get("p_value_holm")
            delta_text = "NA" if difference is None else f"{difference:+.2f}"
            ci_text = "NA" if interval is None else f"{interval[0]:+.2f}…{interval[1]:+.2f}"
            p_text = "NA" if pvalue is None else f"{pvalue:.4f}"
            lines.append(
                f"| {mode} | {model} | {test['n_pairs']} | {delta_text} | {ci_text} | {p_text} |"
            )
    lines += [
        "",
        "## Диагностика и ограничения",
        "",
        "Полный учёт текстов отказов и повторов MFA — в `failure_audit.json`. "
        "Отказы не исключаются из отчёта ради улучшения чисел. Покрытие и ошибка "
        "по успешным сопоставлениям не заменяют частоту отказов.",
        "",
        "Проверять вывод о чувствительности MAE вместе с покрытием: ошибка "
        "измеряется на распознанных и сопоставленных словах, состав которых "
        "зависит от модели. RTF включает параллельную MFA и не служит "
        "контролируемым сравнением скорости моделей.",
        "",
        "Утверждения CLAIM_LEDGER этим отчётом не утверждаются. Литературный "
        "аудит и ограничения журнала — `docs/LITERATURE_AUDIT_20261106.md`.",
    ]
    safety.atomic_json(out / "failure_audit.json", detail)
    (out / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return analysis


def figures(out: Path, analysis: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = [*sub.S3_SIZES, "large-v3"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    for mode, label, style in [("B2_proposed", "MFA", "o-"), ("B2_brqe", "MFA + BRQE", "s--")]:
        rows = [
            analysis["frozen_large_v3"][mode]
            if model == "large-v3"
            else analysis["runs"][f"buckeye_{model}"][mode]
            for model in models
        ]
        axes[0].plot(models, [r["mean_speaker_mae_ms"] for r in rows], style, label=label)
        axes[1].plot(models, [100 * r["word_coverage"] for r in rows], style, label=label)
    for ax in axes:
        ax.tick_params(axis="x", rotation=35)
        ax.grid(alpha=0.25)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncols=2, frameon=False)
    axes[0].set_ylabel("Mean speaker word MAE, ms")
    axes[1].set_ylabel("Matched word coverage, %")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    target = out / "figures"
    target.mkdir(exist_ok=True)
    fig.savefig(target / "s3_asr_size.png", dpi=300)
    fig.savefig(target / "s3_asr_size.pdf")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--figures", action="store_true")
    args = parser.parse_args()
    analysis = build(args.output_dir)
    if args.figures:
        figures(args.output_dir, analysis)
    print(json.dumps({"results": str(args.output_dir / "results.md"), "models": len(sub.S3_SIZES)}))


if __name__ == "__main__":
    main()
