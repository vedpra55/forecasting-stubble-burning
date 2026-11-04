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

**Outcome (owner, 2026-11-04): approved. NOAA-20 only for active-fire labels.** Recorded in `configs/task.yaml` (`label_sensor`). S-NPP and NOAA-21 may still be used for sensitivity analysis and for estimating label recall in Phase 2, never as the primary label.

---

## D-002 — Phase 1 gate decisions (open; see `docs/phase_reports/phase_1.md` §6)

Pilot districts, cell size, forecast horizon, issue frequency.
Each has a recommendation and trade-offs in the phase report.

**Outcome (owner, 2026-11-04): approved as recommended.**
- **Pilot districts:** Sangrur and Tarn Taran for train/validation; Bathinda as the spatial holdout, never used in training (`configs/region.yaml`).
- **Cell size:** 500 m (`configs/grid.yaml`). Revisit only if the measured GEE cost difference between cell sizes says so; the cost pilot is still pending (see the phase report §4).
- **Horizon:** 7 days, with 3 days as a secondary result (`configs/task.yaml`).
- **Issue dates:** daily for validation and test; every 3rd season day for training (`configs/task.yaml`).

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

**Outcome (owner, 2026-11-04): approved.** Add a geostationary fire product in Phase 2, scoped to measuring polar-orbiter miss rates per season. It is a measurement of label quality, not a label for individual 500 m cells: geostationary pixels are 12–24 km² over Punjab. Which satellite to use is D-005.

---

## D-005: Which geostationary fire product for measuring polar-orbiter miss rates? (open)

**Context.**
- D-004 needs an instrument that observes Punjab through the afternoon, so we can measure, per season, what share of fire activity happens outside the ~13:00–14:45 IST VIIRS window.
- View geometry over Punjab (30.8°N, 75.4°E), from first-order geometry in `reports/metrics/geostationary_view_geometry.json`:

| Satellite (sub-satellite lon) | View zenith angle | ~3.9 µm pixel at Punjab | Repeat |
|---|---|---|---|
| INSAT-3DR Imager (74.0°E) | 35.9° | 4.1 × 5.1 km (20.9 km²) | 30 min |
| INSAT-3DS Imager (82.0°E) | 36.6° | 4.1 × 5.1 km (21.2 km²) | 30 min |
| Meteosat-9 SEVIRI, IODC (45.5°E, since Jun 2022) | 48.4° | 3.2 × 4.8 km (15.0 km²) | 15 min |
| Meteosat-8 SEVIRI, IODC (41.5°E, until Jun 2022) | 51.3° | 3.2 × 5.1 km (16.1 km²) | 15 min |
| GK2A AMI (128.2°E) | 66.7° | 2.2 × 5.5 km (12.2 km²) | 10 min |
| Himawari-9 AHI (140.7°E) | 77.5° | 2.3 × 10.4 km (23.5 km²) | 10 min |

- **Best *view*:** the INSAT satellites, which see Punjab most directly (lowest view angle: shortest path through haze and smoke, least parallax). GK2A has the smallest pixel area, but sees Punjab at a steep 67° angle: about 2.5× the vertical atmospheric path (1/cos 66.7°) and a strongly stretched footprint.
- **What matters as much as the view is whether a fire product and an archive exist for 2019–2026.** Checked 2026-11-04:
  - **Meteosat IODC (SEVIRI).**
    - LSA SAF publishes an FRP-PIXEL fire list for the full IODC disk (file names `..._IODC-Disk_YYYYMMDDhhmm`). It is listed every 15 min for 2017 through 2026; I confirmed a complete day of file names for 1 Nov 2019 and 1 Nov 2023.
    - The algorithm is published and validated against MODIS elsewhere (Wooster et al. 2015, ACP).
    - It is the instrument the ISRO study used for exactly this question.
    - Status is "demonstration", best effort. Access needs free LSA SAF registration, and file *contents* over Punjab are not yet checked.
  - **INSAT-3DR / 3DS.**
    - MOSDAC lists an operational active-fire product for INSAT-3DS (`3SIMG_L2P_FIR`, KML points) and describes one for INSAT-3DR.
    - I found no published validation for crop-residue fires.
    - Archive access for 2019–2024 through MOSDAC is unverified.
    - The record changes satellite (3DR → 3DS from 2024) at a different position.
  - **GK2A.**
    - Open L1B on AWS (`noaa-gk2a-pds`) starts only in **Feb 2023**, so it misses 2019–2022.
    - No ready-made fire product was found; we would need to write our own detection algorithm. Jethva (2026) did this with NMSC-sourced data for 2019–2025.
  - **Himawari.** The JAXA wildfire product covers only 80°E–160°W (README), which excludes Punjab (74–77°E), and the view angle is 77.5°. Rejected.

**Options.** (1) Meteosat IODC SEVIRI FRP-PIXEL; (2) INSAT-3DR/3DS MOSDAC fire product; (3) GK2A with our own algorithm.

**Recommendation: option 1, Meteosat IODC SEVIRI FRP-PIXEL (LSA SAF)**, conditional on a one-file check that it contains Punjab detections. Keep INSAT-3DR as a cross-check if the MOSDAC archive turns out to be accessible.

**Why.**
- It is the only candidate with all three of: a published, validated fire algorithm; one consistent 15-minute product covering every season 2019–2026; and an archive we can confirm exists.
- INSAT's better view does not outweigh an unvalidated product, a satellite change mid-record and an unverified archive.
- GK2A's open archive misses half the seasons.

**Known confound to handle in Phase 2.**
- The IODC satellite switched from Meteosat-8 to Meteosat-9 in June 2022, between the 2021 and 2022 seasons. That is exactly when the reported diurnal shift begins.
- Meteosat-9 sees Punjab slightly better (48.4° vs 51.3° view angle), so a jump in SEVIRI detections in 2022 could be partly instrumental.
- **Check:** compare, per season, SEVIRI detections within ±30 min of the VIIRS overpass against VIIRS detections. If that ratio is stable across 2021→2022, the switch is not driving the trend.

**Owner action needed:** register at https://mokey.lsasvcs.ipma.pt/auth/signup (free) and provide the credentials as environment secrets `LSASAF_USER` / `LSASAF_PASSWORD`.

**Outcome:** _pending owner decision_
