from datetime import date

import pandas as pd
import pytest

from stubblecast.data import firms


def _raw(conf, n=3):
    return pd.DataFrame({
        "latitude": [30.2] * n, "longitude": [75.8] * n,
        "acq_date": ["2023-11-01"] * n, "acq_time": ["0812", "812", "2005"][:n],
        "confidence": conf, "version": ["2"] * n,
    })


def test_viirs_confidence_is_categorical():
    df = firms.normalise(_raw(["l", "n", "h"]), "viirs_noaa20")
    assert list(df.confidence_class) == ["low", "nominal", "high"]
    assert df.confidence_pct.isna().all()


def test_viirs_rejects_numeric_confidence():
    with pytest.raises(ValueError):
        firms.normalise(_raw(["50", "n", "h"]), "viirs_noaa20")


def test_modis_confidence_is_numeric_and_bounded():
    df = firms.normalise(_raw(["0", "55", "100"]), "modis")
    assert df.confidence_class.isna().all()
    with pytest.raises(ValueError):
        firms.normalise(_raw(["0", "55", "101"]), "modis")


def test_acq_time_parsing_handles_missing_leading_zero():
    df = firms.normalise(_raw(["n", "n", "n"]), "viirs_noaa20")
    assert df.acq_hour_utc.tolist() == pytest.approx([8.2, 8.2, 20 + 5 / 60])


@pytest.mark.parametrize("d,expected", [
    (date(2023, 9, 24), False), (date(2023, 9, 25), True),
    (date(2023, 12, 5), True), (date(2023, 12, 6), False),
])
def test_season_window_is_inclusive(d, expected):
    assert firms.in_season(d, 2023, "09-25", "12-05") is expected


def test_test_seasons_are_guarded():
    with pytest.raises(PermissionError):
        firms.load_year("viirs_noaa20", 2025, allowed_years=[2019, 2020])
