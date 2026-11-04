import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "phase1"))

from _common import parse_profile  # noqa: E402


def test_parse_profile_sums_compute_column():
    text = """EECU-s PeakMem Count  Description
  0.512     12M     4  Algorithm Image.reduceRegion
  1.250    3.1G     2  Loading assets: X
"""
    assert parse_profile(text) == pytest_approx(1.762)


def pytest_approx(v):
    import pytest

    return pytest.approx(v)
