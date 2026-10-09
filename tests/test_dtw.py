import numpy as np
import pytest

from subtitle_workbench.dtw import banded_dtw


def test_identical_sequence_has_diagonal_zero_cost():
    result = banded_dtw(np.arange(5), np.arange(5), band=1)
    np.testing.assert_array_equal(result.path, np.column_stack((np.arange(5), np.arange(5))))
    assert result.cost == 0
    assert result.cells == 13


def test_expanded_sequence_has_complete_monotone_zero_cost_path():
    result = banded_dtw(np.array([0, 1, 2]), np.array([0, 0, 1, 2, 2]), band=2)
    np.testing.assert_array_equal(result.path[[0, -1]], [[0, 0], [2, 4]])
    steps = np.diff(result.path, axis=0)
    assert np.all((steps >= 0) & (steps <= 1))
    assert np.all(steps.sum(axis=1) >= 1)
    assert result.cost == 0


def test_nonzero_distance_matches_manual_cost():
    result = banded_dtw(np.array([0, 1]), np.array([0, 2]), band=1)
    assert result.cost == 1


@pytest.mark.parametrize(
    "reference,target",
    [
        ([0, np.nan], [0, 1]),
        ([0, np.inf], [0, 1]),
        ([0], [0, 1]),
        (np.zeros((2, 2)), np.zeros((2, 3))),
        (np.zeros((2, 0)), np.zeros((2, 0))),
        (np.zeros((2, 2, 2)), np.zeros((2, 2, 2))),
    ],
)
def test_invalid_features_are_rejected(reference, target):
    with pytest.raises(ValueError, match="finite feature"):
        banded_dtw(reference, target, band=1)


def test_cell_guard_prevents_unbounded_allocation():
    with pytest.raises(ValueError, match="exceeding max_cells"):
        banded_dtw(np.arange(100), np.arange(100), band=50, max_cells=100)


def test_disconnected_scaled_band_fails_explicitly():
    with pytest.raises(ValueError, match="no complete DTW path"):
        banded_dtw(np.arange(2), np.arange(30), band=1)


@pytest.mark.parametrize("band", [True, 0, 1.5, 10001])
def test_band_validation(band):
    with pytest.raises(ValueError, match="band must"):
        banded_dtw(np.arange(3), np.arange(3), band=band)
