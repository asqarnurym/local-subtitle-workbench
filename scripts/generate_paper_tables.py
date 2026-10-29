"""LaTeX Publication Table Generator for Speech Alignment Benchmark Suite.

Generates production-quality booktabs LaTeX tables for Paper 2 publication:
- Table 1: Alignment Accuracy across ablation modes (mean boundary error, Acc@20ms)
- Table 2: Statistical Significance (Paired Wilcoxon W, p-value, Cliff's delta)

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
    "B0_whisper": "(B0) Whisper timestamps",
    "B1_whisper_ctc": "(B1) Whisper + CTC",
    "B2_proposed": "(B2) Proposed: Whisper + MFA",
    "A1_ctc": "(A1) Known text + CTC",
    "A2_proposed": "(A2) Proposed: known text + MFA",
    "B2_const": "(B2) + constant offset",
    "B2_brqe": "(B2) + BRQE",
    "A2_const": "(A2) + constant offset",
    "A2_brqe": "(A2) + BRQE",
}

# Standard comparison pair display names
COMPARISON_DISPLAY_NAMES: dict[str, str] = {
    "B2_vs_B0": "B2 Proposed vs. B0 Whisper",
    "B2_vs_B1": "B2 Proposed vs. B1 Whisper + CTC",
    "A2_vs_A1": "A2 Proposed vs. A1 CTC",
    "B2brqe_vs_B2": "B2 + BRQE vs. B2",
    "B2brqe_vs_B2const": "B2 + BRQE vs. B2 + constant offset",
    "A2brqe_vs_A2": "A2 + BRQE vs. A2",
    "A2brqe_vs_A2const": "A2 + BRQE vs. A2 + constant offset",
}

PREFERRED_MODE_ORDER: list[str] = list(METHOD_DISPLAY_NAMES)

CORPUS_CAPTIONS: dict[str, str] = {
    "timit": "TIMIT (read speech, manual boundaries)",
    "buckeye": "Buckeye (spontaneous speech, manual boundaries)",
    "librispeech": "LibriSpeech test-clean (silver reference: MFA alignments)",
    "l2arctic": "L2-ARCTIC (accented speech; silver reference: forced alignments)",
    "synthetic": "Synthetic self-test",
}


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
    if mode_id in METHOD_DISPLAY_NAMES:
        return METHOD_DISPLAY_NAMES[mode_id]
    return escape_latex(mode_data.get("name", "") or mode_id)


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
    corpus_label = CORPUS_CAPTIONS.get(corpus, escape_latex(corpus.capitalize()))
    n_utt = data.get("n_utterances")
    n_spk = data.get("n_speakers")
    sample = f" ({n_utt} utterances, {n_spk} speakers)" if n_utt and n_spk else ""
    base_caption = f"Boundary Error on {corpus_label}{sample}"

    caption = f"{prefix}{base_caption}"

    lines: list[str] = [
        r"\begin{table}[t]",
        r"\centering",
        f"\\caption{{{caption}}}",
        r"\label{tab:alignment_accuracy}",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        (
            r"Method & Word MAE [95\% CI] (ms) & Word Acc@20ms (\%) & "
            r"Phone MAE (ms) & Phone Acc@20ms (\%) \\"
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

        if p_metrics and p_metrics.get("mae_ms") is not None:
            p_mae_str = f"{float(p_metrics['mae_ms']):.1f}"
        else:
            p_mae_str = "--"

        acc_20_str = _format_acc(w_metrics.get("acc_20ms"))
        p_acc_20_str = _format_acc(p_metrics.get("acc_20ms")) if p_metrics else "--"

        row = f"{method_name} & {w_mae_str} & {acc_20_str} & {p_mae_str} & {p_acc_20_str} \\\\"
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

    tests_dict = data.get("statistical_tests")
    if tests_dict is None:
        tests_dict = data.get("statistical_significance")
    if tests_dict is None:
        raise ValueError(
            "Benchmark results JSON missing 'statistical_tests' or "
            "'statistical_significance' dictionary"
        )
    if not tests_dict:
        return (
            "% Table 3 omitted: paired statistical significance testing requires "
            "at least two evaluated ablation modes.\n"
        )

    caption = f"{prefix}Paired Wilcoxon Signed-Rank Test and Cliff's Delta Effect Size"

    lines: list[str] = [
        r"\begin{table}[t]",
        r"\centering",
        f"\\caption{{{caption}}}",
        r"\label{tab:statistical_significance}",
        r"\begin{tabular}{lccccc}",
        r"\toprule",
        r"Comparison Pair & \(n\) & Wilcoxon \(W\) & \(p_{Holm}\) & Cliff's \(\delta\) & Effect \\",
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

        n_val = pair_data.get("n_pairs")
        n_str = str(int(n_val)) if n_val is not None else "--"
        row = f"{pair_name} & {n_str} & {w_str} & {p_str} & {delta_str} & {effect_str} \\\\"
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
    """Load benchmark JSON and generate all LaTeX tables.

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

    t3_content = generate_statistical_significance_table(
        data, table_format=table_format, allow_simulated=allow_simulated
    )
    t3_path = out_dir / "table_statistical_significance.tex"
    t3_path.write_text(t3_content, encoding="utf-8")

    return {
        "alignment_accuracy": t1_path,
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
