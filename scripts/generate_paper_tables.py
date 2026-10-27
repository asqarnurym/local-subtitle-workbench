"""LaTeX Publication Table Generator for Speech Alignment Benchmark Suite.

Generates production-quality booktabs LaTeX tables for Paper 2 publication:
- Table 1: Alignment Accuracy across ablation modes (TIMIT / Buckeye)
- Table 2: Computational Performance (RTF, peak VRAM, peak host RAM)
- Table 3: Statistical Significance (Paired Wilcoxon W, p-value, Cliff's delta)

Adheres strictly to the Zero-Emoji Discipline and pure ASCII formatting.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

# Standard method display names for publication tables
METHOD_DISPLAY_NAMES: dict[str, str] = {
    "mode1_whisper": "Whisper Large-v3",
    "mode2_ctc": "CTC Trellis (MMS\\_FA)",
    "mode3_hybrid": "Proposed Hybrid",
}

# Standard comparison pair display names
COMPARISON_DISPLAY_NAMES: dict[str, str] = {
    "proposed_vs_whisper": "Proposed Hybrid vs. Whisper Large-v3",
    "mode3_vs_mode1": "Proposed Hybrid vs. Whisper Large-v3",
    "proposed_vs_ctc": "Proposed Hybrid vs. CTC Trellis",
    "mode3_vs_mode2": "Proposed Hybrid vs. CTC Trellis",
}

PREFERRED_MODE_ORDER: list[str] = [
    "mode1_whisper",
    "mode2_ctc",
    "mode3_hybrid",
]


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters in text strings.

    Specifically handles underscores (_) and percent signs (%) if not already escaped.
    Does not double-escape characters already preceded by a backslash.
    """
    if not text:
        return ""
    # Escape unescaped %
    out = re.sub(r"(?<!\\)%", r"\%", str(text))
    # Escape unescaped _
    out = re.sub(r"(?<!\\)_", r"\_", out)
    return out


def _format_method_name(mode_id: str, mode_data: dict[str, Any]) -> str:
    """Format publication method name with LaTeX escaping."""
    if "description" in mode_data and mode_data["description"]:
        return escape_latex(str(mode_data["description"]))

    name = mode_data.get("name", "")
    if mode_id in METHOD_DISPLAY_NAMES:
        if not name or "Internal Timestamps" in name or "MMS_FA" in name or "MFA" in name:
            return METHOD_DISPLAY_NAMES[mode_id]
        return escape_latex(name)

    return escape_latex(name or mode_id)


def _format_ci(mae: float, ci: list[float] | tuple[float, float] | None) -> str:
    """Format MAE with optional [95% CI] interval."""
    if ci is not None and len(ci) == 2 and not (math.isnan(ci[0]) or math.isnan(ci[1])):
        return f"{mae:.1f} [{ci[0]:.1f}, {ci[1]:.1f}]"
    return f"{mae:.1f}"


def _format_acc(val: float | None) -> str:
    """Format accuracy percentage with escaped percent symbol."""
    if val is None or math.isnan(val):
        return "--"
    return f"{val:.1f}\\%"


def _format_rtf(rtf: float | None) -> str:
    """Format Real-Time Factor to 3 decimal places with LaTeX multiplication symbol."""
    if rtf is None or math.isnan(rtf):
        return "--"
    return f"{rtf:.3f}\\(\\times\\)"


def _format_vram(vram_mb: float | None) -> str:
    """Format peak VRAM in MB or '--' if 0.0 or None."""
    if vram_mb is None or math.isnan(vram_mb) or vram_mb <= 0.0:
        return "--"
    return f"{vram_mb:.1f}"


def _format_ram(ram_mb: float | None) -> str:
    """Format peak host RAM in MB."""
    if ram_mb is None or math.isnan(ram_mb):
        return "--"
    return f"{ram_mb:.1f}"


def _format_p_value(p_val: float | None) -> str:
    """Format p-value in scientific notation ($a \\times 10^{b}$) or decimal."""
    if p_val is None or math.isnan(p_val):
        return "--"
    if p_val == 0.0:
        return "$< 0.001$"
    if p_val < 0.001:
        exp = int(math.floor(math.log10(abs(p_val))))
        mantissa = p_val / (10**exp)
        return f"${mantissa:.2f} \\times 10^{{{exp}}}$"
    return f"{p_val:.3f}"


def _format_cliffs_delta(delta: float | None) -> str:
    """Format Cliff's delta with explicit sign and 2 decimal places."""
    if delta is None or math.isnan(delta):
        return "--"
    return f"{delta:+.2f}"


def _check_provenance_and_get_prefix(
    data: dict[str, Any],
    allow_simulated: bool = False,
) -> str:
    """Validate data provenance and return caption prefix if simulated data is allowed.

    Refuses (raises ValueError) if data is simulated/offline and allow_simulated is False.
    """
    provenance = data.get("data_provenance")
    is_offline = bool(
        data.get("offline_synthetic", False) or (provenance == "SIMULATED_PREDICTIONS")
    )

    if provenance != "MODEL_EXECUTION" or is_offline:
        if not allow_simulated:
            raise ValueError(
                f"Refusing to generate publication tables from unverified/simulated benchmark data "
                f"(data_provenance={provenance!r}, offline_synthetic={is_offline}). "
                f"Publication tables require real MODEL_EXECUTION data. "
                f"Pass --allow-simulated to override for pipeline self-tests."
            )
        return "SIMULATED SELF-TEST -- NOT RESULTS: "
    return ""


def generate_alignment_accuracy_table(
    data: dict[str, Any],
    table_format: str = "booktabs",
    allow_simulated: bool = False,
) -> str:
    """Generate Table 1: Alignment Accuracy Across Ablation Modes."""
    if table_format != "booktabs":
        raise ValueError(f"Unsupported table format: '{table_format}'. Must be 'booktabs'.")

    prefix = _check_provenance_and_get_prefix(data, allow_simulated=allow_simulated)

    if "modes" not in data or not data["modes"]:
        raise ValueError("Benchmark results JSON missing 'modes' dictionary")

    modes_dict = data["modes"]

    ordered_keys = [k for k in PREFERRED_MODE_ORDER if k in modes_dict]
    remaining_keys = [k for k in modes_dict if k not in ordered_keys]
    all_keys = ordered_keys + remaining_keys

    corpus = str(data.get("corpus", "synthetic")).lower()
    if corpus == "timit":
        base_caption = "TIMIT Core Test Alignment Accuracy Across Ablation Modes"
    elif corpus == "buckeye":
        base_caption = "Buckeye Speech Corpus Alignment Accuracy Across Ablation Modes"
    elif corpus == "synthetic":
        base_caption = "Synthetic Benchmark Alignment Accuracy Across Ablation Modes"
    else:
        base_caption = f"{corpus.capitalize()} Alignment Accuracy Across Ablation Modes"

    caption = f"{prefix}{base_caption}"

    lines: list[str] = [
        r"\begin{table}[t]",
        r"\centering",
        f"\\caption{{{caption}}}",
        r"\label{tab:alignment_accuracy}",
        r"\begin{tabular}{lcccccc}",
        r"\toprule",
        (
            r"Method & Word MAE [95\% CI] (ms) & Word MedAE (ms) & Phone MAE (ms) & "
            r"Acc@20ms (\%) & Acc@50ms (\%) & Acc@100ms (\%) \\"
        ),
        r"\midrule",
    ]

    for key in all_keys:
        m_info = modes_dict[key]
        method_name = _format_method_name(key, m_info)

        w_metrics = m_info.get("word_metrics") or {}
        p_metrics = m_info.get("phone_metrics")

        w_mae = w_metrics.get("mae_ms")
        w_ci = w_metrics.get("ci_95")
        if w_mae is not None:
            w_mae_str = _format_ci(float(w_mae), w_ci)
        else:
            w_mae_str = "--"

        w_medae = w_metrics.get("medae_ms")
        w_medae_str = f"{float(w_medae):.1f}" if w_medae is not None else "--"

        if p_metrics and p_metrics.get("mae_ms") is not None:
            p_mae_str = f"{float(p_metrics['mae_ms']):.1f}"
        else:
            p_mae_str = "--"

        acc_20_str = _format_acc(w_metrics.get("acc_20ms"))
        acc_50_str = _format_acc(w_metrics.get("acc_50ms"))
        acc_100_str = _format_acc(w_metrics.get("acc_100ms"))

        row = (
            f"{method_name} & {w_mae_str} & {w_medae_str} & {p_mae_str} & "
            f"{acc_20_str} & {acc_50_str} & {acc_100_str} \\\\"
        )
        lines.append(row)

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_computational_performance_table(
    data: dict[str, Any],
    table_format: str = "booktabs",
    allow_simulated: bool = False,
) -> str:
    """Generate Table 2: Computational Efficiency Across Ablation Modes."""
    if table_format != "booktabs":
        raise ValueError(f"Unsupported table format: '{table_format}'. Must be 'booktabs'.")

    prefix = _check_provenance_and_get_prefix(data, allow_simulated=allow_simulated)

    if "modes" not in data or not data["modes"]:
        raise ValueError("Benchmark results JSON missing 'modes' dictionary")

    modes_dict = data["modes"]

    ordered_keys = [k for k in PREFERRED_MODE_ORDER if k in modes_dict]
    remaining_keys = [k for k in modes_dict if k not in ordered_keys]
    all_keys = ordered_keys + remaining_keys

    caption = f"{prefix}Computational Efficiency Across Ablation Modes"

    lines: list[str] = [
        r"\begin{table}[t]",
        r"\centering",
        f"\\caption{{{caption}}}",
        r"\label{tab:computational_performance}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"Method & Real-Time Factor (RTF) & Peak VRAM (MB) & Peak Host RAM (MB) \\",
        r"\midrule",
    ]

    for key in all_keys:
        m_info = modes_dict[key]
        method_name = _format_method_name(key, m_info)

        perf = m_info.get("computational_metrics") or m_info.get("performance") or {}

        rtf_val = perf.get("rtf")
        rtf_str = _format_rtf(float(rtf_val) if rtf_val is not None else None)

        vram_val = perf.get("peak_vram_mb")
        vram_str = _format_vram(float(vram_val) if vram_val is not None else None)

        ram_val = perf.get("peak_ram_mb")
        if ram_val is None:
            ram_val = perf.get("peak_host_ram_mb")
        ram_str = _format_ram(float(ram_val) if ram_val is not None else None)

        row = f"{method_name} & {rtf_str} & {vram_str} & {ram_str} \\\\"
        lines.append(row)

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_statistical_significance_table(
    data: dict[str, Any],
    table_format: str = "booktabs",
    allow_simulated: bool = False,
) -> str:
    """Generate Table 3: Paired Wilcoxon Signed-Rank Test and Cliff's Delta Effect Size."""
    if table_format != "booktabs":
        raise ValueError(f"Unsupported table format: '{table_format}'. Must be 'booktabs'.")

    prefix = _check_provenance_and_get_prefix(data, allow_simulated=allow_simulated)

    tests_dict = data.get("statistical_tests") or data.get("statistical_significance")
    if not tests_dict:
        raise ValueError(
            "Benchmark results JSON missing 'statistical_tests' or "
            "'statistical_significance' dictionary"
        )

    caption = f"{prefix}Paired Wilcoxon Signed-Rank Test and Cliff's Delta Effect Size"

    lines: list[str] = [
        r"\begin{table}[t]",
        r"\centering",
        f"\\caption{{{caption}}}",
        r"\label{tab:statistical_significance}",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"Comparison Pair & Wilcoxon \(W\) & \(p\)-value & Cliff's \(\delta\) & Effect Size \\",
        r"\midrule",
    ]

    for key, pair_data in tests_dict.items():
        if key in COMPARISON_DISPLAY_NAMES:
            pair_name = COMPARISON_DISPLAY_NAMES[key]
        elif "comparison" in pair_data:
            pair_name = escape_latex(str(pair_data["comparison"]))
        elif "pair" in pair_data:
            pair_name = escape_latex(str(pair_data["pair"]))
        else:
            clean = key.replace("_vs_", " vs. ").replace("_", " ").title()
            pair_name = escape_latex(clean)

        w_val = pair_data.get("w_statistic")
        if w_val is None:
            w_val = pair_data.get("wilcoxon_w")
        w_str = f"{float(w_val):.1f}" if w_val is not None else "--"

        p_val = pair_data.get("p_value")
        p_str = _format_p_value(float(p_val) if p_val is not None else None)

        delta_val = pair_data.get("cliffs_delta")
        delta_str = _format_cliffs_delta(float(delta_val) if delta_val is not None else None)

        effect_val = pair_data.get("effect_size", "")
        effect_str = str(effect_val).capitalize() if effect_val else "--"

        row = f"{pair_name} & {w_str} & {p_str} & {delta_str} & {effect_str} \\\\"
        lines.append(row)

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_all_tables(
    input_path: Path | str,
    output_dir: Path | str,
    table_format: str = "booktabs",
    allow_simulated: bool = False,
) -> dict[str, Path]:
    """Load benchmark JSON and generate all three LaTeX tables.

    Returns dictionary mapping table keys to created Path instances.
    """
    in_file = Path(input_path)
    if not in_file.is_file():
        raise FileNotFoundError(f"Benchmark results file not found: {in_file}")

    content = in_file.read_text(encoding="utf-8")
    data = json.loads(content)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t1_content = generate_alignment_accuracy_table(
        data, table_format=table_format, allow_simulated=allow_simulated
    )
    t1_path = out_dir / "table_alignment_accuracy.tex"
    t1_path.write_text(t1_content, encoding="utf-8")

    t2_content = generate_computational_performance_table(
        data, table_format=table_format, allow_simulated=allow_simulated
    )
    t2_path = out_dir / "table_computational_performance.tex"
    t2_path.write_text(t2_content, encoding="utf-8")

    t3_content = generate_statistical_significance_table(
        data, table_format=table_format, allow_simulated=allow_simulated
    )
    t3_path = out_dir / "table_statistical_significance.tex"
    t3_path.write_text(t3_content, encoding="utf-8")

    return {
        "alignment_accuracy": t1_path,
        "computational_performance": t2_path,
        "statistical_significance": t3_path,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publication LaTeX Table Generator for Speech Alignment Benchmark."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("reports/benchmark/benchmark_results.json"),
        help=(
            "Path to benchmark JSON results file "
            "(default: reports/benchmark/benchmark_results.json)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/paper"),
        help="Directory where LaTeX tables will be written (default: docs/paper)",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="booktabs",
        choices=["booktabs"],
        help="Table formatting style (default: booktabs)",
    )
    parser.add_argument(
        "--allow-simulated",
        action="store_true",
        default=False,
        help="Allow generating tables from simulated self-test benchmark data with warning prefix in captions",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
    except SystemExit as err:
        return err.code

    try:
        tables = generate_all_tables(
            input_path=args.input,
            output_dir=args.output_dir,
            table_format=args.format,
            allow_simulated=args.allow_simulated,
        )
        for name, path in tables.items():
            print(f"[+] Generated {name} table: {path}")
        print("[OK] All publication LaTeX tables generated successfully.")
        return 0
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as err:
        sys.stderr.write(f"[-] Error: {err}\n")
        return 1
    except Exception as err:
        sys.stderr.write(f"[-] Unexpected Error: {err}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
