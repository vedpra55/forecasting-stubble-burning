"""Verify FIRMS: yearly CSV schema per sensor, coverage, and (if a key is set) the Area API.

Test-season files (2025, 2026) are checked only with an HTTP HEAD request - their
contents are not downloaded or read in Phase 1.
"""

from __future__ import annotations

import os

import requests
from _common import Skipped, run_check
from dotenv import load_dotenv

from stubblecast import config
from stubblecast.data import firms

SENSORS = ["viirs_noaa20", "viirs_snpp", "modis"]


def check_yearly() -> dict:
    years = config.load("seasons")["eda_seasons"]
    out = {}
    for sensor in SENSORS:
        per = {}
        for y in years:
            df = firms.load_year(sensor, y, allowed_years=years)
            per[y] = {
                "rows_in_bbox": len(df),
                "min_date": str(df.acq_date.min()), "max_date": str(df.acq_date.max()),
                "versions": sorted(df.version.astype(str).unique().tolist()),
                "confidence_values": sorted(df.confidence.astype(str).unique().tolist())[:10],
                "type_values": sorted(int(t) for t in df["type"].unique()),
                "satellites": sorted(df.satellite.astype(str).unique().tolist()),
            }
        out[sensor] = {"columns": list(df.columns[:15]), "per_year": per}
    head = {}
    for sensor in SENSORS + ["viirs_noaa21"]:
        for y in (2025, 2026):
            try:
                url = firms.yearly_url(sensor, y)
            except KeyError:
                folder = {"viirs_noaa21": "viirs-jpss2"}[sensor]
                url = config.load("sources")["firms"]["yearly_country_url"].format(
                    folder=folder, year=y, country="India")
            r = requests.head(url, timeout=60, allow_redirects=True)
            head[f"{sensor}_{y}"] = {"http": r.status_code,
                                     "last_modified": r.headers.get("last-modified")}
    viirs_conf_ok = all(set(v["confidence_values"]) <= {"l", "n", "h"}
                        for s in ("viirs_noaa20", "viirs_snpp")
                        for v in out[s]["per_year"].values())
    return {"_ok": viirs_conf_ok, "source": "FIRMS yearly country CSV (public)",
            "per_sensor": out, "test_season_files_head_only": head,
            "viirs_confidence_categorical_lnh": viirs_conf_ok}


def check_api() -> dict:
    load_dotenv(config.REPO_ROOT / ".env")
    key = os.environ.get("FIRMS_MAP_KEY")
    if not key:
        raise Skipped("FIRMS_MAP_KEY not set (not needed for history; needed for 2026 NRT)")
    src = config.load("sources")["firms"]
    status = requests.get(f"https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/"
                          f"?MAP_KEY={key}", timeout=60).json()
    avail = requests.get(f"https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv/"
                         f"{key}/all", timeout=60).text
    lon0, lat0, lon1, lat1 = config.load("region")["punjab_bbox"]
    # A training-season date only (2024-11-01, validation season is allowed for API smoke)
    url = src["area_api_url"].format(key=key, source="VIIRS_NOAA20_SP",
                                     bbox=f"{lon0},{lat0},{lon1},{lat1}", days=1,
                                     date="2023-11-01")
    r = requests.get(url, timeout=120)
    lines = r.text.strip().splitlines()
    too_many = requests.get(src["area_api_url"].format(
        key=key, source="VIIRS_NOAA20_SP", bbox=f"{lon0},{lat0},{lon1},{lat1}", days=10,
        date="2023-11-01"), timeout=120)
    return {"_ok": r.ok and len(lines) > 1, "mapkey_status": status,
            "data_availability": avail.splitlines()[:20],
            "area_api_header": lines[0] if lines else None,
            "area_api_rows_2023_11_01": len(lines) - 1,
            "day_range_10_response": too_many.text[:200]}


if __name__ == "__main__":
    run_check("verify_firms_yearly", check_yearly, needs_gee=False)
    run_check("verify_firms_api", check_api, needs_gee=False)
