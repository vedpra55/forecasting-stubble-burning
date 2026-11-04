"""Compare district boundaries: geoBoundaries (local, used) vs FAO GAUL 2025 (GEE).

Punjab has 23 districts since Malerkotla was carved out of Sangrur in 2021. This check
reports what each source contains so the boundary vintage is documented.
"""

from __future__ import annotations

from _common import run_check

from stubblecast import config
from stubblecast.data import boundaries


def check() -> dict:
    import ee

    gb = boundaries.districts_for_state("Punjab")
    gb_names = sorted(f["properties"]["district"] for f in gb["features"])
    coll = ee.FeatureCollection(config.load("region")["boundaries"]["gee_collection"])
    first = coll.first()
    props = first.propertyNames().getInfo()
    # find a level-1 name field and a level-2 name field without assuming exact names
    l1 = next((p for p in props if p.lower() in ("gaul1_name", "adm1_name")), None)
    l2 = next((p for p in props if p.lower() in ("gaul2_name", "adm2_name")), None)
    gaul_names = None
    if l1 and l2:
        gaul_names = sorted(coll.filter(ee.Filter.eq(l1, "Punjab"))
                            .filter(ee.Filter.stringContains(
                                next(p for p in props if p.lower() in
                                     ("gaul0_name", "adm0_name")), "India"))
                            .aggregate_array(l2).getInfo())
    return {
        "geoboundaries_commit": boundaries.GB_COMMIT,
        "geoboundaries_punjab_n": len(gb_names), "geoboundaries_punjab": gb_names,
        "gaul_collection": config.load("region")["boundaries"]["gee_collection"],
        "gaul_property_names": props, "gaul_punjab_n": len(gaul_names) if gaul_names else None,
        "gaul_punjab": gaul_names,
        "malerkotla_in_geoboundaries": any("Maler" in n for n in gb_names),
        "malerkotla_in_gaul": any("Maler" in n for n in gaul_names) if gaul_names else None,
    }


if __name__ == "__main__":
    run_check("verify_boundaries", check)
