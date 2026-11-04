"""Measure Earth Engine batch cost (EECU-seconds) for one district and one season.

Pipeline mirrors what Phase 3 will run, so the measured cost is representative:
  0. grid      : cropland cells (>= min fraction of WorldCover class 40) -> table asset
  1. s2        : 5-day cloud-masked median composites of NDVI/NBR/NDMI, mean per cell
  2. s1        : VV/VH (linear power) mean per cell for every acquisition
  3. era5      : daily weather at each cell centroid
  Scaling runs : S2 for October only at 300 / 500 / 1000 m, to see how cost scales
                 with cell count (cost should track pixels read, i.e. area, more than cells).

All exports are compact per-cell tables written to Earth Engine assets (rule 6: reduce
server-side, never download imagery). Each task's EECU usage is read back from the task
status / operation metadata and saved to reports/metrics/gee_cost_pilot.json.

Usage:  python scripts/phase1/gee_cost_pilot.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date, timedelta

from stubblecast import config, gee
from stubblecast.data import gee_region
from stubblecast.metrics_io import write_metrics

SEASON = 2023
POLL_SECONDS = 30


def window(season: int) -> tuple[str, str]:
    cfg = config.load("seasons")
    m, d = map(int, cfg["season_start"].split("-"))
    start = date(season, m, d) - timedelta(days=cfg["lookback_days"])
    m1, d1 = map(int, cfg["season_end"].split("-"))
    return start.isoformat(), (date(season, m1, d1) + timedelta(days=1)).isoformat()


def asset_root(project: str) -> str:
    return f"projects/{project}/assets/stubblecast_phase1"


def ensure_folder(path: str) -> None:
    import ee

    try:
        ee.data.getAsset(path)
    except ee.EEException:
        ee.data.createAsset({"type": "FOLDER"}, path)


def delete_if_exists(path: str) -> None:
    import ee

    try:
        ee.data.getAsset(path)
        ee.data.deleteAsset(path)
    except ee.EEException:
        pass


def build_grid(region, cell_m: int):
    import ee

    g = config.load("grid")
    src = config.load("sources")["gee"]
    proj = ee.Projection(g["crs"]).atScale(cell_m)
    crop = (ee.Image(ee.ImageCollection(src["worldcover"]).first())
            .select("Map").eq(g["cropland_class"]).rename("crop_frac"))
    cells = region.coveringGrid(proj)
    cells = crop.reduceRegions(cells, ee.Reducer.mean().setOutputs(["crop_frac"]),
                               scale=10, tileScale=4)
    cells = cells.filter(ee.Filter.gte("crop_frac", g["min_cropland_fraction"]))
    return cells.map(lambda f: f.set({
        "cell_id": f.get("system:index"),
        "lon": f.geometry().centroid(1).coordinates().get(0),
        "lat": f.geometry().centroid(1).coordinates().get(1),
    }))


def _point_row(f, props: list[str]):
    """Compact row with the cell centroid as geometry.

    Export.table.toAsset rejects features with null geometry, so rows carry the cell
    centroid (from the grid's lon/lat properties: no geometry computation needed).
    """
    import ee

    geom = ee.Geometry.Point([f.get("lon"), f.get("lat")])
    return ee.Feature(geom, f.toDictionary(props))


def s2_table(grid, region, start: str, end: str):
    import ee

    src = config.load("sources")["gee"]
    band, thr = src["cloud_score_band"], src["cloud_score_threshold"]
    csp = ee.ImageCollection(src["cloud_score_plus"])
    names = ["NDVI", "NBR", "NDMI"]
    empty = ee.Image.constant([0, 0, 0]).rename(names).updateMask(ee.Image(0)).toFloat()

    def prep(img):
        img = img.updateMask(img.select(band).gte(thr))
        ndvi = img.normalizedDifference(["B8", "B4"])
        nbr = img.normalizedDifference(["B8", "B12"])
        ndmi = img.normalizedDifference(["B8", "B11"])
        # Image.cat drops properties; keep the timestamp or per-period filterDate()
        # below matches nothing and every composite is empty.
        return (ee.Image.cat([ndvi, nbr, ndmi]).rename(names).toFloat()
                .copyProperties(img, ["system:time_start"]))

    s2 = (ee.ImageCollection(src["s2"]).filterBounds(region).filterDate(start, end)
          .linkCollection(csp, [band]).map(prep))
    n_periods = ee.Date(end).difference(ee.Date(start), "day").divide(5).ceil()
    starts = ee.List.sequence(0, n_periods.subtract(1)).map(
        lambda i: ee.Date(start).advance(ee.Number(i).multiply(5), "day"))

    def per_period(d):
        d = ee.Date(d)
        col = s2.filterDate(d, d.advance(5, "day"))
        comp = col.merge(ee.ImageCollection([empty])).median()
        n = col.select("NDVI").merge(ee.ImageCollection([empty.select("NDVI")])).count()
        img = comp.addBands(n.rename("n_obs"))
        fc = img.reduceRegions(grid, ee.Reducer.mean(), scale=20, tileScale=4)
        return fc.map(lambda f: _point_row(
            f, ["cell_id", "NDVI", "NBR", "NDMI", "n_obs"]).set(
            "period_start", d.format("YYYY-MM-dd")))

    return ee.FeatureCollection(starts.map(per_period)).flatten()


def s1_table(grid, region, start: str, end: str):
    import ee

    src = config.load("sources")["gee"]
    s1 = (ee.ImageCollection(src["s1"]).filterBounds(region).filterDate(start, end)
          .filter(ee.Filter.eq("instrumentMode", "IW"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH")))

    def per_image(img):
        lin = ee.Image(10).pow(img.select(["VV", "VH"]).divide(10)).rename(["VV_lin", "VH_lin"])
        fc = lin.reduceRegions(grid, ee.Reducer.mean(), scale=20, tileScale=4)
        fc = fc.filter(ee.Filter.notNull(["VV_lin"]))
        return fc.map(lambda f: _point_row(f, ["cell_id", "VV_lin", "VH_lin"]).set({
                "date": img.date().format("YYYY-MM-dd'T'HH:mm"),
                "pass": img.get("orbitProperties_pass"),
                "rel_orbit": img.get("relativeOrbitNumber_start"),
                "platform": img.get("platform_number")}))

    return s1.map(per_image).flatten()


def era5_table(grid, start: str, end: str):
    import ee

    src = config.load("sources")["gee"]
    pts = grid.map(lambda f: ee.Feature(f.geometry().centroid(1), {"cell_id": f.get("cell_id")}))
    col = ee.ImageCollection(src["era5_land_daily"]).filterDate(start, end).select(
        src["era5_bands"])

    def per_day(img):
        fc = img.reduceRegions(pts, ee.Reducer.first(), scale=11132)
        # pts already carry the centroid geometry; keep it (toAsset rejects null geometry).
        return fc.map(lambda f: ee.Feature(f.geometry(), f.toDictionary()).set(
            "date", img.date().format("YYYY-MM-dd")))

    return col.map(per_day).flatten()


def start_export(fc, asset_id: str, description: str):
    import ee

    delete_if_exists(asset_id)
    task = ee.batch.Export.table.toAsset(collection=fc, description=description,
                                         assetId=asset_id)
    task.start()
    return task


def wait(tasks: dict, project: str) -> dict:
    """Poll until all tasks finish; return final status dicts keyed by name."""
    import ee

    done = {}
    while len(done) < len(tasks):
        for name, t in tasks.items():
            if name in done:
                continue
            st = t.status()
            if st["state"] in ("COMPLETED", "FAILED", "CANCELLED"):
                try:
                    op = ee.data.getOperation(f"projects/{project}/operations/{t.id}")
                    st["operation_metadata"] = op.get("metadata", {})
                except Exception as e:  # noqa: BLE001
                    st["operation_metadata_error"] = str(e)
                done[name] = st
                print(f"  {name}: {st['state']} eecu_s={eecu_seconds(st)}")
        if len(done) < len(tasks):
            time.sleep(POLL_SECONDS)
    return done


def eecu_seconds(st: dict) -> float | None:
    for k in ("batch_eecu_usage_seconds", "batchEecuUsageSeconds"):
        if st.get(k) is not None:
            return float(st[k])
    md = st.get("operation_metadata", {})
    v = md.get("batchEecuUsageSeconds")
    return float(v) if v is not None else None


def geodesic_area_km2(geom) -> float:
    from pyproj import Geod

    return abs(Geod(ellps="WGS84").geometry_area_perimeter(geom)[0]) / 1e6


def table_rows(asset_id: str) -> int | None:
    import ee

    try:
        return int(ee.FeatureCollection(asset_id).size().getInfo())
    except ee.EEException:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="build graphs, export nothing")
    args = ap.parse_args()

    import ee

    project = gee.initialize()
    district = config.load("region")["cost_pilot_district"]
    shp = gee_region.district_shape("Punjab", district)
    region = gee_region.to_ee(shp)
    start, end = window(SEASON)
    oct_start, oct_end = f"{SEASON}-10-01", f"{SEASON}-11-01"
    root = asset_root(project)
    cell_main = config.load("grid")["cell_size_m"]
    sizes = config.load("grid")["candidate_cell_sizes_m"]
    tag = f"{district.lower().replace(' ', '_')}_{SEASON}"

    if args.dry_run:
        g = build_grid(region, 1000)
        print("dry run: 1 km grid cells =", g.size().getInfo())
        return

    ensure_folder(root)
    # Stage 1: grids
    grid_tasks = {f"grid_{c}m": start_export(build_grid(region, c), f"{root}/grid_{tag}_{c}m",
                                             f"grid_{tag}_{c}m") for c in sizes}
    grid_status = wait(grid_tasks, project)
    grids = {c: ee.FeatureCollection(f"{root}/grid_{tag}_{c}m") for c in sizes}

    # Stage 2: feature tables (main cell size, full window) + S2 October scaling runs
    tasks = {
        f"s2_full_{cell_main}m": start_export(s2_table(grids[cell_main], region, start, end),
                                              f"{root}/s2_{tag}_{cell_main}m", "s2_full"),
        f"s1_full_{cell_main}m": start_export(s1_table(grids[cell_main], region, start, end),
                                              f"{root}/s1_{tag}_{cell_main}m", "s1_full"),
        f"era5_full_{cell_main}m": start_export(era5_table(grids[cell_main], start, end),
                                                f"{root}/era5_{tag}_{cell_main}m", "era5_full"),
    }
    for c in sizes:
        tasks[f"s2_oct_{c}m"] = start_export(s2_table(grids[c], region, oct_start, oct_end),
                                             f"{root}/s2oct_{tag}_{c}m", f"s2_oct_{c}m")
    feat_status = wait(tasks, project)

    asset_for = {f"grid_{c}m": f"{root}/grid_{tag}_{c}m" for c in sizes}
    asset_for.update({f"s2_full_{cell_main}m": f"{root}/s2_{tag}_{cell_main}m",
                      f"s1_full_{cell_main}m": f"{root}/s1_{tag}_{cell_main}m",
                      f"era5_full_{cell_main}m": f"{root}/era5_{tag}_{cell_main}m"})
    asset_for.update({f"s2_oct_{c}m": f"{root}/s2oct_{tag}_{c}m" for c in sizes})

    results = {}
    for name, st in {**grid_status, **feat_status}.items():
        results[name] = {
            "state": st["state"], "eecu_seconds": eecu_seconds(st),
            "asset": asset_for[name], "rows": table_rows(asset_for[name]),
            "start_ms": st.get("start_timestamp_ms"), "update_ms": st.get("update_timestamp_ms"),
            "error": st.get("error_message"),
            "raw_status_keys": sorted(st.keys()),
            "operation_metadata": json.loads(json.dumps(st.get("operation_metadata", {}),
                                                        default=str)),
        }
    total = sum(r["eecu_seconds"] or 0 for r in results.values())
    write_metrics("gee_cost_pilot", {
        "district": district, "season": SEASON, "window": [start, end],
        "district_area_km2_geodesic": round(geodesic_area_km2(shp), 1),
        "exports": results, "total_eecu_seconds": total,
        "total_eecu_hours": round(total / 3600, 3),
        "all_completed": all(r["state"] == "COMPLETED" for r in results.values()),
    }, params={"cell_main_m": cell_main, "scaling_sizes_m": sizes,
               "s2_reduce_scale_m": 20, "s1_reduce_scale_m": 20, "s2_composite_days": 5,
               "cloud_score_threshold": config.load("sources")["gee"]["cloud_score_threshold"]})
    print(f"total EECU-hours: {total / 3600:.3f}")


if __name__ == "__main__":
    main()
