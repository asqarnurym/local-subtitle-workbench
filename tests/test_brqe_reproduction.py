"""Independent reproduction checks must detect state and forward-output drift."""

import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_brqe_reproduction import compare_outputs, compare_states  # noqa: E402
from subtitle_workbench.refiner import Boundary  # noqa: E402


def test_state_comparison_checks_buffers_dtype_and_exact_values():
    original = {"weight": torch.tensor([1.0]), "num_batches_tracked": torch.tensor(12)}
    assert compare_states(original, {k: v.clone() for k, v in original.items()})["equal"]
    control = {k: v.clone() for k, v in original.items()}
    control["num_batches_tracked"] += 1
    assert not compare_states(original, control)["equal"]
    control = {**original, "weight": original["weight"].double()}
    assert not compare_states(original, control)["equal"]
    assert not compare_states(original, {"weight": original["weight"]})["equal"]
    control = {**original, "weight": torch.nextafter(original["weight"], torch.tensor([2.0]))}
    assert not compare_states(original, control)["equal"]


def test_same_state_is_accepted_despite_different_checkpoint_container_bytes(tmp_path: Path):
    original = {"weight": torch.tensor([1.0, 2.0]), "num_batches_tracked": torch.tensor(12)}
    first, second = tmp_path / "first.pt", tmp_path / "second.pt"
    torch.save(original, first)
    torch.save(original, second)
    assert first.read_bytes() != second.read_bytes()
    assert compare_states(
        torch.load(first, weights_only=True), torch.load(second, weights_only=True)
    )["equal"]


def test_direct_forward_comparison_detects_reliability_head_drift():
    def original(x, s):
        return torch.zeros(len(x)), torch.zeros(len(x))

    def changed(x, s):
        return torch.zeros(len(x)), torch.ones(len(x))

    boundaries = [Boundary("u", 0.1, "word_start", "A", 0.2)] * 3
    mels = {"u": np.zeros((64, 60), dtype=np.float32)}
    exact = compare_outputs(original, original, boundaries, mels, batch_size=2)
    assert exact["equal"] and exact["heads"]["error_probability"]["n_values"] == 3
    assert exact["prediction_sha256"]["original"] == exact["prediction_sha256"]["control"]
    drift = compare_outputs(original, changed, boundaries, mels, batch_size=2)
    assert not drift["equal"]
    assert drift["heads"]["shift_seconds"]["n_different"] == 0
    assert drift["heads"]["error_probability"]["n_different"] == 3
