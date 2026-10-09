"""Banded dynamic programming with deterministic tie breaking."""

from dataclasses import dataclass
from math import ceil, floor

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class DTWResult:
    path: NDArray[np.int64]
    cost: float
    cells: int


def banded_dtw(
    reference: NDArray, target: NDArray, band: int, max_cells: int = 2_000_000
) -> DTWResult:
    """Use a scaled diagonal band and diagonal/up/left predecessor priority."""
    reference = np.asarray(reference, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    if reference.ndim == 1:
        reference = reference[:, None]
    if target.ndim == 1:
        target = target[:, None]
    if (
        reference.ndim != 2
        or target.ndim != 2
        or reference.shape[1] != target.shape[1]
        or reference.shape[1] == 0
        or min(len(reference), len(target)) < 2
        or not np.isfinite(reference).all()
        or not np.isfinite(target).all()
    ):
        raise ValueError("DTW requires finite feature matrices of matching nonzero width")
    if isinstance(band, bool) or not isinstance(band, int) or not 1 <= band <= 10000:
        raise ValueError("band must be an integer between 1 and 10000")
    if (
        isinstance(max_cells, bool)
        or not isinstance(max_cells, int)
        or not 2 <= max_cells <= 5_000_000
    ):
        raise ValueError("max_cells must be an integer between 2 and 5000000")
    n, m = len(reference), len(target)
    if max(n, m) > 10000:
        raise ValueError("DTW feature sequence exceeds hard limit of 10000 frames")
    ranges = []
    for i in range(n):
        centre = i * (m - 1) / (n - 1)
        ranges.append((max(0, ceil(centre - band)), min(m, floor(centre + band) + 1)))
    cells = sum(right - left for left, right in ranges)
    if cells > max_cells:
        raise ValueError(f"DTW requires {cells} cells, exceeding max_cells={max_cells}")
    previous = np.empty(0)
    previous_left, previous_right = 0, 0
    predecessors: list[NDArray] = []
    for i, (left, right) in enumerate(ranges):
        current = np.full(right - left, np.inf)
        row = np.zeros(right - left, dtype=np.uint8)
        distances = np.sum((target[left:right] - reference[i]) ** 2, axis=1)
        for j in range(left, right):
            if i == 0 and j == 0:
                current[j - left] = distances[j - left]
                continue
            costs = (
                previous[j - 1 - previous_left]
                if i and previous_left <= j - 1 < previous_right
                else np.inf,
                previous[j - previous_left]
                if i and previous_left <= j < previous_right
                else np.inf,
                current[j - left - 1] if j > left else np.inf,
            )
            direction = min(range(3), key=costs.__getitem__)
            current[j - left] = distances[j - left] + costs[direction]
            row[j - left] = direction + 1
        predecessors.append(row)
        previous = current
        previous_left, previous_right = left, right
    if not np.isfinite(previous[-1]):
        raise ValueError("no complete DTW path fits this band; increase band_seconds")
    i, j = n - 1, m - 1
    path = [(i, j)]
    while i or j:
        direction = predecessors[i][j - ranges[i][0]]
        if direction == 1:
            i, j = i - 1, j - 1
        elif direction == 2:
            i -= 1
        elif direction == 3:
            j -= 1
        else:
            raise ValueError("incomplete DTW predecessor path")
        path.append((i, j))
    path.reverse()
    return DTWResult(np.asarray(path, dtype=np.int64), float(previous[-1]), cells)
