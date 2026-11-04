import pytest

from stubblecast.features.weather import rh_from_dewpoint


def test_saturation_is_100pct():
    assert rh_from_dewpoint(300.0, 300.0) == pytest.approx(100.0)


def test_known_value():
    # 25 C air, 15 C dewpoint -> about 54% RH
    assert rh_from_dewpoint(298.15, 288.15) == pytest.approx(53.9, abs=0.5)
