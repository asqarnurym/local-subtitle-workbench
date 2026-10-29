"""Tests for seeded per-speaker samples and the benchmark --utterance-list option."""

from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from subtitle_workbench.corpora import stage_synthetic_benchmark
from subtitle_workbench.metrics import BenchmarkError
from subtitle_workbench.provenance import sha256

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.speech_benchmark import (  # noqa: E402
    SAMPLE_SCHEMA_VERSION,
    draw_speaker_sample,
    load_synthetic_utterances,
    load_utterance_sample,
    run_benchmark,
    select_utterances,
)


def _synthetic(tmp_path: Path):
    return load_synthetic_utterances(stage_synthetic_benchmark(tmp_path / "synth"))


def _write_sample(path: Path, ids: list[str], corpus: str = "synthetic") -> Path:
    payload = {
        "schema_version": SAMPLE_SCHEMA_VERSION,
        "corpus": corpus,
        "seed": 7,
        "per_speaker": 1,
        "utterance_ids": ids,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _timit_like(root: Path, speakers: int, per_speaker: int) -> Path:
    for s in range(speakers):
        d = root / f"dr1-spk{s}"
        d.mkdir(parents=True)
        for u in range(per_speaker):
            with wave.open(str(d / f"sx{u}.wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16000)
                w.writeframes(b"\x00\x01" * 16000)
            (d / f"sx{u}.wrd").write_text("1600 8000 she\n", encoding="utf-8")
            (d / f"sx{u}.phn").write_text("1600 4000 sh\n4000 8000 iy\n", encoding="utf-8")
    return root


def test_draw_speaker_sample_is_deterministic_and_balanced(tmp_path: Path) -> None:
    utts = _synthetic(tmp_path)
    first = draw_speaker_sample(utts, per_speaker=2, seed=20260401)
    assert first == draw_speaker_sample(list(reversed(utts)), per_speaker=2, seed=20260401)
    assert len(first) == 6 and len(set(first)) == 6
    by_spk: dict[str, list[str]] = {}
    for i in first:
        by_spk.setdefault(i.split("_")[0], []).append(i)
    assert sorted(by_spk) == ["spk01", "spk02", "spk03"]
    assert all(len(v) == 2 and v == sorted(v) for v in by_spk.values())


def test_draw_speaker_sample_speaker_subset(tmp_path: Path) -> None:
    utts = _synthetic(tmp_path)
    ids = draw_speaker_sample(utts, per_speaker=1, seed=3, n_speakers=2)
    assert len(ids) == 2
    assert len({i.split("_")[0] for i in ids}) == 2


@pytest.mark.parametrize(
    ("per_speaker", "seed", "n_speakers", "message"),
    [
        (4, 1, None, "fewer than 4"),
        (0, 1, None, "per_speaker"),
        (1, -1, None, "non-negative"),
        (1, 1, 4, "n_speakers"),
        (1, 1, 0, "n_speakers"),
    ],
)
def test_draw_speaker_sample_rejects_invalid_requests(
    tmp_path: Path, per_speaker: int, seed: int, n_speakers: int | None, message: str
) -> None:
    with pytest.raises(BenchmarkError, match=message):
        draw_speaker_sample(_synthetic(tmp_path), per_speaker, seed, n_speakers)


def test_select_utterances_keeps_list_order_and_rejects_missing(tmp_path: Path) -> None:
    utts = _synthetic(tmp_path)
    picked = select_utterances(utts, ["spk03_utt02", "spk01_utt01"])
    assert [u.id for u in picked] == ["spk03_utt02", "spk01_utt01"]
    with pytest.raises(BenchmarkError, match="not found"):
        select_utterances(utts, ["spk01_utt01", "spk09_utt01"])


def test_load_utterance_sample_validation(tmp_path: Path) -> None:
    good = _write_sample(tmp_path / "good.json", ["a", "b"])
    assert load_utterance_sample(good)["utterance_ids"] == ["a", "b"]
    with pytest.raises(BenchmarkError, match="duplicates"):
        load_utterance_sample(_write_sample(tmp_path / "dup.json", ["a", "a"]))
    with pytest.raises(BenchmarkError, match="non-empty"):
        load_utterance_sample(_write_sample(tmp_path / "empty.json", []))
    bad_schema = tmp_path / "schema.json"
    bad_schema.write_text(json.dumps({"schema_version": 99, "utterance_ids": ["a"]}))
    with pytest.raises(BenchmarkError, match="schema"):
        load_utterance_sample(bad_schema)
    with pytest.raises(BenchmarkError, match="not found"):
        load_utterance_sample(tmp_path / "missing.json")


def test_run_benchmark_with_utterance_list(tmp_path: Path) -> None:
    ids = ["spk02_utt03", "spk01_utt02", "spk03_utt04"]
    sample = _write_sample(tmp_path / "sample.json", ids)
    res = run_benchmark(
        corpus="synthetic",
        output_dir=tmp_path / "out",
        offline_synthetic=True,
        bootstrap_resamples=50,
        utterance_list=sample,
    )
    assert res["n_utterances"] == 3 and res["n_speakers"] == 3
    assert res["config"]["sample"] == {
        "path": sample.as_posix(),
        "sha256": sha256(sample),
        "seed": 7,
        "per_speaker": 1,
        "n_utterances": 3,
    }
    rows = json.loads((tmp_path / "out" / "benchmark_utterances.json").read_text())
    assert {r["utterance"] for r in rows} == set(ids)
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["config"]["sample"]["sha256"] == sha256(sample)
    assert sorted(manifest["inputs"]["audio_files"]) == sorted(ids)


def test_run_benchmark_utterance_list_errors(tmp_path: Path) -> None:
    sample = _write_sample(tmp_path / "timit.json", ["spk01_utt01"], corpus="timit")
    with pytest.raises(BenchmarkError, match="corpus 'timit'"):
        run_benchmark(
            corpus="synthetic",
            output_dir=tmp_path / "o1",
            offline_synthetic=True,
            bootstrap_resamples=10,
            utterance_list=sample,
        )
    with pytest.raises(BenchmarkError, match="mutually exclusive"):
        run_benchmark(
            corpus="synthetic",
            output_dir=tmp_path / "o2",
            offline_synthetic=True,
            bootstrap_resamples=10,
            utterance_list=sample,
            max_utterances=1,
        )


def test_make_benchmark_sample_cli(tmp_path: Path) -> None:
    data = _timit_like(tmp_path / "timit", speakers=4, per_speaker=3)
    out = tmp_path / "reports" / "sample.json"
    cmd = [
        sys.executable,
        "scripts/make_benchmark_sample.py",
        "--corpus",
        "timit",
        "--data-dir",
        str(data),
        "--speakers",
        "3",
        "--per-speaker",
        "2",
        "--seed",
        "20260401",
        "--output",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    assert proc.returncode == 0, proc.stderr
    sample = json.loads(out.read_text(encoding="utf-8"))
    assert sample["schema_version"] == SAMPLE_SCHEMA_VERSION
    assert sample["corpus"] == "timit" and sample["seed"] == 20260401
    assert sample["source_n_utterances"] == 12 and sample["source_n_speakers"] == 4
    assert sample["n_speakers"] == 3 and sample["n_utterances"] == 6
    assert load_utterance_sample(out)["utterance_ids"] == sample["utterance_ids"]

    before = out.read_bytes()
    again = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    assert again.returncode == 1
    assert "refusing to overwrite" in again.stderr
    assert out.read_bytes() == before


def _textgrid_corpus(root: Path, speakers: list[str], per_speaker: int) -> Path:
    """Minimal Buckeye-style clips: <spk>01a_<nnnn>.wav + .TextGrid."""
    root.mkdir(parents=True)
    tg = (
        'File type = "ooTextFile"\nObject class = "TextGrid"\n\nxmin = 0\nxmax = 1\n'
        "tiers? <exists>\nsize = 2\nitem []:\n"
        '    item [1]:\n        class = "IntervalTier"\n        name = "words"\n'
        "        xmin = 0\n        xmax = 1\n        intervals: size = 1\n"
        "        intervals [1]:\n            xmin = 0.1\n            xmax = 0.6\n"
        '            text = "yes"\n'
        '    item [2]:\n        class = "IntervalTier"\n        name = "phones"\n'
        "        xmin = 0\n        xmax = 1\n        intervals: size = 2\n"
        "        intervals [1]:\n            xmin = 0.1\n            xmax = 0.3\n"
        '            text = "y"\n'
        "        intervals [2]:\n            xmin = 0.3\n            xmax = 0.6\n"
        '            text = "eh"\n'
    )
    for spk in speakers:
        for i in range(per_speaker):
            stem = root / f"{spk}01a_{i:04d}"
            with wave.open(str(stem.with_suffix(".wav")), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16000)
                w.writeframes(b"\x00\x01" * 16000)
            stem.with_suffix(".TextGrid").write_text(tg, encoding="utf-8")
    return root


def test_split_speakers_is_deterministic_and_disjoint() -> None:
    from scripts.make_speaker_split import split_speakers

    spk = [f"s{i:02d}" for i in range(1, 41)]
    test, train = split_speakers(list(reversed(spk)), n_test=20, seed=20260401)
    assert (test, train) == split_speakers(spk, n_test=20, seed=20260401)
    assert len(test) == len(train) == 20
    assert not set(test) & set(train) and set(test) | set(train) == set(spk)
    assert test == sorted(test) and train == sorted(train)
    with pytest.raises(BenchmarkError, match="n_test"):
        split_speakers(spk, n_test=40, seed=1)


def test_split_and_group_sample_cli(tmp_path: Path) -> None:
    data = _textgrid_corpus(tmp_path / "bk", ["s01", "s02", "s03", "s04"], per_speaker=3)
    split_path = tmp_path / "reports" / "split.json"
    split_cmd = [
        sys.executable,
        "scripts/make_speaker_split.py",
        "--corpus",
        "buckeye",
        "--data-dir",
        str(data),
        "--n-test",
        "2",
        "--seed",
        "7",
        "--output",
        str(split_path),
    ]
    proc = subprocess.run(split_cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    assert proc.returncode == 0, proc.stderr
    split = json.loads(split_path.read_text(encoding="utf-8"))
    assert len(split["test_speakers"]) == 2 and len(split["train_speakers"]) == 2
    again = subprocess.run(split_cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    assert again.returncode == 1 and "refusing to overwrite" in again.stderr

    out = tmp_path / "reports" / "test_sample.json"
    cmd = [
        sys.executable,
        "scripts/make_benchmark_sample.py",
        "--corpus",
        "buckeye",
        "--data-dir",
        str(data),
        "--per-speaker",
        "2",
        "--seed",
        "7",
        "--split",
        str(split_path),
        "--group",
        "test",
        "--output",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    assert proc.returncode == 0, proc.stderr
    sample = json.loads(out.read_text(encoding="utf-8"))
    assert {i[:3] for i in sample["utterance_ids"]} == set(split["test_speakers"])
    assert sample["n_utterances"] == 4
    assert sample["split"]["group"] == "test"
    assert sample["split"]["sha256"] == sha256(split_path)


def test_run_benchmark_writes_predictions_and_runtime(tmp_path: Path) -> None:
    res = run_benchmark(
        corpus="synthetic",
        output_dir=tmp_path / "out",
        offline_synthetic=True,
        bootstrap_resamples=20,
    )
    rt = res["runtime"]
    assert rt["note"].startswith("transparency only")
    assert rt["audio_seconds"] > 0 and rt["rtf_total"] >= 0
    preds = json.loads((tmp_path / "out" / "benchmark_predictions.json").read_text())
    assert set(preds["modes"]) == set(res["modes"])
    b2 = preds["modes"]["B2_proposed"]
    assert len(b2) == 10
    first = next(iter(b2.values()))
    assert first["status"] == "ok" and len(first["words"][0]) == 5 and first["phones"]
    assert preds["modes"]["B0_whisper"][next(iter(b2))]["phones"] is None
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["outputs"]["benchmark_predictions.json"]["sha256"] == sha256(
        tmp_path / "out" / "benchmark_predictions.json"
    )
