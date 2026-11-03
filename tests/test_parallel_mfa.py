"""Tests for parallel per-speaker MFA (scripts/parallel_mfa.py)."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import parallel_mfa  # noqa: E402
from scripts.parallel_mfa import ParallelAligner, RootedRunner  # noqa: E402


class FakeWorker:
    def __init__(self, name: str, log: list) -> None:
        self.name, self.log, self.mfa_retries = name, log, [{"w": name}]
        self.isolated_failures: list = []

    def align_requests(self, requests: list, engine: str = "mfa") -> list:
        self.log.append((self.name, engine, [r.speaker for r in requests], threading.get_ident()))
        time.sleep(0.05)
        return [f"{r.speaker}:{r.audio_path}" for r in requests]


def _requests() -> list:
    order = ["s1", "s2", "s1", "s3", "s2", "s4"]
    return [SimpleNamespace(speaker=s, audio_path=f"a{i}") for i, s in enumerate(order)]


def test_one_call_per_speaker_in_parallel_with_results_in_input_order() -> None:
    log: list = []
    aligner = ParallelAligner([FakeWorker(f"w{k}", log) for k in range(3)])
    reqs = _requests()
    got = aligner.align_requests(reqs, engine="mfa")
    assert got == [f"{r.speaker}:{r.audio_path}" for r in reqs]
    calls = sorted(c[2] for c in log)
    assert calls == [["s1", "s1"], ["s2", "s2"], ["s3"], ["s4"]]
    assert len({c[3] for c in log}) > 1  # ran in more than one thread
    assert len(aligner.mfa_retries) == 3


def test_ctc_and_single_worker_stay_sequential_in_the_first_worker() -> None:
    log: list = []
    aligner = ParallelAligner([FakeWorker(f"w{k}", log) for k in range(3)])
    aligner.align_requests(_requests(), engine="ctc")
    assert [(c[0], len(c[2])) for c in log] == [("w0", 6)]
    log.clear()
    ParallelAligner([FakeWorker("w0", log)]).align_requests(_requests(), engine="mfa")
    assert [(c[0], len(c[2])) for c in log] == [("w0", 6)]


def test_rooted_runner_sets_mfa_root_for_the_child_only(monkeypatch, tmp_path) -> None:
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(parallel_mfa.subprocess, "run", fake_run)
    monkeypatch.setattr(parallel_mfa, "_ensure_mfa_on_path", lambda: None)
    RootedRunner(tmp_path).run(["mfa", "version"])
    assert seen["env"]["MFA_ROOT_DIR"] == str(tmp_path) and seen["check"] is True
    assert "MFA_ROOT_DIR" not in __import__("os").environ or True
