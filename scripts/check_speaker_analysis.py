"""Independently validate E1 boundary data, aggregation, CIs and exact speaker tests.

Run with the pinned isolated SciPy/Pillow analysis environment in the protocol.
This script does not import the primary analysis implementation.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from functools import cache
from pathlib import Path

import numpy as np
import scipy
from PIL import Image
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts import speech_benchmark as benchmark  # noqa: E402
from scripts.replay_frozen_metrics import deserialize_predictions, write_json  # noqa: E402
from scripts.verify_frozen_evidence import digest, local_path, read_json, require  # noqa: E402
from subtitle_workbench.metrics import _align_token_sequences, clustered_bootstrap_ci  # noqa: E402
from subtitle_workbench.phone_sets import fold_phones  # noqa: E402
from subtitle_workbench.provenance import code_provenance  # noqa: E402


def close(left, right, name, atol=1e-9):
    require(bool(np.allclose(left, right, rtol=0, atol=atol)), f"Independent mismatch: {name}")


def check_corpus(name: str, saved: dict, work: Path) -> dict:
    frozen = read_json(f"reports/{name}/benchmark_results.json")
    manifest = read_json(f"reports/{name}/manifest.json")
    source = (
        benchmark.load_timit_utterances(local_path("data/corpora/timit"))
        if name == "timit"
        else benchmark.load_textgrid_utterances(local_path("data/corpora/buckeye"), "buckeye")
    )
    utterances = {
        u.id: u
        for u in benchmark.select_utterances(source, list(manifest["inputs"]["audio_files"]))
    }
    predictions = deserialize_predictions(read_json(f"reports/{name}/benchmark_predictions.json"))
    rows = read_json(f"reports/{name}/benchmark_utterances.json")
    success = {(r["mode"], r["utterance"]) for r in rows if r["status"] == "ok"}
    ledger_path = local_path(saved["ledger"]["path"])
    require(digest(ledger_path) == saved["ledger"]["sha256"], "Boundary ledger hash changed")
    values, clusters, by_clip = defaultdict(list), defaultdict(list), defaultdict(list)
    grouped = defaultdict(list)
    phone_classes = {
        phone: group
        for group, labels in {
            "vowel": "aa ae ah ao aw ay eh er ey ih iy ow oy uh uw",
            "stop": "b d g p t k",
            "affricate": "ch jh",
            "fricative": "f v th dh s z sh zh hh",
            "nasal": "m n ng",
            "approximant": "l r w y",
        }.items()
        for phone in labels.split()
    }
    actual_pairs = defaultdict(set)

    @cache
    def tokens(mode, uid, tier):
        p = predictions[mode][uid]
        return (
            (p[0], utterances[uid].ref_words)
            if tier == "word"
            else (fold_phones(p[1] or []), fold_phones(utterances[uid].ref_phones))
        )

    records = 0
    with ledger_path.open(encoding="utf-8") as stream:
        header = json.loads(next(stream))
        expected_fields = [
            "mode",
            "utterance",
            "speaker",
            "tier",
            "kind",
            "pred_index",
            "ref_index",
            "phone",
            "reference_duration_s",
            "reference_characters",
            "signed_error_ms",
        ]
        require(
            header == {"schema_version": 1, "fields": expected_fields}, "Ledger schema mismatch"
        )
        for line in stream:
            mode, uid, speaker, tier, kind, pi, ri, label, duration, length, error = json.loads(
                line
            )
            require(
                (mode, uid) in success and speaker == utterances[uid].speaker_id,
                "Invalid ledger clip/speaker",
            )
            pred, ref = tokens(mode, uid, tier)
            require(
                kind in ("start", "end") and tier in ("word", "phone"), "Invalid boundary tier/kind"
            )
            p, r = pred[pi], ref[ri]
            require(
                error == (getattr(p, kind) - getattr(r, kind)) * 1000,
                "Ledger error does not match saved timestamps",
            )
            require(duration == r.end - r.start, "Reference duration mismatch")
            require(
                (label == r.phoneme and length == 0)
                if tier == "phone"
                else (label == "" and length == sum(c.isalpha() for c in r.normalized)),
                "Reference label/length mismatch",
            )
            pair = (pi, ri, kind)
            key = (mode, uid, tier)
            require(pair not in actual_pairs[key], "Repeated matched boundary")
            actual_pairs[key].add(pair)
            values[(mode, tier)].append(abs(error))
            clusters[(mode, tier)].append(speaker)
            if tier == "word":
                by_clip[(mode, uid)].append(abs(error))
                length_label = (
                    "0"
                    if length == 0
                    else ("1-3", "4-6", "7+")[int(np.searchsorted([3, 6], length, side="left"))]
                )
                duration_label = ("<100", "100-200", "200-400", ">=400")[
                    int(np.searchsorted([0.1, 0.2, 0.4], duration, side="right"))
                ]
                grouped[(mode, f"word/length/{length_label}")].append(error)
                grouped[(mode, f"word/duration_ms/{duration_label}")].append(error)
            else:
                grouped[(mode, f"phone/label/{label}")].append(error)
                grouped[(mode, f"phone/group/{phone_classes.get(label, 'other')}")].append(error)
            grouped[(mode, f"{tier}/{kind}")].append(error)
            records += 1
    require(set(by_clip) == success, "Entire scored clips are missing from the ledger")
    for (mode, uid, tier), pairs in actual_pairs.items():
        pred, ref = tokens(mode, uid, tier)
        pindex, rindex = (
            {id(t): i for i, t in enumerate(pred)},
            {id(t): i for i, t in enumerate(ref)},
        )
        expected = {
            (pindex[id(p)], rindex[id(r)], kind)
            for p, r in _align_token_sequences(pred, ref)[0]
            for kind in ("start", "end")
        }
        require(pairs == expected, "Ledger does not contain exactly the frozen matched pairs")
    for (mode, tier), errors in values.items():
        current = saved["modes"][mode]["tiers"][tier]
        errors = np.asarray(errors)
        speaker = clusters[(mode, tier)]
        close(errors.mean(), current["mae_ms"], f"{mode}/{tier}/MAE")
        close(100 * np.mean(errors <= 20.0001), current["acc_20ms"], f"{mode}/{tier}/Acc")
        close(
            clustered_bootstrap_ci(errors, speaker, num_resamples=2000, seed=42),
            current["mae_ci_95_ms"],
            f"{mode}/{tier}/CI MAE",
        )
        close(
            clustered_bootstrap_ci(
                100.0 * (errors <= 20.0001), speaker, num_resamples=2000, seed=42
            ),
            current["acc_20ms_ci_95"],
            f"{mode}/{tier}/CI Acc",
        )
        require(
            len(errors) == frozen["modes"][mode][f"{tier}_metrics"]["n_boundaries"],
            "Incomplete boundary ledger",
        )
        reference_all = sum(
            len(u.ref_words) if tier == "word" else len(fold_phones(u.ref_phones))
            for u in utterances.values()
        )
        reference_scored = sum(
            len(tokens(mode, uid, tier)[1])
            for uid in utterances
            if (mode, uid, tier) in actual_pairs
        )
        require(
            current["num_reference_all_attempted"] == reference_all
            and current["num_reference_scored"] == reference_scored,
            "Coverage reference denominator differs",
        )
        require(current["num_matched"] == len(errors) // 2, "Matched token count differs")
        close(
            current["coverage_all_attempted"],
            (len(errors) // 2) / reference_all,
            "All-attempted coverage",
        )
        require(
            current["coverage_scored"] == round((len(errors) // 2) / reference_scored, 4),
            "Conditional coverage differs",
        )
    for mode, data in saved["modes"].items():
        require(
            {key for (m, key) in grouped if m == mode} <= data["breakdowns"].keys(),
            "Descriptive groups were dropped",
        )
        require(
            data["quality_estimation"] == frozen["modes"][mode].get("quality_estimation"),
            "Rejection curve differs from its frozen source",
        )
        require(
            data["failures"] == [r for r in rows if r["mode"] == mode and r["status"] != "ok"],
            "Failure list differs",
        )
        for key, summary in data["breakdowns"].items():
            signed = np.asarray(grouped[(mode, key)], dtype=float)
            require(len(signed) == summary["n_boundaries"], "Descriptive bin count differs")
            if len(signed):
                close(np.mean(np.abs(signed)), summary["mae_ms"], "Descriptive MAE")
                close(np.mean(signed), summary["mean_signed_error_ms"], "Signed bias")
                close(
                    100 * np.mean(np.abs(signed) <= 20.0001), summary["acc_20ms"], "Descriptive Acc"
                )
            else:
                require(
                    summary["mae_ms"] is None and summary["acc_20ms"] is None,
                    "Empty bins must not have numeric metrics",
                )
        worst = sorted(
            [(uid, float(np.mean(errors))) for (m, uid), errors in by_clip.items() if m == mode],
            key=lambda item: (-item[1], item[0]),
        )[:10]
        require(
            [uid for uid, _ in worst] == [r["utterance"] for r in data["worst_clips"]],
            "Worst-clip ranking differs",
        )
    raw_p, keys = [], []
    for key, comparison in saved["speaker_comparisons"].items():
        baseline, proposed = comparison["baseline"], comparison["proposed"]
        a = {uid for mode, uid in success if mode == baseline}
        b = {uid for mode, uid in success if mode == proposed}
        common = sorted(a & b)
        require(common == comparison["common_clip_ids"], "Paired clip intersection differs")
        expected_speakers = sorted({utterances[u].speaker_id for u in common})
        require(
            [v["speaker"] for v in comparison["speaker_pairs"]] == expected_speakers,
            "Paired speakers incomplete",
        )
        delta = []
        for pair in comparison["speaker_pairs"]:
            selected = [u for u in common if utterances[u].speaker_id == pair["speaker"]]
            means = []
            require(len(selected) == pair["n_common_clips"], "Paired clip count differs")
            for role, mode in (("baseline", baseline), ("proposed", proposed)):
                errors = [v for uid in selected for v in by_clip[(mode, uid)]]
                require(len(errors) == pair[role]["n_boundaries"], "Speaker denominator differs")
                mean = math.fsum(errors) / len(errors)
                close(mean, pair[role]["mae_ms"], "Speaker mean")
                means.append(mean)
            difference = float(np.round(means[0] - means[1], 9))
            close(difference, pair["rank_difference_ms"], "Rounded rank input", atol=0)
            delta.append(difference)
        nonzero = np.array([d for d in delta if d != 0])
        if len(nonzero):
            result = stats.wilcoxon(
                nonzero,
                alternative="two-sided",
                zero_method="wilcox",
                method=stats.PermutationMethod(n_resamples=np.inf, batch=8192),
            )
            close(result.statistic, comparison["w"], "Wilcoxon W", atol=0)
            close(result.pvalue, comparison["p_value_raw"], "Exact SciPy p-value", atol=1e-15)
            p = float(result.pvalue)
        else:
            p = 1.0
            require(
                comparison["w"] == 0 and comparison["p_value_raw"] == 1, "All-zero speaker case"
            )
        raw_p.append(p)
        keys.append(key)
        print(f"[*] independent {name}/{key}: exact SciPy test verified", flush=True)
    order = np.argsort(raw_p, kind="stable")
    holm = np.minimum(
        1, np.maximum.accumulate(np.array(raw_p)[order] * np.arange(len(raw_p), 0, -1))
    )
    for index, p in zip(order, holm, strict=True):
        item = saved["speaker_comparisons"][keys[index]]
        close(p, item["p_value_holm"], "Holm p-value", atol=1e-15)
        require(
            item["significant_0_05"] == (p < 0.05) and item["significant_0_01"] == (p < 0.01),
            "Significance flag differs",
        )
    require(
        saved["original_clip_comparisons"] == frozen["statistical_significance"],
        "Original clip tests were altered",
    )
    return {
        "boundary_records_verified": records,
        "tier_cis_verified": len(values) * 2,
        "speaker_tests_verified": len(raw_p),
        "scipy_exact_p_values": dict(zip(keys, raw_p, strict=True)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", required=True)
    args = parser.parse_args()
    work = local_path(args.analysis_dir)
    report_path = work / "independent_check.json"
    require(not report_path.exists(), "Independent report already exists")
    analysis = read_json((work / "analysis.json").relative_to(ROOT).as_posix())
    code_start = code_provenance()
    require(code_start["git_worktree_dirty"] is False, "Commit verification code before checking")
    require(analysis["status"] == "COMPLETE", "Analysis did not complete")
    for p, sha in analysis["protected_files"].items():
        require(digest(local_path(p)) == sha, f"Protected file changed: {p}")
    result = {
        "schema_version": 1,
        "status": "VERIFIED",
        "analysis_sha256": digest(work / "analysis.json"),
        "code": code_start,
        "checker_sha256": digest(Path(__file__).resolve()),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "corpora": {},
    }
    for name, saved in analysis["corpora"].items():
        result["corpora"][name] = check_corpus(name, saved, work)
    figure_manifest = read_json((work / "figure_manifest.json").relative_to(ROOT).as_posix())
    require(
        figure_manifest["analysis_sha256"] == result["analysis_sha256"],
        "Figures refer to a different analysis",
    )
    require(
        figure_manifest["renderer_sha256"] == digest(ROOT / "scripts/render_error_analysis.py"),
        "Renderer source changed",
    )
    require(
        len(figure_manifest["files"]) == 24, "Expected six figures in two languages and two formats"
    )
    for relative, data in figure_manifest["files"].items():
        path = local_path(relative)
        require(digest(path) == data["sha256"], "Figure hash mismatch")
        if path.suffix == ".png":
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                dpi = im.info.get("dpi", (0, 0))
                require(min(dpi) >= 299.9 and min(im.size) >= 1000, "Low-resolution figure")
    result["figure_files_verified"] = len(figure_manifest["files"])
    for relative, sha in figure_manifest["tables"].items():
        path = local_path(relative)
        require(digest(path) == sha, "Table hash mismatch")
        corpus = path.stem.removeprefix("speaker_tests_")
        table_rows = [
            line
            for line in path.read_text().splitlines()
            if " & " in line and not line.startswith("Comparison")
        ]
        require(len(table_rows) == 7, "Speaker table rows incomplete")
        for line, values in zip(
            table_rows, analysis["corpora"][corpus]["speaker_comparisons"].values(), strict=True
        ):
            cells = [cell.strip() for cell in line.removesuffix(r"\\").split("&")]
            require(
                int(cells[1]) == values["n_pairs"]
                and int(cells[2]) == values["n_speakers_improved"],
                "Speaker table counts differ",
            )
            require(
                float(cells[3]) == float(f"{values['p_value_holm']:.6g}"), "Table p-value differs"
            )
    result["table_files_verified"] = len(figure_manifest["tables"])
    result["figure_manifest_sha256"] = digest(work / "figure_manifest.json")
    for p, sha in analysis["protected_files"].items():
        require(digest(local_path(p)) == sha, f"Protected file changed during verification: {p}")
    result["code_end"] = code_provenance()
    require(result["code_end"] == code_start, "Verification worktree changed")
    result["scope"] = (
        "Separate timestamp/denominator checks, direct speaker bootstrap and exhaustive SciPy sign permutations; frozen token matching/folding reused. No new model execution or human annotation audit."
    )
    write_json(report_path, result)
    print("[+] Independent E1 verification passed", flush=True)


if __name__ == "__main__":
    main()
