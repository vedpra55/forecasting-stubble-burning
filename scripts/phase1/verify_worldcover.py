"""Verify ESA WorldCover v200 and count cropland grid cells at candidate cell sizes.

A cell counts as cropland if >= min_cropland_fraction of its 10 m pixels are class 40.
The Punjab-wide counts give the denominator for class-imbalance estimates.
"""

from __future__ import annotations

from _common import run_check

from stubblecast import config
from stubblecast.data import gee_region


def check() -> dict:
    import ee

    src = config.load("sources")["gee"]
    g = config.load("grid")
    wc = ee.Image(ee.ImageCollection(src["worldcover"]).first())
    crop = wc.select("Map").eq(g["cropland_class"])

    regions = {d: gee_region.to_ee(gee_region.district_shape("Punjab", d))
               for d in config.load("region")["candidate_pilot_districts"]}
    regions["Punjab"] = gee_region.to_ee(gee_region.state_shape("Punjab"), simplify=0.002)
    regions["Haryana"] = gee_region.to_ee(gee_region.state_shape("Haryana"), simplify=0.002)
    out = {"bands": wc.bandNames().getInfo(), "cropland_class": g["cropland_class"]}
    for name, region in regions.items():
        res = {}
        frac = crop.reduceRegion(ee.Reducer.mean(), region, scale=30, maxPixels=1e10,
                                 tileScale=4).get("Map")
        res["cropland_pixel_fraction_30m"] = frac
        for cell in g["candidate_cell_sizes_m"]:
            # No explicit reproject: reduceRegion's crs/scale drives reduceResolution.
            # tileScale=16 keeps each tile's 10 m input under EE's reprojection limit
            # (tileScale=4 failed with "Reprojection output too large" at >=500 m).
            cell_frac = crop.reduceResolution(ee.Reducer.mean(), maxPixels=20000)
            ok = cell_frac.gte(g["min_cropland_fraction"])
            # unweighted(): count whole cells; the default weights edge cells by overlap.
            hist = ok.reduceRegion(ee.Reducer.frequencyHistogram().unweighted(), region,
                                   crs=g["crs"], scale=cell, maxPixels=1e10,
                                   tileScale=16).get("Map")
            res[f"cells_{cell}m"] = hist
        out[name] = ee.Dictionary(res).getInfo()
        for cell in g["candidate_cell_sizes_m"]:
            h = out[name].pop(f"cells_{cell}m") or {}
            out[name][f"cells_{cell}m"] = {"cropland_ge_threshold": int(h.get("1", 0)),
                                           "total": int(sum(h.values()))}
    out["_ok"] = out["Punjab"]["cells_500m"]["cropland_ge_threshold"] > 0
    out["dataset"] = src["worldcover"]
    out["note"] = "WorldCover v200 is a single 2021 map; cropland mask is static across seasons."
    return out


if __name__ == "__main__":
    run_check("verify_worldcover", check)
