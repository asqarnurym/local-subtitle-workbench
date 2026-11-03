"""Parallel MFA for the sub-studies (S1b-S3): several recordings aligned at once.

Each recording is still aligned exactly as by the frozen aligner: one `mfa align` call
with ``num_jobs = 1``, the same models and options. Only the calls for different
recordings run concurrently, each worker in a private MFA root (a copy of the user's
pretrained models and global config with its own temporary directory), so parallel
calls never share MFA's working directory. A deterministic per-recording failure is
isolated as in ``IsolatingAligner``; any other engine error still stops the run.
CTC (GPU) requests stay sequential in the first worker.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue
from typing import Any

from subtitle_workbench.mfa_wrapper import SubprocessRunner, _ensure_mfa_on_path

MFA_HOME = Path.home() / "Documents" / "MFA"


def mfa_root(name: str) -> Path:
    """A private MFA root with the same models and config as the user's default one."""
    root = Path(tempfile.gettempdir()) / "lsw_mfa_roots" / name
    if not (root / "pretrained_models").exists():
        root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(MFA_HOME / "pretrained_models", root / "pretrained_models")
    cfg = [
        f"temporary_directory: {root}" if ln.startswith("temporary_directory:") else ln
        for ln in (MFA_HOME / "global_config.yaml").read_text(encoding="utf-8").splitlines()
    ]
    (root / "global_config.yaml").write_text("\n".join(cfg) + "\n", encoding="utf-8")
    return root


class RootedRunner(SubprocessRunner):
    """The frozen runner, with ``MFA_ROOT_DIR`` set for the child process only."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def run(self, cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
        _ensure_mfa_on_path()
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=timeout,
            env=dict(os.environ, MFA_ROOT_DIR=str(self.root)),
        )


class ParallelAligner:
    """Drop-in for ``IsolatingAligner``: ``workers`` isolating aligners in parallel."""

    def __init__(self, workers: list[Any]) -> None:
        self.workers = workers

    @classmethod
    def build(cls, n: int, num_jobs: int, isolate: bool) -> ParallelAligner:
        """``isolate``: wrap each worker in ``IsolatingAligner`` (one call per recording,
        as S1/S1b do); otherwise the frozen per-speaker batches (S2, S3)."""
        from scripts.s1_long_recordings import IsolatingAligner
        from subtitle_workbench.aligner import ForcedAligner

        workers = []
        for k in range(n):
            inner = ForcedAligner(mfa_num_jobs=num_jobs, mfa_runner=RootedRunner(mfa_root(f"w{k}")))
            workers.append(IsolatingAligner(inner) if isolate else inner)
        return cls(workers)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.workers[0], name)

    @property
    def isolated_failures(self) -> list[dict[str, str]]:
        return [f for w in self.workers for f in getattr(w, "isolated_failures", [])]

    @property
    def mfa_retries(self) -> list[dict[str, object]]:
        return [r for w in self.workers for r in getattr(w, "inner", w).mfa_retries]

    def align_requests(self, requests: list, engine: str = "mfa") -> list:
        """Per speaker, the worker gets all that speaker's requests at once, so MFA still
        runs once per speaker (frozen behaviour); speakers run concurrently."""
        groups: dict[str, list[int]] = {}
        for i, req in enumerate(requests):
            groups.setdefault(req.speaker, []).append(i)
        if engine != "mfa" or len(self.workers) == 1 or len(groups) < 2:
            return self.workers[0].align_requests(requests, engine=engine)
        free: Queue = Queue()
        for w in self.workers:
            free.put(w)

        def one(idx: list[int]) -> list:
            w = free.get()
            try:
                return w.align_requests([requests[i] for i in idx], engine=engine)
            finally:
                free.put(w)

        out: list = [None] * len(requests)
        order = [groups[s] for s in sorted(groups)]
        with ThreadPoolExecutor(max_workers=len(self.workers)) as pool:
            for idx, res in zip(order, pool.map(one, order), strict=True):
                for i, r in zip(idx, res, strict=True):
                    out[i] = r
        return out
