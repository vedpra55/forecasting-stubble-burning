"""NASA FIRMS active-fire detections.

History comes from the public yearly per-country CSVs (no MAP_KEY needed), which
are Collection 2 for VIIRS (`version` == "2") and Collection 6.1 for MODIS.
Each yearly India file is downloaded once, pre-filtered to the study bounding box,
and cached as Parquet.

VIIRS `confidence` is categorical (l / n / h); MODIS `confidence` is 0-100.
They are never mixed: `confidence_class` is only defined for VIIRS (CLAUDE.md pitfall).
FIRMS `type`: 0 presumed vegetation fire, 1 active volcano, 2 other static land source,
3 offshore.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import requests
from shapely import contains_xy
from shapely.geometry import shape
from shapely.ops import unary_union

from stubblecast import config

RAW_DIR = config.DATA_DIR / "raw" / "firms"
VIIRS_CONFIDENCE = {"l": "low", "n": "nominal", "h": "high"}


def yearly_url(sensor: str, year: int, country: str = "India") -> str:
    src = config.load("sources")["firms"]
    folder = src["sensors"][sensor]["folder"]
    return src["yearly_country_url"].format(folder=folder, year=year, country=country)


def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    return dest


def load_year(sensor: str, year: int, allowed_years: list[int] | None = None) -> pd.DataFrame:
    """Return detections for one sensor-year inside the study bbox (cached Parquet).

    `allowed_years` guards against accidentally reading test seasons.
    """
    if allowed_years is not None and year not in allowed_years:
        raise PermissionError(f"Year {year} is not in the allowed set {allowed_years}")
    cache = RAW_DIR / f"{sensor}_{year}_bbox.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    csv_path = RAW_DIR / "csv" / f"{sensor}_{year}_India.csv"
    if not csv_path.exists():
        _download(yearly_url(sensor, year), csv_path)
    df = pd.read_csv(csv_path, dtype={"acq_time": str, "confidence": str, "version": str})
    lon0, lat0, lon1, lat1 = config.load("region")["prefilter_bbox"]
    df = df[df.longitude.between(lon0, lon1) & df.latitude.between(lat0, lat1)].copy()
    df = normalise(df, sensor)
    df.to_parquet(cache, index=False)
    return df


def normalise(df: pd.DataFrame, sensor: str) -> pd.DataFrame:
    """Add typed columns: acq_date (date), acq_hour_utc, sensor, confidence fields."""
    df = df.copy()
    df["acq_date"] = pd.to_datetime(df["acq_date"]).dt.date
    t = df["acq_time"].astype(str).str.zfill(4)
    df["acq_hour_utc"] = t.str[:2].astype(int) + t.str[2:].astype(int) / 60
    df["sensor"] = sensor
    instrument = config.load("sources")["firms"]["sensors"][sensor]["instrument"]
    if instrument == "VIIRS":
        bad = set(df["confidence"].unique()) - set(VIIRS_CONFIDENCE)
        if bad:
            raise ValueError(f"Unexpected VIIRS confidence values: {bad}")
        df["confidence_class"] = df["confidence"].map(VIIRS_CONFIDENCE)
        df["confidence_pct"] = pd.NA
    else:
        df["confidence_pct"] = pd.to_numeric(df["confidence"], errors="raise")
        if not df["confidence_pct"].between(0, 100).all():
            raise ValueError("MODIS confidence outside 0-100")
        df["confidence_class"] = pd.NA
    return df


def in_season(d: date, season: int, start_md: str, end_md: str) -> bool:
    """True if date `d` falls in the season window of year `season` (inclusive)."""
    m0, d0 = map(int, start_md.split("-"))
    m1, d1 = map(int, end_md.split("-"))
    return date(season, m0, d0) <= d <= date(season, m1, d1)


def season_filter(df: pd.DataFrame, season: int) -> pd.DataFrame:
    cfg = config.load("seasons")
    mask = df["acq_date"].map(lambda d: in_season(d, season, cfg["season_start"],
                                                   cfg["season_end"]))
    out = df[mask].copy()
    out["season"] = season
    return out


def assign_districts(df: pd.DataFrame, districts_fc: dict) -> pd.DataFrame:
    """Add a `district` column (None outside all polygons) by point-in-polygon."""
    df = df.copy()
    df["district"] = None
    lon, lat = df["longitude"].to_numpy(), df["latitude"].to_numpy()
    for f in districts_fc["features"]:
        inside = contains_xy(shape(f["geometry"]), lon, lat)
        df.loc[inside, "district"] = f["properties"]["district"]
    return df


def state_union(districts_fc: dict):
    return unary_union([shape(f["geometry"]) for f in districts_fc["features"]])
