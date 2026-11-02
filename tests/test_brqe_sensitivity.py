"""Tests for the pre-registered BRQE sensitivity analysis (scripts/brqe_sensitivity.py)."""

from __future__ import annotations

import copy
import dataclasses
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("torchaudio")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.brqe_sensitivity import (  # noqa: E402
    CONFIGS,
    DEFAULT_HALF_WINDOW,
    compare_with_original,
    train_config,
    window_override,
)
from scripts.train_brqe import cross_validate  # noqa: E402
from subtitle_workbench import refiner as refiner_mod  # noqa: E402
from subtitle_workbench.refiner import N_MELS, N_SCALARS, TrainConfig, window_at  # noqa: E402
from tests.test_refiner import _tone_burst_corpus  # noqa: E402


def test_baseline_is_the_frozen_configuration() -> None:
    cfg, half = train_config("baseline")
    assert cfg == TrainConfig() and half == DEFAULT_HALF_WINDOW == refiner_mod.HALF_WINDOW
    # every other configuration changes exactly one hyperparameter
    base = dataclasses.asdict(cfg)
    for name in CONFIGS:
        c, h = train_config(name)
        changed = {k for k, v in dataclasses.asdict(c).items() if base[k] != v}
        assert len(changed) + (h != half) == (0 if name == "baseline" else 1), name


def test_window_override_changes_shapes_and_always_restores() -> None:
    frozen = (refiner_mod.HALF_WINDOW, refiner_mod.WINDOW)
    mel = np.ones((N_MELS, 200), dtype=np.float32)
    with window_override(10):
        assert window_at(mel, 0.5)[0].shape == (N_MELS, 21)
        net = refiner_mod._build_net()
        assert net.mlp[0].in_features == 32 * 21 + N_SCALARS
    assert (refiner_mod.HALF_WINDOW, refiner_mod.WINDOW) == frozen
    with pytest.raises(RuntimeError), window_override(30):
        raise RuntimeError("boom")
    assert (refiner_mod.HALF_WINDOW, refiner_mod.WINDOW) == frozen
    # The default window leaves features and network identical to the frozen module
    with window_override(DEFAULT_HALF_WINDOW):
        inside = window_at(mel, 0.5)[0]
    assert np.array_equal(inside, window_at(mel, 0.5)[0])


def test_cross_validation_runs_with_a_changed_window() -> None:
    mels, bounds = _tone_burst_corpus(40, np.random.default_rng(3))
    cfg = TrainConfig(epochs=1, batch_size=16)
    with window_override(10):
        cv = cross_validate(bounds, mels, 2, cfg)
    assert cv["scores"]["brqe"]["word_A"]["n_boundaries"] == 40
    assert len(cv["folds"]) == 2


def test_compare_with_original_reports_only_real_differences() -> None:
    report = {
        "scores": {"brqe": {"word_A": {"mae_ms": 16.458, "n_boundaries": 10}}},
        "tests": {"word_A": {"brqe_vs_const": {"p_value": 9.5e-05}}},
        "quality_estimation": {"word": {"roc_auc": 0.78}},
        "decision": {"refinement_enters_proposed": True},
        "folds": [{"fold": 0, "held_out": ["s01"], "n_train": 5, "seconds": 1.0}],
    }
    same = copy.deepcopy(report)
    same["folds"][0]["seconds"] = 99.0  # wall time is not compared
    assert compare_with_original(same, report) == []
    other = copy.deepcopy(report)
    other["scores"]["brqe"]["word_A"]["mae_ms"] = 16.459
    other["decision"]["refinement_enters_proposed"] = False
    diffs = compare_with_original(other, report)
    assert len(diffs) == 2 and any("mae_ms" in d for d in diffs)
