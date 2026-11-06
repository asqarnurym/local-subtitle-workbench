"""Finish S3 artifacts after the supervised chain; keep Windows awake while waiting.

No retries or code changes are made here. An inspection-required state stops this
observer. It writes postprocess_status.json separately from supervisor status.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import experiment_safety as safety  # noqa: E402


@contextlib.contextmanager
def keep_awake():
    if os.name != "nt":
        yield
        return
    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.SetThreadExecutionState.argtypes = [ctypes.c_uint]
    kernel.SetThreadExecutionState.restype = ctypes.c_uint
    if not kernel.SetThreadExecutionState(0x80000001):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        kernel.SetThreadExecutionState(0x80000000)


def command(out: Path, name: str, args: list[str]) -> None:
    with (out / f"{name}.log").open("ab") as log:
        proc = subprocess.Popen(
            args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, **safety.process_options()
        )
        tree = None
        try:
            tree = safety.ProcessTree(proc)
            code = proc.wait(timeout=3600)
            if code:
                raise RuntimeError(f"{name} exited {code}; see {out / (name + '.log')}")
        finally:
            if tree is not None:
                tree.close()
            if proc.poll() is None:
                safety.kill_tree(proc)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    out = a.output_dir.resolve()
    with safety.exclusive_lock(out / "observer.lock"):
        try:
            with keep_awake():
                start = time.monotonic()
                while True:
                    status = safety.read(out / "status.json")
                    if status["state"] == "inspection_required":
                        raise RuntimeError(f"Experiment requires inspection: {status.get('error')}")
                    if status["state"] == "experiments_complete":
                        break
                    # A vanished supervisor or stale heartbeat cannot be called success.
                    age = time.time() - (out / "status.json").stat().st_mtime
                    if age > 180 or time.monotonic() - start > 72 * 3600:
                        raise RuntimeError(
                            "Supervisor heartbeat stale or observer lifetime exceeded"
                        )
                    safety.atomic_json(
                        out / "postprocess_status.json",
                        {
                            "state": "waiting",
                            "observer_pid": os.getpid(),
                            "automatic_sleep_inhibited": os.name == "nt",
                            "supervisor": status,
                        },
                    )
                    time.sleep(30)
                command(
                    out,
                    "report",
                    [
                        "uv",
                        "run",
                        "--no-project",
                        "--python",
                        "3.11",
                        "--with",
                        "matplotlib==3.11.2",
                        "python",
                        "scripts/report_s3_results.py",
                        "--output-dir",
                        str(out),
                        "--figures",
                    ],
                )
                command(
                    out,
                    "literature_inventory",
                    [
                        "uv",
                        "run",
                        "--no-project",
                        "--with",
                        "pymupdf",
                        "python",
                        "scripts/audit_literature_inventory.py",
                    ],
                )
            safety.atomic_json(
                out / "postprocess_status.json",
                {
                    "state": "artifacts_ready_for_review",
                    "report": str(out / "results.md"),
                    "visual_review_pending": True,
                    "literature_manual_checks_pending": True,
                },
            )
            return 0
        except BaseException as err:
            safety.atomic_json(
                out / "postprocess_status.json",
                {
                    "state": "inspection_required",
                    "error": f"{type(err).__name__}: {err}",
                },
            )
            raise


if __name__ == "__main__":
    sys.exit(main())
