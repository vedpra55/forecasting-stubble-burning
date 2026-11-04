"""Verify Sentinel-1 GRD over the pilot district and measure acquisitions per season.

Sentinel-1B failed on 2021-12-23, so seasons 2022-2024 should show roughly half the
acquisitions of 2019-2021. Sentinel-1C opened to users in March 2025 (not measured here:
2025 is a test season and stays untouched in Phase 1).
"""

from __future__ import annotations

from _common import run_check

from stubblecast import config
from stubblecast.data import gee_region


def check() -> dict:
    import ee

    src = config.load("sources")["gee"]
    district = config.load("region")["cost_pilot_district"]
    region = gee_region.to_ee(gee_region.district_shape("Punjab", district))
    seasons = config.load("seasons")["eda_seasons"]

    base = (ee.ImageCollection(src["s1"]).filterBounds(region)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH")))

    per = {}
    for s in seasons:
        c = base.filterDate(f"{s}-08-01", f"{s}-12-06")
        per[s] = {
            "n_images": c.size(),
            "dates": c.aggregate_array("system:time_start").map(
                lambda t: ee.Date(t).format("YYYY-MM-dd")).distinct(),
            "platforms": c.aggregate_histogram("platform_number"),
            "passes": c.aggregate_histogram("orbitProperties_pass"),
            "rel_orbits": c.aggregate_array("relativeOrbitNumber_start").distinct(),
        }
    sample = base.filterDate("2023-10-01", "2023-11-01").first()
    stats = sample.select(["VV", "VH"]).reduceRegion(
        ee.Reducer.mean(), region, scale=100, maxPixels=1e9)
    info = ee.Dictionary({"per": per, "bands": sample.bandNames(), "stats": stats}).getInfo()

    out = {}
    for s, v in info["per"].items():
        dates = sorted(v["dates"])
        gaps = [(_d(b) - _d(a)).days for a, b in zip(dates[:-1], dates[1:], strict=True)]
        out[s] = {"n_images": v["n_images"], "n_dates": len(dates),
                  "platforms": v["platforms"], "passes": v["passes"],
                  "relative_orbits": sorted(v["rel_orbits"]),
                  "max_gap_days": max(gaps) if gaps else None,
                  "median_gap_days": sorted(gaps)[len(gaps) // 2] if gaps else None}
    return {
        "_ok": "VV" in info["bands"] and "VH" in info["bands"],
        "dataset": src["s1"], "district": district, "window": "Aug 1 - Dec 5",
        "bands": info["bands"], "sample_mean_db_oct2023": info["stats"],
        "per_season": out,
    }


def _d(s):
    from datetime import date

    return date.fromisoformat(s)


if __name__ == "__main__":
    run_check("verify_s1", check)
