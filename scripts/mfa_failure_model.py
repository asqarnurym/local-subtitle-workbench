"""Read-only model of MFA chunk failures in the finished S1b runs.

Backlog evidence for docs/MFA_FAILURE_BACKLOG.md. It runs no model and writes nothing:
it reads run records, predictions and the derived reference TextGrids, then prints
chunk failure rates, the independent-chunk prediction of failed recordings, repeat
failures of identical chunks, words lost under both accounting rules and the profile
of failed chunks.

Run from the repository root, without syncing the project environment:
    uv run --no-project --with scipy --with numpy python scripts/mfa_failure_model.py
"""

from __future__ import annotations

import difflib
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

RUNS = Path("reports/s1b_long_20261103/runs")
DERIVED = Path("data/derived/s1b_long_20261103")
LENGTHS = ("L01", "L05", "L10")
SCENARIOS = (("A", "A1", "A2_proposed"), ("B", "B1", "B2_proposed"))
LOG_ORDER = (
    ("B1", "B1_whisper_ctc"),
    ("B2", "B2_proposed"),
    ("A1", "A1_ctc"),
    ("A2", "A2_proposed"),
)


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def reference(speaker: str, length: str) -> list[tuple[float, float, str]]:
    text = (DERIVED / length / f"{speaker}_{length}.TextGrid").read_text(encoding="utf-8")
    words = text.split('name = "phones"')[0]
    pattern = r'xmin = ([\d.]+)\s+xmax = ([\d.]+)\s+text = "(.*?)"'
    return [(float(a), float(b), c.lower()) for a, b, c in re.findall(pattern, words) if c.strip()]


def load(length: str) -> dict[str, Any]:
    """Seam log entries carry no recording name; they follow mode order, successes only."""
    run = RUNS / f"{length}_anchored"
    log = read(run / "run_record.json")["seam_reconciliation_log"]
    rows = read(run / "benchmark_utterances.json")
    seams: dict[tuple[str, str], dict[str, Any]] = {}
    pos = 0
    for name, mode in LOG_ORDER:
        for row in rows:
            if row["mode"] == mode and row["status"] == "ok":
                seams[(name, row["speaker"])] = log[pos]
                pos += 1
    assert pos == len(log), "seam log does not match the successful recordings"
    failed: dict[str, dict[str, list[int]]] = {"A": {}, "B": {}}
    for scenario, _, mode in SCENARIOS:
        for row in rows:
            error = row.get("error", "")
            if row["mode"] == mode and row["status"] != "ok" and "chunk(s)" in error:
                ids = re.search(r"\[([^\]]*)\]", error).group(1)
                failed[scenario][row["speaker"]] = [int(x) for x in ids.split(",")]
    return {"seams": seams, "failed": failed, "speakers": sorted({r["speaker"] for r in rows})}


def bounds(data: dict[str, Any], source: str, speaker: str, end: float) -> list[float]:
    seams = data["seams"][(source, speaker)]["seams"]
    return [0.0, *[s["seam_s"] for s in seams], end]


def rates(runs: dict[str, dict[str, Any]]) -> None:
    print("== chunk failure rate; failed recordings predicted from the L10 rate")
    for scenario, source, _ in SCENARIOS:
        chunks = {
            L: [runs[L]["seams"][(source, s)]["n_chunks"] for s in runs[L]["speakers"]]
            for L in LENGTHS
        }
        lost = {L: sum(map(len, runs[L]["failed"][scenario].values())) for L in LENGTHS}
        p10 = lost["L10"] / sum(chunks["L10"])
        for length in LENGTHS:
            total = sum(chunks[length])
            ci = stats.binomtest(lost[length], total).proportion_ci(method="wilson")
            risks = [1 - (1 - p10) ** n for n in chunks[length]]
            sd = math.sqrt(sum(q * (1 - q) for q in risks))
            print(
                f"{scenario} {length}: {lost[length]}/{total} chunks = "
                f"{lost[length] / total:.4f} [{ci.low:.4f}, {ci.high:.4f}]; recordings "
                f"{len(runs[length]['failed'][scenario])} observed, "
                f"{sum(risks):.1f} +- {sd:.1f} predicted"
            )


def repeats(runs: dict[str, dict[str, Any]]) -> None:
    print("== chunks with identical bounds in L05 and L10: failed again?")
    for scenario, source, _ in SCENARIOS:
        same = again = 0
        for speaker, ids in runs["L05"]["failed"][scenario].items():
            short = bounds(runs["L05"], source, speaker, reference(speaker, "L05")[-1][1])
            long = bounds(runs["L10"], source, speaker, reference(speaker, "L10")[-1][1])
            for k in ids:
                if k + 1 >= len(short) - 1:
                    continue  # the last chunk of the shorter recording ends differently
                for j in range(len(long) - 1):
                    if abs(long[j] - short[k]) < 0.05 and abs(long[j + 1] - short[k + 1]) < 0.05:
                        same += 1
                        again += j in runs["L10"]["failed"][scenario].get(speaker, [])
        print(f"{scenario}: {again}/{same}")


def words_lost(runs: dict[str, dict[str, Any]]) -> None:
    print("== reference words lost: whole-recording rule against failed chunks only")
    for length in ("L05", "L10"):
        for scenario, source, _ in SCENARIOS:
            total = whole = inside = 0
            for speaker in runs[length]["speakers"]:
                ref = reference(speaker, length)
                edges = bounds(runs[length], source, speaker, ref[-1][1])
                ids = runs[length]["failed"][scenario].get(speaker, [])
                total += len(ref)
                whole += len(ref) if ids else 0
                inside += sum(any(edges[k] <= w[0] < edges[k + 1] for k in ids) for w in ref)
            print(
                f"{length} {scenario}: {whole}/{total} = {whole / total:.3f}; "
                f"{inside}/{total} = {inside / total:.3f}"
            )


def matched(ref: list[tuple[float, float, str]], hyp: list[list[Any]]) -> dict[int, list[Any]]:
    tokens = ([r[2] for r in ref], [h[1] for h in hyp])
    matcher = difflib.SequenceMatcher(None, *tokens, autojunk=False)
    return {
        block.a + t: hyp[block.b + t]
        for block in matcher.get_matching_blocks()
        for t in range(block.size)
    }


def profile(runs: dict[str, dict[str, Any]]) -> None:
    print("== L10 chunks, median failed / other, Mann-Whitney p (descriptive, uncorrected)")
    data = runs["L10"]
    modes = read(RUNS / "L10_anchored" / "benchmark_predictions.json")["modes"]
    for scenario, source, _ in SCENARIOS:
        rows = []
        for speaker in data["speakers"]:
            ref = reference(speaker, "L10")
            edges = bounds(data, source, speaker, ref[-1][1])
            ctc = matched(ref, modes["A1_ctc"][f"{speaker}_L10"]["words"])
            asr = matched(ref, modes["B0_whisper"][f"{speaker}_L10"]["words"])
            ids = data["failed"][scenario].get(speaker, [])
            for k in range(len(edges) - 1):
                idx = [i for i, w in enumerate(ref) if edges[k] <= w[0] < edges[k + 1]]
                if len(idx) < 2:
                    continue
                errors = [
                    (abs(ctc[i][2] - ref[i][0]) + abs(ctc[i][3] - ref[i][1])) * 500
                    for i in idx
                    if i in ctc
                ]
                rows.append(
                    {
                        "failed": k in ids,
                        "ctc_mae_ms": float(np.mean(errors)),
                        "whisper_word_share": sum(i in asr for i in idx) / len(idx),
                        "words_per_s": len(idx) / (edges[k + 1] - edges[k]),
                        "words": len(idx),
                    }
                )
        for key in ("ctc_mae_ms", "whisper_word_share", "words_per_s", "words"):
            bad = [r[key] for r in rows if r["failed"]]
            good = [r[key] for r in rows if not r["failed"]]
            p = stats.mannwhitneyu(bad, good, alternative="two-sided").pvalue
            print(
                f"{scenario} {key}: {np.median(bad):.3f} / {np.median(good):.3f}, "
                f"p = {p:.4f} (n = {len(bad)} / {len(good)})"
            )


def main() -> None:
    runs = {length: load(length) for length in LENGTHS}
    rates(runs)
    repeats(runs)
    words_lost(runs)
    profile(runs)


if __name__ == "__main__":
    main()
