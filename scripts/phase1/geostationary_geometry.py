"""View geometry of candidate geostationary imagers over Punjab (D-004).

For each satellite: great-circle angle to the target, satellite view zenith angle (VZA),
slant range, and an approximate pixel footprint at the target. The footprint uses the
standard first-order geometry for a fixed angular sampling:
    tangential size ~ nadir * (slant / H)
    radial size     ~ nadir * (slant / H) / cos(VZA)
where H is the orbit altitude above the sub-satellite point. This ignores Earth curvature
within a pixel and instrument PSF, so treat it as a ranking aid, not a product spec.
"""

from __future__ import annotations

import math

from stubblecast import config
from stubblecast.metrics_io import write_metrics

R_EARTH = 6378.137   # km, equatorial
R_GEO = 42164.0      # km, geostationary orbit radius
H = R_GEO - R_EARTH  # km, altitude above sub-satellite point


def geometry(lat: float, lon: float, sub_lon: float) -> dict:
    phi, dlam = math.radians(lat), math.radians(lon - sub_lon)
    cos_c = math.cos(phi) * math.cos(dlam)          # great-circle angle to sub-sat point
    c = math.acos(cos_c)
    slant = math.sqrt(R_EARTH**2 + R_GEO**2 - 2 * R_EARTH * R_GEO * cos_c)
    # VZA: angle at the target between local vertical and the line to the satellite
    vza = math.degrees(math.asin(R_GEO * math.sin(c) / slant))
    return {"great_circle_deg": round(math.degrees(c), 1), "vza_deg": round(vza, 1),
            "slant_km": round(slant), "visible": vza < 90}


def main() -> None:
    g = config.load("sources")["geostationary"]
    tgt = g["target_point"]
    out = {}
    for key, s in g["satellites"].items():
        geo = geometry(tgt["lat"], tgt["lon"], s["sub_lon"])
        scale = geo["slant_km"] / H
        tang = s["ir_nadir_km"] * scale
        rad = tang / math.cos(math.radians(geo["vza_deg"]))
        out[key] = {**s, **geo,
                    "ir_pixel_tangential_km": round(tang, 1),
                    "ir_pixel_radial_km": round(rad, 1),
                    "ir_pixel_area_km2": round(tang * rad, 1)}
    ranked = sorted(out, key=lambda k: out[k]["ir_pixel_area_km2"])
    write_metrics("geostationary_view_geometry", {
        "target": tgt, "satellites": out, "ranked_by_pixel_area": ranked,
        "note": "first-order geometry; see script docstring",
    })
    for k in ranked:
        v = out[k]
        print(f"{v['label']:42s} VZA {v['vza_deg']:5.1f}  pixel ~{v['ir_pixel_tangential_km']}"
              f" x {v['ir_pixel_radial_km']} km  ({v['ir_pixel_area_km2']} km2), "
              f"every {v['repeat_min']} min")


if __name__ == "__main__":
    main()
