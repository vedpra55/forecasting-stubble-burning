"""Verify Sentinel-2 L2A (harmonized) + Cloud Score+ over the cost-pilot district.

Checks: collection ID resolves, expected bands exist, scene count in the pilot season,
Cloud Score+ links by system:index, and per-scene clear-pixel fraction (cs_cdf >= threshold).
"""

from __future__ import annotations

from _common import run_check

from stubblecast import config
from stubblecast.data import gee_region

EXPECTED_BANDS = ["B2", "B3", "B4", "B8", "B8A", "B11", "B12", "SCL"]
SEASON = 2023


def check() -> dict:
    import ee

    src = config.load("sources")["gee"]
    district = config.load("region")["cost_pilot_district"]
    region = gee_region.to_ee(gee_region.district_shape("Punjab", district))
    start, end = f"{SEASON}-09-25", f"{SEASON}-12-06"

    s2 = ee.ImageCollection(src["s2"]).filterBounds(region).filterDate(start, end)
    csp = ee.ImageCollection(src["cloud_score_plus"])
    band = src["cloud_score_band"]
    thr = src["cloud_score_threshold"]
    linked = s2.linkCollection(csp, [band])

    def clear_frac(img):
        clear = img.select(band).gte(thr)
        stats = clear.reduceRegion(ee.Reducer.mean(), region, scale=100, maxPixels=1e9)
        return ee.Feature(None, {
            "date": img.date().format("YYYY-MM-dd"),
            "tile": img.get("MGRS_TILE"),
            "clear_frac": stats.get(band),
            "has_cs": img.bandNames().contains(band),
        })

    first = s2.first()
    info = ee.Dictionary({
        "n_scenes": s2.size(),
        "bands": first.bandNames(),
        "tiles": s2.aggregate_array("MGRS_TILE").distinct(),
        "scenes": linked.map(clear_frac).toList(500).map(
            lambda f: ee.Feature(f).toDictionary()),
    }).getInfo()

    scenes = info.pop("scenes")
    by_date: dict[str, list[float]] = {}
    for s in scenes:
        if s.get("clear_frac") is not None:
            by_date.setdefault(s["date"], []).append(s["clear_frac"])
    date_clear = {d: max(v) for d, v in sorted(by_date.items())}
    vals = list(date_clear.values())
    missing = [b for b in EXPECTED_BANDS if b not in info["bands"]]
    linked_ok = all(s.get("has_cs") for s in scenes)
    return {
        "_ok": not missing and linked_ok and info["n_scenes"] > 0,
        "dataset": src["s2"], "cloud_score_dataset": src["cloud_score_plus"],
        "district": district, "season_window": [start, end],
        "n_scenes": info["n_scenes"], "mgrs_tiles": info["tiles"],
        "missing_expected_bands": missing,
        "cloud_score_linked_all_scenes": linked_ok,
        "n_acquisition_dates": len(date_clear),
        "clear_frac_by_date_best_tile": {d: round(v, 3) for d, v in date_clear.items()},
        "share_dates_ge50pct_clear": round(sum(v >= 0.5 for v in vals) / len(vals), 3)
        if vals else None,
        "median_clear_frac": round(sorted(vals)[len(vals) // 2], 3) if vals else None,
    }


if __name__ == "__main__":
    run_check("verify_s2", check, params={"season": SEASON, "clear_scale_m": 100})
