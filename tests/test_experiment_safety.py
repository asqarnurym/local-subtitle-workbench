"""Crash/restart guards tested against damaged artifacts and real OS processes."""

import json
from pathlib import Path

import pytest

from scripts import experiment_safety as safe
from scripts import supervise_experiments as supervisor


def test_smoke_sample_uses_real_benchmark_loader(monkeypatch, tmp_path):
    from scripts import s2_s3_substudies as sub
    from scripts.speech_benchmark import load_utterance_sample

    def fake_run(run, workers, record, **kwargs):
        sample = load_utterance_sample(kwargs["utterance_list"])
        assert len(sample["utterance_ids"]) == 2
        assert len({i[:3] for i in sample["utterance_ids"]}) == 2
        safe.atomic_json(
            run / "benchmark_results.json", {"modes": {"test": {"n_utterances_failed": 0}}}
        )

    monkeypatch.setattr(sub, "_run_one", fake_run)
    assert supervisor.smoke(tmp_path, 4) == 0


def test_s3_uses_frozen_exclusion_without_changing_original_sample():
    root = Path(__file__).resolve().parents[1]
    sample = root / "reports/buckeye_test_sample_20260401.json"
    assert len(safe.read(sample)["utterance_ids"]) == 1000
    ids = safe.effective_sample_ids(root, sample)
    assert len(ids) == 999 and "s1901b_0119" not in ids
    assert ids == set(safe.read(root / "reports/buckeye/manifest.json")["inputs"]["audio_files"])


@pytest.mark.parametrize("kind", [MemoryError, ImportError, FileNotFoundError])
def test_resource_errors_stop_strict_experiments_but_not_legacy(monkeypatch, kind):
    from scripts.speech_benchmark import _check_infrastructure_error

    monkeypatch.delenv("LSW_STRICT_INFRASTRUCTURE", raising=False)
    _check_infrastructure_error(kind("example"))
    monkeypatch.setenv("LSW_STRICT_INFRASTRUCTURE", "1")
    with pytest.raises(RuntimeError, match="Infrastructure failure"):
        _check_infrastructure_error(kind("example"))
    _check_infrastructure_error(ValueError("no matching speech"))


def bundle(tmp_path: Path) -> Path:
    modes = ["B0_whisper", "B2_proposed"]
    files = {
        "benchmark_results.json": {
            "n_utterances": 2,
            "offline_synthetic": False,
            "data_provenance": "MODEL_EXECUTION",
            "config": {"modes": modes},
            "modes": {m: {"n_utterances_failed": 1} for m in modes},
        },
        "benchmark_utterances.json": [
            {"mode": m, "utterance": i, "status": s}
            for m in modes
            for i, s in [("a", "ok"), ("b", "failed")]
        ],
        "benchmark_predictions.json": {
            "modes": {m: {"a": {"status": "ok"}, "b": {"status": "failed"}} for m in modes}
        },
    }
    for name, content in files.items():
        safe.atomic_json(tmp_path / name, content)
    safe.atomic_json(
        tmp_path / "manifest.json",
        {
            "inputs": {"audio_files": {"a": "hash-a", "b": "hash-b"}},
            "config": {"modes": modes},
            "outputs": {name: {"sha256": safe.sha(tmp_path / name)} for name in files},
        },
    )
    return tmp_path


def test_bundle_preserves_valid_failures(tmp_path):
    assert len(safe.validate_bundle(bundle(tmp_path), {"a", "b"})) == 4


def test_metric_failure_on_generated_prediction_is_valid(tmp_path):
    run = bundle(tmp_path)
    predictions = safe.read(run / "benchmark_predictions.json")
    predictions["modes"]["B0_whisper"]["b"]["status"] = "ok"
    rows = safe.read(run / "benchmark_utterances.json")
    next(r for r in rows if r["mode"] == "B0_whisper" and r["utterance"] == "b")["error"] = (
        "MetricComputationError: Zero matching tokens"
    )
    safe.atomic_json(run / "benchmark_predictions.json", predictions)
    safe.atomic_json(run / "benchmark_utterances.json", rows)
    manifest = safe.read(run / "manifest.json")
    for name in ("benchmark_predictions.json", "benchmark_utterances.json"):
        manifest["outputs"][name]["sha256"] = safe.sha(run / name)
    safe.atomic_json(run / "manifest.json", manifest)
    safe.validate_bundle(run)


@pytest.mark.parametrize(
    "damage", ["missing", "truncated", "duplicate", "sample", "hash", "counts"]
)
def test_rejects_incomplete_or_incompatible_artifacts(tmp_path, damage):
    run = bundle(tmp_path)
    if damage == "missing":
        (run / "benchmark_predictions.json").unlink()
    elif damage == "truncated":
        (run / "benchmark_results.json").write_text('{"modes":')
    elif damage == "duplicate":
        rows = safe.read(run / "benchmark_utterances.json")
        safe.atomic_json(run / "benchmark_utterances.json", rows + [rows[0]])
    elif damage == "hash":
        with (run / "benchmark_results.json").open("a") as f:
            f.write(" ")
    elif damage == "counts":
        result = safe.read(run / "benchmark_results.json")
        result["modes"]["B0_whisper"]["n_utterances_failed"] = 0
        safe.atomic_json(run / "benchmark_results.json", result)
    with pytest.raises((safe.IntegrityError, FileNotFoundError, json.JSONDecodeError)):
        safe.validate_bundle(run, {"a", "c"} if damage == "sample" else {"a", "b"})


def test_completion_marker_does_not_override_bundle_or_condition(tmp_path):
    run = bundle(tmp_path)
    safe.atomic_json(run / "run_record.json", {"study": "S2", "rate": 1.0})
    safe.validate_complete(run, {"study": "S2", "rate": 1.0})
    with pytest.raises(safe.IntegrityError):
        safe.validate_complete(run, {"study": "S2", "rate": 0.8})
    (run / "manifest.json").unlink()
    with pytest.raises(FileNotFoundError):
        safe.validate_complete(run, {"study": "S2", "rate": 1.0})


def test_lock_prevents_concurrent_start_and_releases(tmp_path):
    path = tmp_path / "experiment.lock"
    with safe.exclusive_lock(path):
        with pytest.raises(safe.IntegrityError):
            with safe.exclusive_lock(path):
                pytest.fail("concurrent lock accepted")
    with safe.exclusive_lock(path):
        pass


def test_atomic_write_failure_preserves_previous_record(monkeypatch, tmp_path):
    path = tmp_path / "state.json"
    safe.atomic_json(path, {"value": 1})

    def disk_full(*args):
        raise OSError("disk full")

    monkeypatch.setattr(safe.os, "replace", disk_full)
    with pytest.raises(OSError):
        safe.atomic_json(path, {"value": 2})
    assert safe.read(path) == {"value": 1}
    assert not list(tmp_path.glob("*.tmp"))


def test_supervisor_records_nonzero_and_does_not_retry(tmp_path):
    with pytest.raises(RuntimeError, match="exit 4"):
        supervisor.run_step(tmp_path, "failed", ["-c", "import sys; sys.exit(4)"])
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert sum(e["event"] == "started" for e in events) == 1


def test_supervisor_kills_timed_out_process(tmp_path):
    with pytest.raises(TimeoutError):
        supervisor.run_step(tmp_path, "timeout", ["-c", "import time; time.sleep(60)"], hours=0)
