# Decisions log

Format: context → options → recommendation → why → **outcome** (filled in by the owner).
Numbers cited here come from `reports/metrics/` (file named in brackets).

---

## D-000 — Phase 1 setup choices (owner-decided, 2026-11-04)

- **Earth Engine auth:** service account on project `stubblecast`, key kept outside the repo.
  **Outcome:** decided by owner.
- **Test seasons in EDA:** EDA uses 2019–2024 only; 2025 and 2026 are not read.
  **Outcome:** decided by owner. The FIRMS 2025/2026 yearly files were checked only by HTTP HEAD (`verify_firms_yearly.json`).

---

## D-001 — Which fire sensor(s) define the active-fire labels? (open)

**Context.**
- NOAA ended S-NPP science-data delivery on 2026-11-02, so the 2026 test season has S-NPP for only part of the season.
- NOAA-21 starts 2023-03 and has no FIRMS yearly country files (`verify_firms_yearly.json`).
- NOAA-20 runs continuously from 2018-04.
- The two VIIRS sensors pass Punjab ~50 min apart (`firms_eda.json → viirs_agreement_vs_cell_size`). Because the fires are short, they see largely *different* fires: at 500 m only 3.5–6.8% of NOAA-20 cell-days are also detected by S-NPP on the same day.
- So the union of sensors finds many more burned cells than either one alone, and the number of sensors changes how many positives there are.

**Options.**
1. **NOAA-20 only**, 2019–2026. The sensor is constant across all seasons, but each cell's fire is seen only once a day.
2. **Union of S-NPP + NOAA-20** for 2019–2026. More positives, but the 2026 season loses S-NPP partway through, which is a train/test shift.
3. **Union of whichever VIIRS are available** (adds NOAA-21 from 2023). Most positives, but the label definition changes in 2023 and again in 2026.

**Recommendation: option 1 (NOAA-20 only) as the primary label.** S-NPP and NOAA-21 are kept as a sensitivity analysis, and as extra "fire seen by any sensor" information to use in Phase 2 when estimating label recall.

**Why.**
- A label whose detection rate changes between seasons makes season-based evaluation misleading: a model could look better or worse in 2026 just because a sensor disappeared.
- Constant-sensor labels keep train and test comparable.
- The cost is fewer positives. That's acceptable because Phase 2 adds burn-scar labels, which do not depend on overpass timing.

**Outcome:** _pending owner decision_

---

## D-002 — Phase 1 gate decisions (open; see `docs/phase_reports/phase_1.md` §6)

Pilot districts, cell size, forecast horizon, issue frequency.
Each has a recommendation and trade-offs in the phase report.

**Outcome:** _pending owner decision_

---

## D-003 — District boundary source (proposed)

**Context.**
- We need district polygons both for FIRMS clipping (done locally) and for GEE exports.
- geoBoundaries IND ADM2 (commit 9469f09) gives **22** Punjab districts. Malerkotla (created 2021 from Sangrur) is missing, and so is Haryana's Charkhi Dadri (created 2016).
- FAO GAUL 2025 level 2 is in the GEE catalog but is not checked yet (`verify_boundaries.json` is skipped until GEE access works).

**Recommendation.** Use one boundary source everywhere, so FIRMS counts and GEE features line up. Use GAUL 2025 if `verify_boundaries.py` shows it has the current 23 Punjab districts; otherwise keep geoBoundaries and document that "Sangrur" includes Malerkotla.

**Why.** Districts are reporting and spatial-holdout units, not model inputs. A slightly old boundary only matters if we report Malerkotla separately.

**Outcome:** _pending (needs GEE)_

---

## D-004 — Label-validity risk from late-afternoon burning (flag for Phase 2)

**Context.**
- Two geostationary studies report that burning shifted to late afternoon from about 2022, after the ~13:30 polar overpass:
  - Jethva 2026, Remote Sensing 18:1506
  - an ISRO SEVIRI study, known only from press coverage
- NOAA-20 in-season detections in Punjab fell from 77,849 (2020) to 10,384 (2024) (`firms_eda.json`).
- Polar-orbiter data alone can't tell how much of that drop is less burning and how much is fewer *detections*. Our detection-time check in the 13:00–14:45 window is inconclusive (`firms_eda.json → detection_time_drift`).

**Implication.**
- The 2024 validation season and the 2025–2026 test seasons may have systematically lower label recall than 2019–2021.
- Phase 2 must:
  1. build Sentinel-2 burn-scar labels, which don't depend on time of day;
  2. measure active-fire vs scar agreement *per season*;
  3. consider a geostationary fire product as an extra label source.

**Outcome:** _for discussion at the Phase 1 gate_
