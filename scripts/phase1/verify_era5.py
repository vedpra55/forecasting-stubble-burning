"""Verify ERA5-Land daily aggregates: band names, sample values, latency.

Relative humidity is not a band; it is derived from dewpoint and temperature (Magnus
formula) in the feature pipeline. This check computes it for the sample to confirm units.
"""

from __future__ import annotations

import math
from datetime import date

from _common import run_check

from stubblecast import config
from stubblecast.data import gee_region
from stubblecast.features.weather import rh_from_dewpoint


def check() -> dict:
    import ee

    src = config.load("sources")["gee"]
    district = config.load("region")["cost_pilot_district"]
    pt = gee_region.to_ee(gee_region.district_shape("Punjab", district).centroid)
    col = ee.ImageCollection(src["era5_land_daily"])
    bands = src["era5_bands"]
    week = col.filterDate("2023-10-25", "2023-11-01").select(bands)

    def sample(img):
        v = img.reduceRegion(ee.Reducer.first(), pt, scale=11132)
        return ee.Feature(None, v).set("date", img.date().format("YYYY-MM-dd"))

    recent = col.filterDate(ee.Date(date.today().isoformat()).advance(-120, "day"),
                            ee.Date(date.today().isoformat()).advance(1, "day"))
    info = ee.Dictionary({
        "all_bands": col.first().bandNames(),
        "samples": week.map(sample).toList(10).map(lambda f: ee.Feature(f).toDictionary()),
        "latest": ee.Date(recent.aggregate_max("system:time_start")).format("YYYY-MM-dd"),
    }).getInfo()
    missing = [b for b in bands if b not in info["all_bands"]]
    for s in info["samples"]:
        s["rh_pct_derived"] = round(rh_from_dewpoint(s["temperature_2m"],
                                                      s["dewpoint_temperature_2m"]), 1)
        s["wind_speed_ms"] = round(math.hypot(s["u_component_of_wind_10m"],
                                              s["v_component_of_wind_10m"]), 2)
    lag = (date.today() - date.fromisoformat(info["latest"])).days
    return {
        "_ok": not missing,
        "dataset": src["era5_land_daily"], "missing_bands": missing,
        "relative_humidity_band_present": any("humidity" in b for b in info["all_bands"]),
        "samples_sangrur_centroid": info["samples"],
        "latest_available_date": info["latest"], "latency_days_at_check": lag,
    }


if __name__ == "__main__":
    run_check("verify_era5", check)
