"""Extrapolate the measured GEE pilot cost to larger scopes.

Inputs (must exist; nothing is assumed if they don't):
  reports/metrics/gee_cost_pilot.json   measured EECU-seconds per export (one district-season)
  reports/metrics/verify_worldcover.json cropland cell counts per region and cell size

Model: cost of each per-cell export scales linearly with cropland area processed
(pixels read inside cells) and with the number of seasons. The 300/500/1000 m October S2
runs test the assumption that cost tracks area rather than cell count; the measured
ratio is applied when projecting other cell sizes.

Output: reports/metrics/gee_cost_extrapolation.json
"""

from __future__ import annotations

import json

from stubblecast import config
from stubblecast.metrics_io import write_metrics

COMMUNITY_EECU_H_PER_MONTH = 150
CONTRIBUTOR_EECU_H_PER_MONTH = 1000
N_SEASONS = len(config.load("seasons")["seasons"])
# Phase 2 burn-scar labels re-read Sentinel-2 over the same cells; projected here as one
# extra S2 pass. This is an assumption (flagged in the output), not a measurement.
LABEL_S2_PASSES = 1


def _load(name: str) -> dict | None:
    p = config.METRICS_DIR / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def main() -> None:
    pilot = _load("gee_cost_pilot")
    wc = _load("verify_worldcover")
    if not pilot or not pilot.get("all_completed") or not wc or wc.get("status") != "pass":
        write_metrics("gee_cost_extrapolation", {
            "status": "not_measured",
            "reason": "gee_cost_pilot.json and a passing verify_worldcover.json are required",
        })
        print("not measured")
        return

    cell = config.load("grid")["cell_size_m"]
    sizes = config.load("grid")["candidate_cell_sizes_m"]
    ex = pilot["exports"]
    pilot_cells = ex[f"grid_{cell}m"]["rows"]
    pilot_area = pilot_cells * (cell / 1000) ** 2
    per_km2 = {src: ex[f"{src}_full_{cell}m"]["eecu_seconds"] / pilot_area
               for src in ("s2", "s1", "era5")}
    per_km2["grid"] = ex[f"grid_{cell}m"]["eecu_seconds"] / pilot_area / N_SEASONS  # once only
    oct_ratio = {c: ex[f"s2_oct_{c}m"]["eecu_seconds"] / ex[f"s2_oct_{cell}m"]["eecu_seconds"]
                 for c in sizes}

    def scope_cost(area_km2: float, size_factor: float = 1.0) -> dict:
        s2 = per_km2["s2"] * area_km2 * N_SEASONS * size_factor
        s1 = per_km2["s1"] * area_km2 * N_SEASONS * size_factor
        era5 = per_km2["era5"] * area_km2 * N_SEASONS
        grid = per_km2["grid"] * area_km2 * N_SEASONS
        labels = s2 * LABEL_S2_PASSES
        total_s = s2 + s1 + era5 + grid + labels
        h = total_s / 3600
        return {"area_km2": round(area_km2, 1), "eecu_hours_features": round(
            (s2 + s1 + era5 + grid) / 3600, 2), "eecu_hours_labels_assumed": round(
            labels / 3600, 2), "eecu_hours_total": round(h, 2),
            "community_months": round(h / COMMUNITY_EECU_H_PER_MONTH, 2),
            "contributor_months": round(h / CONTRIBUTOR_EECU_H_PER_MONTH, 3)}

    def crop_area(region: str, c: int) -> float:
        return wc[region][f"cells_{c}m"]["cropland_ge_threshold"] * (c / 1000) ** 2

    pilots = config.load("region")["candidate_pilot_districts"]
    scopes = {}
    # Area is always measured at the main cell size; the measured S2 October cost ratio
    # (same district, same month, different cell size) carries the cell-size effect.
    for c in sizes:
        f = oct_ratio[c]
        scopes[f"{c}m"] = {
            "candidate_pilots": scope_cost(sum(crop_area(d, cell) for d in pilots), f),
            "punjab": scope_cost(crop_area("Punjab", cell), f),
            "punjab_haryana": scope_cost(crop_area("Punjab", cell)
                                         + crop_area("Haryana", cell), f),
        }
    write_metrics("gee_cost_extrapolation", {
        "status": "pass",
        "pilot_cropland_cells": pilot_cells, "pilot_cropland_area_km2": pilot_area,
        "measured_eecu_s_per_km2_season": per_km2,
        "s2_oct_cost_ratio_vs_main_cell": oct_ratio,
        "n_seasons": N_SEASONS, "scopes": scopes,
        "assumptions": [
            "cost linear in cropland area and number of seasons",
            f"burn-scar labels cost = {LABEL_S2_PASSES} extra S2 pass (not measured)",
            "issue frequency does not change GEE cost: features are computed per composite "
            "period / acquisition, and issue-date windows are assembled offline",
            "no re-runs; budget headroom for failures and iteration is not included",
        ],
        "quota_eecu_h_per_month": {"community": COMMUNITY_EECU_H_PER_MONTH,
                                   "contributor": CONTRIBUTOR_EECU_H_PER_MONTH},
    })
    print(json.dumps(scopes, indent=1))


if __name__ == "__main__":
    main()
