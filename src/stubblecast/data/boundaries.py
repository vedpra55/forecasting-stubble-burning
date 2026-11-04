"""District boundaries for the study states.

Source: geoBoundaries gbOpen IND ADM2 (districts, year represented 2021, built from
lgdirectory.gov.in; ODbL 1.0), commit 9469f09. ADM2 features carry no state attribute,
so each district is assigned to the ADM1 state that contains its representative point.
The same polygons are pushed to Earth Engine as geometries, so FIRMS clipping and GEE
exports use one boundary source.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests
from shapely.geometry import mapping, shape
from shapely.strtree import STRtree

from stubblecast.config import DATA_DIR

GB_COMMIT = "9469f09"
GB_URL = (
    "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/"
    "{commit}/releaseData/gbOpen/IND/{adm}/geoBoundaries-IND-{adm}.geojson"
)
RAW_DIR = DATA_DIR / "raw" / "boundaries"
OUT_DIR = DATA_DIR / "interim" / "boundaries"

# geoBoundaries ADM1 names use diacritics.
STATE_NAMES = {"Punjab": "Punjab", "Haryana": "Haryāna"}


def download(adm: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"geoBoundaries-IND-{adm}.geojson"
    if path.exists() and path.stat().st_size > 10_000:
        return path
    r = requests.get(GB_URL.format(commit=GB_COMMIT, adm=adm), timeout=600)
    r.raise_for_status()
    path.write_bytes(r.content)
    return path


def districts_for_state(state: str) -> dict:
    """Return a GeoJSON FeatureCollection of the districts of `state` (cached)."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{state.lower()}_districts.geojson"
    if out.exists():
        return json.loads(out.read_text())

    adm1 = json.loads(download("ADM1").read_text())
    adm2 = json.loads(download("ADM2").read_text())
    gb_name = STATE_NAMES[state]
    state_geom = next(
        shape(f["geometry"]) for f in adm1["features"] if f["properties"]["shapeName"] == gb_name
    )
    geoms = [shape(f["geometry"]) for f in adm2["features"]]
    tree = STRtree(geoms)
    feats = []
    for idx in tree.query(state_geom):
        g = geoms[idx]
        if state_geom.contains(g.representative_point()):
            props = adm2["features"][idx]["properties"]
            feats.append({
                "type": "Feature",
                "properties": {"district": props["shapeName"], "shapeID": props["shapeID"],
                               "state": state},
                "geometry": mapping(g),
            })
    feats.sort(key=lambda f: f["properties"]["district"])
    fc = {"type": "FeatureCollection", "features": feats}
    out.write_text(json.dumps(fc))
    return fc
