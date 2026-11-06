"""Supervise S3 with bounded processes, durable heartbeat and strict resume gates.

Run with the locked speech environment, outside the interactive session. A nonzero
exit stops the chain. MFA native-error retries remain bounded inside ForcedAligner;
the supervisor never blindly repeats a scientific run. Inspect and archive a failed
attempt before explicitly resuming. No manuscript text is generated.
"""

from __future__ import annotations

import argparse
import datetime
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import experiment_safety as safety  # noqa: E402


def utc() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def event(out: Path, kind: str, **fields) -> None:
    import json

    with (out / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"utc": utc(), "event": kind, **fields}) + "\n")
        f.flush()


def run_step(out: Path, name: str, args: list[str], hours: float = 12) -> None:
    log = out / f"{name}.log"
    env = dict(
        os.environ,
        PYTHONUNBUFFERED="1",
        LSW_STRICT_INFRASTRUCTURE="1",
        LSW_DIAGNOSTICS_DIR=str(out / "diagnostics" / name),
    )
    start = time.monotonic()
    with log.open("ab") as stream:
        proc = subprocess.Popen(
            [sys.executable, "-X", "faulthandler", "-u", *args],
            cwd=ROOT,
            stdout=stream,
            stderr=subprocess.STDOUT,
            env=env,
            **safety.process_options(),
        )
        tree = None
        try:
            tree = safety.ProcessTree(proc)
            event(out, "started", step=name, pid=proc.pid, timeout_hours=hours)
            poll_count = 0
            while proc.poll() is None:
                free = shutil.disk_usage(ROOT).free
                age = max(0, time.time() - log.stat().st_mtime)
                state = {
                    "state": "running",
                    "step": name,
                    "pid": proc.pid,
                    "supervisor_pid": os.getpid(),
                    "utc": utc(),
                    "elapsed_seconds": round(time.monotonic() - start),
                    "log_quiet_seconds": round(age),
                    "disk_free_bytes": free,
                }
                safety.atomic_json(out / "status.json", state)
                if poll_count % 5 == 0:
                    event(out, "health", **{k: v for k, v in state.items() if k != "utc"})
                if free < 5 * 1024**3:
                    raise RuntimeError("Less than 5 GiB free; stopping before disk exhaustion")
                if time.monotonic() - start > hours * 3600:
                    raise TimeoutError(f"{name}: wall-clock limit exceeded")
                # Quiet logs produce a warning, never an inference of a hung engine.
                if age > 1800 and poll_count % 5 == 0:
                    event(out, "quiet_log_warning", step=name, seconds=round(age))
                poll_count += 1
                try:
                    proc.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    pass
            if proc.returncode:
                raise RuntimeError(f"{name}: exit {proc.returncode}; inspect {log}")
            event(out, "finished", step=name, seconds=round(time.monotonic() - start))
        finally:
            if proc.poll() is None:
                safety.kill_tree(proc)
            if tree is not None:
                tree.close()


def smoke(out: Path, workers: int) -> int:
    from scripts import s2_s3_substudies as sub

    original = safety.read(ROOT / sub.BUCKEYE_SAMPLE)
    ids = original["utterance_ids"]
    # Two speakers exercise both concurrent MFA roots and the CTC path.
    chosen = [ids[0], next(i for i in ids if i[:3] != ids[0][:3])]
    sample = out / "smoke_sample.json"
    safety.atomic_json(
        sample,
        {
            "schema_version": benchmark_sample_schema(),
            "corpus": "buckeye",
            "utterance_ids": chosen,
        },
    )
    with safety.exclusive_lock(safety.shared_lock()):
        sub._run_one(
            out / "smoke",
            workers,
            {"study": "S3_smoke", "asr_model": "tiny"},
            corpus="buckeye",
            data_dir=ROOT / sub.BUCKEYE_DIR,
            utterance_list=sample,
            modes=sub.S3_MODES,
            asr_model="tiny",
        )
    # A successful process alone is insufficient: require real output in every mode.
    result = safety.read(out / "smoke/benchmark_results.json")
    if any(m["n_utterances_failed"] for m in result["modes"].values()):
        raise safety.IntegrityError("Smoke produced failed clips; inspect before a full run")
    return 0


def benchmark_sample_schema() -> int:
    from scripts.speech_benchmark import SAMPLE_SCHEMA_VERSION

    return SAMPLE_SCHEMA_VERSION


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, default=Path("reports/s3_asr_size_20261106"))
    p.add_argument("--mfa-workers", type=int, default=4)
    p.add_argument("--smoke-only", action="store_true")
    p.add_argument("--smoke-worker", action="store_true", help=argparse.SUPPRESS)
    a = p.parse_args()
    out = a.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if a.smoke_worker:
        return smoke(out, a.mfa_workers)
    from scripts import s2_s3_substudies as sub

    with safety.exclusive_lock(out / "supervisor.lock"):
        try:
            snapshot = safety.validate_s3_environment(ROOT)
            baseline = out / "environment.json"
            if baseline.exists() and safety.read(baseline) != snapshot:
                raise safety.IntegrityError("Environment differs from the start snapshot")
            safety.atomic_json(baseline, snapshot)
            if not (out / "smoke/run_record.json").exists():
                run_step(
                    out,
                    "smoke",
                    [
                        "scripts/supervise_experiments.py",
                        "--smoke-worker",
                        "--output-dir",
                        str(out),
                        "--mfa-workers",
                        str(a.mfa_workers),
                    ],
                    hours=1,
                )
            else:
                safety.validate_complete(out / "smoke", {"study": "S3_smoke", "asr_model": "tiny"})
            if not a.smoke_only:
                for model in sub.S3_SIZES:
                    if safety.validate_s3_environment(ROOT) != snapshot:
                        raise safety.IntegrityError(
                            "Inputs, code or weights changed between models"
                        )
                    run_step(
                        out,
                        model,
                        [
                            "scripts/s2_s3_substudies.py",
                            "s3-run",
                            "--output-dir",
                            str(out),
                            "--asr-model",
                            model,
                            "--mfa-workers",
                            str(a.mfa_workers),
                        ],
                    )
                    if safety.validate_s3_environment(ROOT) != snapshot:
                        raise safety.IntegrityError(
                            "Inputs, code or weights changed during model run"
                        )
                run_step(
                    out,
                    "analyze",
                    [
                        "scripts/s2_s3_substudies.py",
                        "analyze",
                        "--output-dir",
                        str(out),
                    ],
                    hours=1,
                )
            safety.atomic_json(
                out / "status.json",
                {
                    "state": "smoke_complete" if a.smoke_only else "experiments_complete",
                    "utc": utc(),
                    "literature_pending": True,
                },
            )
            event(out, "chain_complete", smoke_only=a.smoke_only)
            return 0
        except BaseException as err:
            event(out, "chain_stopped", error=f"{type(err).__name__}: {err}")
            safety.atomic_json(
                out / "status.json",
                {
                    "state": "inspection_required",
                    "utc": utc(),
                    "error": f"{type(err).__name__}: {err}",
                },
            )
            traceback.print_exc()
            return 1


if __name__ == "__main__":
    sys.exit(main())
