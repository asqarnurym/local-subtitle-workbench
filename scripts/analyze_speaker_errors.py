"""E1a/b: exact speaker tests and descriptive errors, using frozen predictions only."""

from __future__ import annotations

import argparse
import datetime
import json
import platform
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts import speech_benchmark as benchmark  # noqa: E402
from scripts.replay_frozen_metrics import deserialize_predictions, write_json  # noqa: E402
from scripts.verify_frozen_evidence import (  # noqa: E402
    audit,
    digest,
    local_path,
    read_json,
    require,
    verify_reference_snapshot,
)
from subtitle_workbench.metrics import (  # noqa: E402
    BOUNDARY_EPSILON_MS,
    _align_token_sequences,
    bonferroni_holm_adjustment,
)
from subtitle_workbench.phone_sets import fold_phones  # noqa: E402
from subtitle_workbench.provenance import code_provenance  # noqa: E402

FIELDS = [
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
PHONE_GROUPS = {
    "vowel": set("aa ae ah ao aw ay eh er ey ih iy ow oy uh uw".split()),
    "stop": set("b d g p t k".split()),
    "affricate": {"ch", "jh"},
    "fricative": set("f v th dh s z sh zh hh".split()),
    "nasal": {"m", "n", "ng"},
    "approximant": {"l", "r", "w", "y"},
}
BASELINE = "reports/frozen_evidence_audit_20261101.json"


def exact_signed_rank(differences_ms) -> dict:
    d = np.round(np.asarray(differences_ms, dtype=np.float64), 9)
    require(d.ndim == 1 and bool(np.isfinite(d).all()), "Invalid signed-rank differences")
    nonzero = d[d != 0]
    n = len(nonzero)
    require(n <= 30, "Exact DP is restricted to at most 30 nonzero speaker pairs")
    if n == 0:
        return {"w": 0.0, "p_value_raw": 1.0, "n_nonzero": 0}
    absolute = np.abs(nonzero)
    doubled_ranks = np.empty(n, dtype=int)
    order = np.argsort(absolute, kind="stable")
    first = 0
    while first < n:
        last = first + 1
        while last < n and absolute[order[last]] == absolute[order[first]]:
            last += 1
        doubled_ranks[order[first:last]] = first + 1 + last
        first = last
    positive = int(doubled_ranks[nonzero > 0].sum())
    total = int(doubled_ranks.sum())
    w2 = min(positive, total - positive)
    distribution = np.zeros(total + 1, dtype=np.uint64)
    distribution[0] = 1
    for rank in doubled_ranks:
        distribution[rank:] += distribution[:-rank].copy()
    p = min(1.0, 2 * int(distribution[: w2 + 1].sum()) / (2**n))
    return {"w": w2 / 2, "p_value_raw": p, "n_nonzero": n}


def tier_summary(errors, speakers, resamples=2000, seed=42) -> dict:
    errors = np.asarray(errors, dtype=np.float64)
    speakers = np.asarray(speakers)
    labels = sorted(set(speakers))
    require(len(errors) > 0 and len(labels) >= 2, "Insufficient data for speaker CI")
    sums = np.array([errors[speakers == sp].sum() for sp in labels])
    counts = np.array([np.count_nonzero(speakers == sp) for sp in labels])
    hits = np.array(
        [np.count_nonzero(errors[speakers == sp] <= 20 + BOUNDARY_EPSILON_MS) for sp in labels]
    )
    draw = np.random.default_rng(seed).integers(0, len(labels), size=(resamples, len(labels)))
    sampled_n = counts[draw].sum(axis=1)
    return {
        "mae_ms": float(errors.mean()),
        "acc_20ms": float(100 * hits.sum() / counts.sum()),
        "mae_ci_95_ms": np.percentile(sums[draw].sum(axis=1) / sampled_n, [2.5, 97.5]).tolist(),
        "acc_20ms_ci_95": np.percentile(
            100 * hits[draw].sum(axis=1) / sampled_n, [2.5, 97.5]
        ).tolist(),
        "n_boundaries": len(errors),
        "n_speakers": len(labels),
    }


def phone_group(label: str) -> str:
    return next((group for group, labels in PHONE_GROUPS.items() if label in labels), "other")


def duration_bin(seconds: float) -> str:
    return (
        "<100"
        if seconds < 0.1
        else "100-200"
        if seconds < 0.2
        else "200-400"
        if seconds < 0.4
        else ">=400"
    )


def descriptive(values) -> dict:
    a = np.asarray(values, dtype=float)
    if not len(a):
        return {"n_boundaries": 0, "mae_ms": None, "mean_signed_error_ms": None, "acc_20ms": None}
    return {
        "n_boundaries": len(a),
        "mae_ms": float(np.abs(a).mean()),
        "mean_signed_error_ms": float(a.mean()),
        "acc_20ms": float(100 * np.mean(np.abs(a) <= 20 + BOUNDARY_EPSILON_MS)),
    }


def analyze_corpus(name: str, destination: Path) -> dict:
    original = read_json(f"reports/{name}/benchmark_results.json")
    manifest = read_json(f"reports/{name}/manifest.json")
    all_utts = (
        benchmark.load_timit_utterances(local_path("data/corpora/timit"))
        if name == "timit"
        else benchmark.load_textgrid_utterances(local_path("data/corpora/buckeye"), "buckeye")
    )
    utterances = benchmark.select_utterances(all_utts, list(manifest["inputs"]["audio_files"]))
    predictions = deserialize_predictions(read_json(f"reports/{name}/benchmark_predictions.json"))
    frozen_rows = read_json(f"reports/{name}/benchmark_utterances.json")
    successful = {(r["mode"], r["utterance"]) for r in frozen_rows if r["status"] == "ok"}
    destination.mkdir()
    ledger_path = destination / "boundaries.jsonl"
    data, clips = {}, {}
    with ledger_path.open("w", encoding="utf-8", newline="\n") as ledger:
        ledger.write(json.dumps({"schema_version": 1, "fields": FIELDS}) + "\n")
        for mode in original["config"]["modes"]:
            groups = defaultdict(list)
            tier_errors, tier_speakers = defaultdict(list), defaultdict(list)
            references = defaultdict(int)
            per_clip = {}
            for utt in utterances:
                if (mode, utt.id) not in successful:
                    continue
                prediction = predictions[mode][utt.id]
                require(not isinstance(prediction, str), "Scored clip has failed predictions")
                word_errors = []
                for tier, pred, ref in (
                    ("word", prediction[0], utt.ref_words),
                    ("phone", fold_phones(prediction[1] or []), fold_phones(utt.ref_phones)),
                ):
                    pairs = _align_token_sequences(pred, ref)[0]
                    if not pairs:
                        continue
                    references[tier] += len(ref)
                    pred_index, ref_index = (
                        {id(t): i for i, t in enumerate(pred)},
                        {id(t): i for i, t in enumerate(ref)},
                    )
                    for predicted, gold in pairs:
                        label = gold.phoneme if tier == "phone" else ""
                        length = sum(c.isalpha() for c in gold.normalized) if tier == "word" else 0
                        duration = gold.end - gold.start
                        for kind in ("start", "end"):
                            error = (getattr(predicted, kind) - getattr(gold, kind)) * 1000
                            ledger.write(
                                json.dumps(
                                    [
                                        mode,
                                        utt.id,
                                        utt.speaker_id,
                                        tier,
                                        kind,
                                        pred_index[id(predicted)],
                                        ref_index[id(gold)],
                                        label,
                                        duration,
                                        length,
                                        error,
                                    ]
                                )
                                + "\n"
                            )
                            tier_errors[tier].append(abs(error))
                            tier_speakers[tier].append(utt.speaker_id)
                            groups[f"{tier}/{kind}"].append(error)
                            if tier == "word":
                                word_errors.append(abs(error))
                                groups[
                                    f"word/length/{'0' if length == 0 else '1-3' if length <= 3 else '4-6' if length <= 6 else '7+'}"
                                ].append(error)
                                groups[f"word/duration_ms/{duration_bin(duration)}"].append(error)
                            else:
                                groups[f"phone/label/{label}"].append(error)
                                groups[f"phone/group/{phone_group(label)}"].append(error)
                per_clip[utt.id] = {
                    "speaker": utt.speaker_id,
                    "n_boundaries": len(word_errors),
                    "sum_abs_error_ms": float(np.sum(word_errors)),
                    "mae_ms": float(np.mean(word_errors)),
                }
            tiers = {}
            for tier, errors in tier_errors.items():
                summary = tier_summary(errors, tier_speakers[tier])
                frozen = original["modes"][mode][f"{tier}_metrics"]
                require(
                    round(summary["mae_ms"], 2) == frozen["mae_ms"],
                    f"Frozen MAE mismatch: {name}/{mode}/{tier}",
                )
                require(
                    round(summary["acc_20ms"], 2) == frozen["acc_20ms"],
                    f"Frozen accuracy mismatch: {name}/{mode}/{tier}",
                )
                require(
                    [round(v, 2) for v in summary["mae_ci_95_ms"]] == frozen["ci_95"],
                    f"Frozen CI mismatch: {name}/{mode}/{tier}",
                )
                require(
                    summary["n_boundaries"] == frozen["n_boundaries"]
                    and references[tier] == frozen["num_reference"],
                    f"Frozen denominator mismatch: {name}/{mode}/{tier}",
                )
                all_references = sum(
                    len(u.ref_words) if tier == "word" else len(fold_phones(u.ref_phones))
                    for u in utterances
                )
                summary.update(
                    {
                        "num_matched": len(errors) // 2,
                        "num_reference_scored": references[tier],
                        "num_reference_all_attempted": all_references,
                        "coverage_scored": frozen["coverage"],
                        "coverage_all_attempted": (len(errors) // 2) / all_references,
                    }
                )
                tiers[tier] = summary
            for label in ("0", "1-3", "4-6", "7+"):
                groups.setdefault(f"word/length/{label}", [])
            for label in ("<100", "100-200", "200-400", ">=400"):
                groups.setdefault(f"word/duration_ms/{label}", [])
            if "phone" in tiers:
                for label in (*PHONE_GROUPS, "other"):
                    groups.setdefault(f"phone/group/{label}", [])
            data[mode] = {
                "tiers": tiers,
                "breakdowns": {key: descriptive(v) for key, v in sorted(groups.items())},
                "failures": [r for r in frozen_rows if r["mode"] == mode and r["status"] != "ok"],
                "worst_clips": [
                    {"utterance": uid, **v}
                    for uid, v in sorted(
                        per_clip.items(), key=lambda item: (-item[1]["mae_ms"], item[0])
                    )[:10]
                ],
                "quality_estimation": original["modes"][mode].get("quality_estimation"),
            }
            clips[mode] = per_clip
            print(f"[*] {name}/{mode}: boundary analysis complete", flush=True)
    comparisons = {}
    for key, baseline, proposed in benchmark.COMPARISONS:
        common = sorted(clips[baseline].keys() & clips[proposed].keys())
        speakers = sorted({clips[baseline][uid]["speaker"] for uid in common})
        pairs = []
        for speaker in speakers:
            ids = [uid for uid in common if clips[baseline][uid]["speaker"] == speaker]
            values = {}
            for mode in (baseline, proposed):
                count = sum(clips[mode][uid]["n_boundaries"] for uid in ids)
                total = sum(clips[mode][uid]["sum_abs_error_ms"] for uid in ids)
                values[mode] = {"n_boundaries": count, "mae_ms": total / count}
            difference = values[baseline]["mae_ms"] - values[proposed]["mae_ms"]
            pairs.append(
                {
                    "speaker": speaker,
                    "n_common_clips": len(ids),
                    "baseline": values[baseline],
                    "proposed": values[proposed],
                    "difference_ms": difference,
                    "rank_difference_ms": float(np.round(difference, 9)),
                }
            )
        test = exact_signed_rank([v["difference_ms"] for v in pairs])
        comparisons[key] = {
            "baseline": baseline,
            "proposed": proposed,
            "n_pairs": len(pairs),
            "n_common_clips": len(common),
            "common_clip_ids": common,
            "speaker_pairs": pairs,
            "n_speakers_improved": sum(v["rank_difference_ms"] > 0 for v in pairs),
            **test,
        }
    adjusted = bonferroni_holm_adjustment([v["p_value_raw"] for v in comparisons.values()])
    for item, p in zip(comparisons.values(), adjusted, strict=True):
        item.update({"p_value_holm": p, "significant_0_05": p < 0.05, "significant_0_01": p < 0.01})
    write_json(destination / "clip_aggregates.json", clips)
    return {
        "n_utterances": len(utterances),
        "n_speakers": original["n_speakers"],
        "modes": data,
        "speaker_comparisons": comparisons,
        "original_clip_comparisons": original["statistical_significance"],
        "ledger": {"path": ledger_path.relative_to(ROOT).as_posix(), "sha256": digest(ledger_path)},
        "clip_aggregates_sha256": digest(destination / "clip_aggregates.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    destination = local_path(args.output_dir)
    require(
        destination.parent == ROOT / "reports" and not destination.exists(),
        "Choose a fresh reports subdirectory",
    )
    code = code_provenance()
    require(code["git_worktree_dirty"] is False, "Commit analysis protocol and code first")
    started = time.perf_counter()
    preflight = audit()
    verify_reference_snapshot(preflight, read_json(BASELINE))
    protected = {p: v["sha256"] for p, v in preflight["files"].items()}
    protected.update(preflight["reference_snapshot"]["files"])
    protected.update(
        {
            p.relative_to(ROOT).as_posix(): digest(p)
            for p in [
                *[
                    ROOT / "scripts" / name
                    for name in (
                        "analyze_speaker_errors.py",
                        "speech_benchmark.py",
                        "replay_frozen_metrics.py",
                        "verify_frozen_evidence.py",
                        "generate_paper_tables.py",
                    )
                ],
                *sorted((ROOT / "src/subtitle_workbench").glob("*.py")),
                ROOT / "docs/E1_ANALYSIS_PROTOCOL.md",
                ROOT / "uv.lock",
                ROOT / "pyproject.toml",
                local_path(BASELINE),
            ]
        }
    )
    destination.mkdir()
    write_json(destination / "integrity_preflight.json", preflight)
    report = {
        "schema_version": 1,
        "analysis": "E1_SPEAKER_AND_ERROR_ANALYSIS",
        "status": "RUNNING",
        "started_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "code_start": code,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "protocol": {
            "path": "docs/E1_ANALYSIS_PROTOCOL.md",
            "sha256": protected["docs/E1_ANALYSIS_PROTOCOL.md"],
        },
        "method": {
            "pairing": "common successful clip IDs; boundary-pooled MAE per speaker",
            "test": "two-sided exact signed-rank sign permutations, Wilcox zeros, average tie ranks",
            "rank_rounding_ms_decimals": 9,
            "holm_family": "7 comparisons per corpus",
            "bootstrap_resamples": 2000,
            "bootstrap_seed": 42,
        },
        "protected_files": protected,
        "corpora": {},
    }
    try:
        for corpus in ("timit", "buckeye"):
            report["corpora"][corpus] = analyze_corpus(corpus, destination / corpus)
            write_json(destination / "analysis.json", report)
        report["status"] = "COMPLETE"
    except Exception as err:
        report.update({"status": "ERROR", "error": f"{type(err).__name__}: {err}"})
        raise
    finally:
        changed = [
            p
            for p, sha in protected.items()
            if not local_path(p).is_file() or digest(local_path(p)) != sha
        ]
        report["protected_files_changed"] = changed
        report["code_end"] = code_provenance()
        if changed or report["code_end"] != code:
            report["status"] = "ERROR"
        report["seconds"] = round(time.perf_counter() - started, 3)
        report["finished_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
        write_json(destination / "analysis.json", report)
    require(report["status"] == "COMPLETE", "Analysis did not complete cleanly")
    print(f"[+] E1 analysis complete: {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
