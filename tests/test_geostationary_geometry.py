import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "phase1"))

from geostationary_geometry import geometry  # noqa: E402


def test_nadir_has_zero_view_zenith():
    g = geometry(0.0, 75.0, 75.0)
    assert g["vza_deg"] == pytest.approx(0.0, abs=0.1)
    assert g["slant_km"] == pytest.approx(35786, abs=1)


def test_view_zenith_grows_with_distance():
    near = geometry(30.8, 75.4, 74.0)["vza_deg"]
    mid = geometry(30.8, 75.4, 45.5)["vza_deg"]
    far = geometry(30.8, 75.4, 140.7)["vza_deg"]
    assert near < mid < far < 90
