"""S1b validation: does a chunk seam cost accuracy with the seam-safe reconciler?

Pre-registered in docs/S1B_SEAM_SAFE_PROTOCOL.md (check C). Each 60 s L01 recording of
the S1 build is aligned twice with identical audio, ASR, anchoring and text: as one
chunk ("single") and with the default <= 30 s chunks and their seams ("multi", seam-safe
reconciler). Word errors near seams (reference onset within 1 s of a seam) are compared
between the two layouts on the same words.

  python scripts/s1b_seam_check.py --output-dir reports/s1b_seam_check_20261103
"""

from __future__ import annotations

import argparse
import datetime
import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import s1_long_recordings as s1  # noqa: E402
from scripts import speech_benchmark as benchmark  # noqa: E402
from scripts.seam_safe import seam_safe_reconciliation  # noqa: E402
from scripts.seam_stitch import stitched_pipeline  # noqa: E402

S1_BUILD = Path("reports/s1_long_20261103")
LENGTH = "L01"
NEAR_SEAM_S = 1.0
MAX_EXCESS_MS = 10.0  # pass rule: pooled near-seam MAE excess of multi over single
SCENARIOS = {"A": "A2 (known text + MFA)", "B": "B2 (Whisper text + MFA)"}


def near_seam(start: float, seams: list[float]) -> bool:
    return any(abs(start - t) <= NEAR_SEAM_S for t in seams)


def compare(utts: list, jobs: dict, aligned: dict, scenario: str) -> dict[str, Any]:
    """Per speaker and pooled MAE on words matched in both layouts, near and far from seams."""
    per_speaker: dict[str, Any] = {}
    pooled: dict[str, list[float]] = {
        k: [] for k in ("near_multi", "near_single", "far_multi", "far_single")
    }
    for utt in utts:
        multi, single = aligned[(scenario, "multi")][utt.id], aligned[(scenario, "single")][utt.id]
        if isinstance(multi, str) or isinstance(single, str):
            # Only the failure text is kept; the other layout may hold aligned words
            per_speaker[utt.speaker_id] = {
                "failed": {
                    layout: res if isinstance(res, str) else None
                    for layout, res in (("multi", multi), ("single", single))
                }
            }
            continue
        seams = [c.start for c in jobs[(scenario, "multi")][utt.id].chunks[1:]]
        em = {i: (s, es, ee) for i, s, es, ee in s1.word_errors(multi, utt.ref_words)}
        es_ = {i: (s, es, ee) for i, s, es, ee in s1.word_errors(single, utt.ref_words)}
        both = sorted(set(em) & set(es_))
        rec: dict[str, Any] = {"n_seams": len(seams), "n_words_both": len(both)}
        for where, keep in (("near", True), ("far", False)):
            idx = [i for i in both if near_seam(em[i][0], seams) == keep]
            vm = [e for i in idx for e in em[i][1:]]
            vs = [e for i in idx for e in es_[i][1:]]
            pooled[f"{where}_multi"] += vm
            pooled[f"{where}_single"] += vs
            rec[where] = {
                "n_words": len(idx),
                "mae_multi_ms": float(np.mean(vm)) if vm else None,
                "mae_single_ms": float(np.mean(vs)) if vs else None,
            }
        per_speaker[utt.speaker_id] = rec

    def mean(v: list[float]) -> float | None:
        return float(np.mean(v)) if v else None

    near_excess = (
        mean(pooled["near_multi"]) - mean(pooled["near_single"]) if pooled["near_multi"] else None
    )
    return {
        "mode": SCENARIOS[scenario],
        "n_boundaries_near": len(pooled["near_multi"]),
        "n_boundaries_far": len(pooled["far_multi"]),
        "near_mae_multi_ms": mean(pooled["near_multi"]),
        "near_mae_single_ms": mean(pooled["near_single"]),
        "near_excess_ms": near_excess,
        "far_mae_multi_ms": mean(pooled["far_multi"]),
        "far_mae_single_ms": mean(pooled["far_single"]),
        "failed": {
            layout: sorted(
                u.speaker_id for u in utts if isinstance(aligned[(scenario, layout)][u.id], str)
            )
            for layout in ("multi", "single")
        },
        "pass": near_excess is not None and near_excess <= MAX_EXCESS_MS,
        "per_speaker": per_speaker,
    }


def reconciliation(reconciler: str, log: list[dict[str, Any]]) -> Any:
    """The chunk handling under test: the seam-safe reconciler or overlap-and-stitch."""
    if reconciler == "stitch":
        return stitched_pipeline(log)
    return seam_safe_reconciliation(log)


def seam_summary(reconciler: str, seam_log: list[dict[str, Any]]) -> dict[str, Any]:
    multi = [r for r in seam_log if r["n_chunks"] > 1]
    if reconciler == "stitch":
        return {
            "n_multi_chunk_recordings": len(multi),
            "n_seams": sum(len(r["seams"]) for r in multi),
            "n_seams_without_anchor": sum(r["n_no_anchor"] for r in multi),
            "log": seam_log,
        }
    return {
        "n_multi_chunk_recordings": len(multi),
        "frozen_reconciler_would_fail": sum(not r["frozen_reconciler_ok"] for r in multi),
        "monotone_pass_used": sum(r["method"] == "monotone_pass" for r in multi),
        "words_clipped": sum(r["n_clipped"] for r in multi),
        "words_total": sum(r["n_words"] for r in multi),
        "log": seam_log,
    }


def mfa_root(k: int) -> Path:
    """A private MFA root (same models and config) so parallel `mfa align` calls never
    share a working directory."""
    home = Path.home() / "Documents" / "MFA"
    root = Path(tempfile.gettempdir()) / "s1b_mfa_roots" / f"w{k}"
    if not (root / "pretrained_models").exists():
        root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(home / "pretrained_models", root / "pretrained_models")
    cfg = [
        f"temporary_directory: {root}" if ln.startswith("temporary_directory:") else ln
        for ln in (home / "global_config.yaml").read_text(encoding="utf-8").splitlines()
    ]
    (root / "global_config.yaml").write_text("\n".join(cfg) + "\n", encoding="utf-8")
    return root


def align_key(task: tuple[str, Path | None, list]) -> dict[str, Any]:
    """Align one (scenario, layout) set of recordings; runs in a worker process."""
    reconciler, root, requests = task
    if root is not None:
        os.environ["MFA_ROOT_DIR"] = str(root)
    from subtitle_workbench.aligner import AlignmentFailure, ForcedAligner

    # One call per recording; MFA NoAlignmentsError becomes that recording's failure
    aligner = s1.IsolatingAligner(ForcedAligner(mfa_num_jobs=benchmark.MFA_NUM_JOBS))
    log: list[dict[str, Any]] = []
    with reconciliation(reconciler, log):
        res = aligner.align_requests(requests, engine="mfa")
    return {
        "results": [
            f"{type(r).__name__}: {r}" if isinstance(r, AlignmentFailure) else r for r in res
        ],
        "log": log,
        "mfa_retries": aligner.mfa_retries,
        "isolated_failures": aligner.isolated_failures,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--reconciler", choices=["seam_safe", "stitch"], default="seam_safe")
    p.add_argument("--workers", type=int, default=1, help="parallel MFA processes (<= 4)")
    p.add_argument("--speakers", nargs="+", help="smoke test on these speakers only")
    args = p.parse_args(argv)
    s1.require(1 <= args.workers <= 4, "--workers must be 1..4")
    out = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    result_file = out / "seam_check.json"
    s1.require(not result_file.exists(), f"{result_file} exists; never overwritten")
    before = s1.git_state()
    s1.require(not before["dirty"], "Worktree is dirty; commit before running")

    from subtitle_workbench import pipeline
    from subtitle_workbench.aligner import AlignmentRequest
    from subtitle_workbench.asr import WhisperTranscriber

    meta = s1.check_build(PROJECT_ROOT / S1_BUILD)
    utts = benchmark.load_textgrid_utterances(
        PROJECT_ROOT / meta["derived_dir"] / LENGTH, "buckeye"
    )
    if args.speakers:
        utts = [u for u in utts if u.speaker_id in args.speakers]
        s1.require(len(utts) == len(args.speakers), "unknown speaker in --speakers")
    single_max = max(u.duration for u in utts) + 1.0
    layouts = {"multi": 30.0, "single": single_max}
    t0 = time.perf_counter()

    # Whisper runs once, in this process only (the GPU holds one large-v3)
    cached = benchmark.CachedTranscriber(
        WhisperTranscriber(model_size_or_path="large-v3", device="cuda")
    )
    jobs: dict[tuple[str, str], dict[str, Any]] = {}
    prep_log: list[dict[str, Any]] = []
    try:
        with reconciliation(args.reconciler, prep_log):
            for scenario in SCENARIOS:
                for layout, max_sec in layouts.items():
                    jobs[(scenario, layout)] = {
                        u.id: pipeline.prepare_alignment_job(
                            u.wav_path,
                            transcriber=cached,
                            transcript_text=u.transcript if scenario == "A" else None,
                            speaker=u.speaker_id,
                            max_chunk_sec=max_sec,
                        )
                        for u in utts
                    }
                    print(f"[*] prepared {scenario}/{layout}", flush=True)
    finally:
        cached.unload()
    for scenario in SCENARIOS:
        s1.require(
            all(len(j.chunks) == 1 for j in jobs[(scenario, "single")].values()),
            "single layout produced more than one chunk",
        )

    keys = list(jobs)
    tasks = [
        (
            args.reconciler,
            mfa_root(k) if args.workers > 1 else None,  # one root per task, never shared
            [
                AlignmentRequest(audio_path=j.audio_path, chunks=j.chunks, speaker=j.speaker)
                for j in jobs[key].values()
            ],
        )
        for k, key in enumerate(keys)
    ]
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            done = list(pool.map(align_key, tasks))
    else:
        done = [align_key(t) for t in tasks]
    aligned: dict[tuple[str, str], dict[str, Any]] = {}
    seam_log: list[dict[str, Any]] = []
    mfa_retries: list[Any] = []
    isolated: list[Any] = []
    for key, d in zip(keys, done, strict=True):
        aligned[key] = dict(zip(jobs[key], d["results"], strict=True))
        seam_log += d["log"]
        mfa_retries += d["mfa_retries"]
        isolated += d["isolated_failures"]
    print(f"[*] aligned all at {time.strftime('%H:%M:%S')}", flush=True)

    results = {s: compare(utts, jobs, aligned, s) for s in SCENARIOS}
    out.mkdir(parents=True, exist_ok=True)
    s1.write_json(
        result_file,
        {
            "protocol": "docs/S1B_SEAM_SAFE_PROTOCOL.md",
            "created_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "reconciler": args.reconciler,
            "workers": args.workers,
            "speakers": sorted(u.speaker_id for u in utts),
            "near_seam_s": NEAR_SEAM_S,
            "max_excess_ms": MAX_EXCESS_MS,
            "single_max_chunk_s": single_max,
            "results": results,
            "seams": seam_summary(args.reconciler, seam_log),
            "mfa_retries": mfa_retries,
            "isolated_failures": isolated,
            "build_sha256": s1.sha_file(PROJECT_ROOT / S1_BUILD / "build.json"),
            "code": s1.code_hashes(),
            "git_before": before,
            "git_after": s1.git_state(),
            "seconds": round(time.perf_counter() - t0, 1),
        },
    )
    for r in results.values():
        print(
            f"[{'+' if r['pass'] else '!'}] {r['mode']}: near-seam MAE multi "
            f"{r['near_mae_multi_ms']} vs single {r['near_mae_single_ms']} ms "
            f"(excess {r['near_excess_ms']}), failed {r['failed']}"
        )
    return 0 if all(r["pass"] for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
