import json
import subprocess
import sys

import numpy as np
import pytest

from subtitle_workbench.demo import generate
from subtitle_workbench.pipeline import align, sha256


def error_boundaries(oracle, timeline):
    return np.array(
        [
            abs(clip[key] - cue[boundary])
            for cue, clip in zip(oracle["cues"], timeline["hasPart"], strict=True)
            for key, boundary in (("startOffset", "start"), ("endOffset", "end"))
        ]
    )


@pytest.mark.parametrize("shift,stretch", [(0.0, 1.0), (0.24, 1.08), (0.12, 0.92)])
def test_timing_transfer_against_controlled_oracle(tmp_path, shift, stretch):
    fixture = tmp_path / "input"
    oracle = generate(fixture, shift, stretch)
    output = tmp_path / "output"
    manifest = align(
        fixture / "reference.wav", fixture / "target.wav", fixture / "cues.json", output
    )
    timeline = json.loads((output / "timeline.jsonld").read_text())
    assert error_boundaries(oracle, timeline).max() <= 0.05
    assert manifest["metrics"]["cue_count"] == 6
    assert manifest["metrics"]["evaluated_cells"] <= manifest["config"]["max_cells"]
    assert manifest["inputs"]["reference_audio"]["sha256"] == sha256(fixture / "reference.wav")
    assert manifest["runtime"]["numpy"] == np.__version__
    assert len(manifest["code"]["source_sha256"]) == 64
    for name, metadata in manifest["outputs"].items():
        assert sha256(output / name) == metadata["sha256"]
    path = json.loads((output / "alignment-path.json").read_text())["path"]
    assert len(path) == manifest["metrics"]["path_length"]
    assert path[0] == [0, 0]
    assert (output / "subtitles.vtt").read_text().startswith("WEBVTT\n\n")


def test_cli_full_run_and_rejected_overwrite(tmp_path):
    fixture = tmp_path / "input"
    generate(fixture)
    command = [
        sys.executable,
        "-m",
        "subtitle_workbench",
        "--reference",
        str(fixture / "reference.wav"),
        "--target",
        str(fixture / "target.wav"),
        "--cues",
        str(fixture / "cues.json"),
        "--output",
        str(tmp_path / "output"),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["cue_count"] == 6
    before = (tmp_path / "output" / "manifest.json").read_bytes()
    rejected = subprocess.run(command, capture_output=True, text=True, check=False)
    assert rejected.returncode == 2
    assert "already exist" in rejected.stderr
    assert (tmp_path / "output" / "manifest.json").read_bytes() == before


def test_malformed_json_produces_cli_error_without_output(tmp_path):
    fixture = tmp_path / "input"
    generate(fixture)
    (fixture / "cues.json").write_text("not json")
    command = [
        sys.executable,
        "-m",
        "subtitle_workbench",
        "--reference",
        str(fixture / "reference.wav"),
        "--target",
        str(fixture / "target.wav"),
        "--cues",
        str(fixture / "cues.json"),
        "--output",
        str(tmp_path / "output"),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == 2
    assert "error:" in completed.stderr
    assert not (tmp_path / "output").exists()


def test_exports_reproduce_with_same_hashes_and_config(tmp_path):
    fixture = tmp_path / "input"
    generate(fixture)
    for name in ("first", "second"):
        align(
            fixture / "reference.wav",
            fixture / "target.wav",
            fixture / "cues.json",
            tmp_path / name,
        )
    for name in ("subtitles.vtt", "timeline.jsonld", "alignment-path.json"):
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()


def test_excessively_nested_json_is_a_clear_cli_error(tmp_path):
    fixture = tmp_path / "input"
    generate(fixture)
    (fixture / "cues.json").write_text("[" * 15000 + "0" + "]" * 15000)
    command = [
        sys.executable,
        "-m",
        "subtitle_workbench",
        "--reference",
        str(fixture / "reference.wav"),
        "--target",
        str(fixture / "target.wav"),
        "--cues",
        str(fixture / "cues.json"),
        "--output",
        str(tmp_path / "output"),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == 2
    assert "nesting exceeds" in completed.stderr
    assert "Traceback" not in completed.stderr
    assert not (tmp_path / "output").exists()
