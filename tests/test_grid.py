import numpy as np

from stubblecast.data import grid


def test_points_in_same_cell_share_id_and_neighbours_differ():
    # two points ~100 m apart, one point ~1.2 km away
    lon = np.array([75.80000, 75.80100, 75.81300])
    lat = np.array([30.20000, 30.20000, 30.20000])
    ids = grid.cell_id(lon, lat, 500)
    assert ids[0] == ids[1] or abs(ids[0] - ids[1]) == 10_000_000
    assert ids[2] != ids[0]


def test_cell_count_scales_with_inverse_area():
    rng = np.random.default_rng(0)
    lon = rng.uniform(75.0, 75.5, 200_000)
    lat = rng.uniform(30.0, 30.5, 200_000)
    n500 = len(np.unique(grid.cell_id(lon, lat, 500)))
    n1000 = len(np.unique(grid.cell_id(lon, lat, 1000)))
    assert 3.6 < n500 / n1000 < 4.4
