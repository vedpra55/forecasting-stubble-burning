"""Grid helpers.

Phase 1 uses a simple local equirectangular projection to bin points into square
cells for counting. The production grid (Phase 2+) is built in UTM 43N (configs/grid.yaml);
over Punjab the two differ by well under 1% in cell area, which is fine for EDA counts.
"""

from __future__ import annotations

import numpy as np

KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON_EQ = 111.320


def cell_index(lon: np.ndarray, lat: np.ndarray, cell_m: float, lat0: float = 31.0):
    """Return integer (ix, iy) cell indices for points, for square cells of `cell_m` metres."""
    x_km = np.asarray(lon) * KM_PER_DEG_LON_EQ * np.cos(np.deg2rad(lat0))
    y_km = np.asarray(lat) * KM_PER_DEG_LAT
    size_km = cell_m / 1000.0
    return np.floor(x_km / size_km).astype(np.int64), np.floor(y_km / size_km).astype(np.int64)


def cell_id(lon: np.ndarray, lat: np.ndarray, cell_m: float, lat0: float = 31.0) -> np.ndarray:
    """Single int64 id per cell (ix * 1e7 + iy)."""
    ix, iy = cell_index(lon, lat, cell_m, lat0)
    return ix * 10_000_000 + iy
