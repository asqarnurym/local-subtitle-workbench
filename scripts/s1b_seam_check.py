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
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import s1_long_recordings as s1  # noqa: E402
from scripts import speech_benchmark as benchmark  # noqa: E402
from scripts.seam_safe import seam_safe_reconciliation  # noqa: E402

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
            per_speaker[utt.speaker_id] = {"failed": {"multi": multi, "single": single}}
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    out = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    result_file = out / "seam_check.json"
    s1.require(not result_file.exists(), f"{result_file} exists; never overwritten")
    before = s1.git_state()
    s1.require(not before["dirty"], "Worktree is dirty; commit before running")

    from subtitle_workbench.aligner import AlignmentFailure, AlignmentRequest, ForcedAligner
    from subtitle_workbench.asr import WhisperTranscriber
    from subtitle_workbench.pipeline import prepare_alignment_job

    meta = s1.check_build(PROJECT_ROOT / S1_BUILD)
    utts = benchmark.load_textgrid_utterances(
        PROJECT_ROOT / meta["derived_dir"] / LENGTH, "buckeye"
    )
    single_max = max(u.duration for u in utts) + 1.0
    layouts = {"multi": 30.0, "single": single_max}
    t0 = time.perf_counter()

    cached = benchmark.CachedTranscriber(
        WhisperTranscriber(model_size_or_path="large-v3", device="cuda")
    )
    jobs: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        for scenario in SCENARIOS:
            for layout, max_sec in layouts.items():
                jobs[(scenario, layout)] = {
                    u.id: prepare_alignment_job(
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

    aligner = ForcedAligner(mfa_num_jobs=benchmark.MFA_NUM_JOBS)
    seam_log: list[dict[str, Any]] = []
    aligned: dict[tuple[str, str], dict[str, Any]] = {}
    with seam_safe_reconciliation(seam_log):
        for key, by_utt in jobs.items():
            ids = list(by_utt)
            res = aligner.align_requests(
                [
                    AlignmentRequest(audio_path=j.audio_path, chunks=j.chunks, speaker=j.speaker)
                    for j in by_utt.values()
                ],
                engine="mfa",
            )
            aligned[key] = {
                i: (f"{type(r).__name__}: {r}" if isinstance(r, AlignmentFailure) else r)
                for i, r in zip(ids, res, strict=True)
            }
            print(f"[*] aligned {key[0]}/{key[1]} at {time.strftime('%H:%M:%S')}", flush=True)

    results = {s: compare(utts, jobs, aligned, s) for s in SCENARIOS}
    multi_logs = [r for r in seam_log if r["n_chunks"] > 1]
    out.mkdir(parents=True, exist_ok=True)
    s1.write_json(
        result_file,
        {
            "protocol": "docs/S1B_SEAM_SAFE_PROTOCOL.md",
            "created_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "near_seam_s": NEAR_SEAM_S,
            "max_excess_ms": MAX_EXCESS_MS,
            "single_max_chunk_s": single_max,
            "results": results,
            "seams": {
                "n_multi_chunk_recordings": len(multi_logs),
                "frozen_reconciler_would_fail": sum(
                    not r["frozen_reconciler_ok"] for r in multi_logs
                ),
                "monotone_pass_used": sum(r["method"] == "monotone_pass" for r in multi_logs),
                "words_clipped": sum(r["n_clipped"] for r in multi_logs),
                "words_total": sum(r["n_words"] for r in multi_logs),
                "log": seam_log,
            },
            "mfa_retries": aligner.mfa_retries,
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
