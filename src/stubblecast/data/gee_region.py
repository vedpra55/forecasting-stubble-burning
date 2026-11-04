"""Earth Engine geometry helpers built from the local district polygons."""

from __future__ import annotations

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from stubblecast.data import boundaries

# Simplification tolerance in degrees (~50 m) keeps request payloads small without
# changing district area by more than a fraction of a percent.
SIMPLIFY_DEG = 0.0005


def district_shape(state: str, district: str):
    fc = boundaries.districts_for_state(state)
    for f in fc["features"]:
        if f["properties"]["district"] == district:
            return shape(f["geometry"])
    raise KeyError(f"{district} not found in {state}")


def state_shape(state: str):
    fc = boundaries.districts_for_state(state)
    return unary_union([shape(f["geometry"]) for f in fc["features"]])


def to_ee(geom, simplify: float = SIMPLIFY_DEG):
    import ee

    g = geom.simplify(simplify, preserve_topology=True)
    return ee.Geometry(mapping(g), proj="EPSG:4326", geodesic=False)
