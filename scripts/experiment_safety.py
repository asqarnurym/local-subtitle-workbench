"""Artifact and process guards for experimental runs; no metric/model changes."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import signal
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any


class IntegrityError(RuntimeError):
    """A run cannot be accepted or safely resumed."""


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def exclusive_lock(path: Path):
    """OS lock releases even on a native crash; the metadata file may remain."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as f:
        f.seek(0, 2)
        if f.tell() == 0:
            f.write(b"0")
            f.flush()
        f.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as err:
            raise IntegrityError(f"Another experiment holds {path}") from err
        try:
            yield
        finally:
            f.seek(0)
            if os.name == "nt":
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def shared_lock() -> Path:
    return Path(tempfile.gettempdir()) / "lsw_mfa_roots" / "experiment.lock"


def kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=30)


def process_options() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


class ProcessTree:
    """Windows job kills descendants even if the immediate parent exits first."""

    def __init__(self, proc: subprocess.Popen):
        self.handle = None
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes as w

        class Basic(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64),
                ("job_time", ctypes.c_int64),
                ("flags", w.DWORD),
                ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t),
                ("active", w.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", w.DWORD),
                ("scheduling", w.DWORD),
            ]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("basic", Basic),
                ("io", ctypes.c_uint64 * 6),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        kernel.CreateJobObjectW.restype = w.HANDLE
        kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        kernel.SetInformationJobObject.restype = w.BOOL
        kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        kernel.AssignProcessToJobObject.restype = w.BOOL
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.CloseHandle.restype = w.BOOL
        self.kernel = kernel
        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            error = ctypes.get_last_error()
            kernel.CloseHandle(handle)
            raise ctypes.WinError(error)
        if not kernel.AssignProcessToJobObject(handle, int(proc._handle)):
            error = ctypes.get_last_error()
            kernel.CloseHandle(handle)
            raise ctypes.WinError(error)
        self.handle = handle

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def validate_bundle(
    run: Path, expected_ids: set[str] | None = None, modes: list[str] | None = None
) -> dict[str, str]:
    """Check hashes, identities, mode-by-clip grid and explicit failure accounting."""
    names = ("benchmark_results.json", "benchmark_utterances.json", "benchmark_predictions.json")
    manifest = read(run / "manifest.json")
    results = read(run / names[0])
    rows = read(run / names[1])
    predictions = read(run / names[2])["modes"]
    ids = set(manifest["inputs"]["audio_files"])
    selected = modes if modes is not None else results["config"]["modes"]
    if expected_ids is not None and ids != expected_ids:
        raise IntegrityError(f"{run}: sample IDs differ")
    if not ids or results["n_utterances"] != len(ids):
        raise IntegrityError(f"{run}: invalid utterance count")
    if results["offline_synthetic"] or results["data_provenance"] != "MODEL_EXECUTION":
        raise IntegrityError(f"{run}: simulated data cannot complete a real experiment")
    if set(results["modes"]) != set(selected) or set(predictions) != set(selected):
        raise IntegrityError(f"{run}: modes differ")
    if set(manifest["config"]["modes"]) != set(selected):
        raise IntegrityError(f"{run}: manifest modes differ")
    pairs = [(r["mode"], r["utterance"]) for r in rows]
    if len(pairs) != len(set(pairs)) or set(pairs) != {(m, i) for m in selected for i in ids}:
        raise IntegrityError(f"{run}: incomplete or duplicate mode/utterance rows")
    for mode in selected:
        if set(predictions[mode]) != ids:
            raise IntegrityError(f"{run}: incomplete predictions for {mode}")
        own = [r for r in rows if r["mode"] == mode]
        for row in own:
            prediction = predictions[mode][row["utterance"]]
            if prediction["status"] != row["status"]:
                # Metrics may validly fail on an otherwise generated prediction
                # (e.g. zero matching words). Preserve that scientific result.
                if not (
                    prediction["status"] == "ok"
                    and row["status"] == "failed"
                    and str(row.get("error", "")).startswith("MetricComputationError:")
                ):
                    raise IntegrityError(f"{run}: unexplained prediction/row status mismatch")
        if any(r["status"] not in {"ok", "failed"} for r in own):
            raise IntegrityError(f"{run}: unknown failure status")
        if (
            sum(r["status"] == "failed" for r in own)
            != results["modes"][mode]["n_utterances_failed"]
        ):
            raise IntegrityError(f"{run}: failure counts differ for {mode}")
    hashes = {}
    for name in (*names, "manifest.json"):
        digest = sha(run / name)
        if name in names and digest != manifest["outputs"][name]["sha256"]:
            raise IntegrityError(f"{run}: changed output {name}")
        hashes[name] = digest
    return hashes


def validate_complete(run: Path, condition: dict, expected_ids=None, modes=None) -> None:
    record = read(run / "run_record.json")
    for key, value in condition.items():
        if record.get(key) != value:
            raise IntegrityError(f"{run}: condition {key} differs")
    hashes = validate_bundle(run, expected_ids, modes)
    if "output_sha256" in record and hashes != record["output_sha256"]:
        raise IntegrityError(f"{run}: completion hashes differ")
    if condition.get("study") == "S3":
        manifest = read(run / "manifest.json")
        if manifest["config"]["asr"]["model"] != condition["asr_model"]:
            raise IntegrityError(f"{run}: ASR model differs")


def effective_sample_ids(root: Path, sample: Path) -> set[str]:
    data = read(sample)
    ids = set(data["utterance_ids"])
    if data["corpus"] == "buckeye":
        frozen = read(root / "reports/buckeye/manifest.json")
        ids -= set(frozen["config"].get("excluded_corpus_defects", {}))
    return ids


def validate_s3_environment(root: Path) -> dict:
    """Snapshot actual selected audio AND annotations, code and frozen weights."""
    sample = root / "reports/buckeye_test_sample_20260401.json"
    raw_ids = read(sample)["utterance_ids"]
    ids = effective_sample_ids(root, sample)
    frozen = read(root / "reports/buckeye/manifest.json")
    if (
        len(raw_ids) != len(set(raw_ids))
        or len(ids) != 999
        or ids != set(frozen["inputs"]["audio_files"])
    ):
        raise IntegrityError("S3 requires the frozen 999-clip sample")
    files = [
        sample,
        root / "uv.lock",
        root / "docs/S2_S3_PROTOCOL.md",
        root / "reports/buckeye/manifest.json",
    ]
    files += sorted((root / "src/subtitle_workbench").glob("*.py"))
    files += [
        root / "scripts" / name
        for name in (
            "speech_benchmark.py",
            "s2_s3_substudies.py",
            "parallel_mfa.py",
            "experiment_safety.py",
            "supervise_experiments.py",
        )
    ]
    files += sorted((root / "models/brqe").glob("*"))
    for cid in ids:
        for ext in (".wav", ".TextGrid"):
            files.append(root / "data/corpora/buckeye" / f"{cid}{ext}")
    snapshot = {p.relative_to(root).as_posix(): sha(p) for p in files}
    mfa = Path.home() / "Documents/MFA/pretrained_models"
    for name in (
        "acoustic/english_us_arpa.zip",
        "dictionary/english_us_arpa.dict",
        "g2p/english_us_arpa.zip",
    ):
        snapshot[f"@mfa/{name}"] = sha(mfa / name)
    return snapshot
