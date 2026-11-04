# Phase 1 report: Scoping and data audit

**Status: partially complete. Stopped at the review gate.**

- **Done:**
  - repo skeleton
  - FIRMS audit and EDA (2019–2024)
  - literature review
  - every Earth Engine check script and the cost-pilot pipeline, written
- **Not done (blocked):**
  - every Earth Engine check
  - the measured GEE cost

  Earth Engine rejected the project with *"Project stubblecast is not registered to use Earth Engine"*. The service-account key itself is accepted. Until the project is registered for noncommercial use, `verify_s2/s1/worldcover/era5/boundaries.json` all have `"status": "skipped"`. **No cost estimate is given below, because none has been measured.**

  Once the project is registered, one command finishes the phase:

  ```bash
  uv run python scripts/phase1/run_all.py
  ```

  Sections 4 and 6 would then need updating with the measured numbers.

Every number in this report comes from a JSON file under `reports/metrics/`; the file is named next to each number.

---

## 1. What was built

| Item | Where | What it does / verifies |
|---|---|---|
| Environment | `pyproject.toml`, `uv.lock` | Python ≥3.11, uv-pinned; ruff and pytest (17 tests pass) |
| Configs | `configs/*.yaml` | Region, grid, seasons and splits, dataset IDs. No dataset IDs are hard-coded in code |
| Secrets template | `.env.example` | `GEE_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS` or `GEE_SERVICE_ACCOUNT_KEY`, `FIRMS_MAP_KEY`, `OPENAQ_API_KEY` |
| Metrics writer | `src/stubblecast/metrics_io.py` | Every JSON records timestamp, git SHA, script and parameters |
| GEE auth | `src/stubblecast/gee.py` | Service-account auth; fails loudly if registration or credentials are missing |
| Boundaries | `src/stubblecast/data/boundaries.py` | geoBoundaries IND ADM2 (commit 9469f09); assigns each district to a state by representative point |
| FIRMS loader | `src/stubblecast/data/firms.py` | Public yearly India CSVs, cached as bbox-filtered Parquet. Raises on any VIIRS confidence value other than l/n/h, and on MODIS values outside 0–100. Raises `PermissionError` if a year outside the allowed set (e.g. a test season) is requested |
| `verify_firms.py` | → `verify_firms_yearly.json` (**pass**), `verify_firms_api.json` (skipped: no `FIRMS_MAP_KEY`) | Schema, versions, confidence scales and `type` values for each sensor-year; 2025/26 checked by HEAD request only |
| `verify_openaq.py` | → `verify_openaq.json` (skipped: no key; Phase 8 only) | v3 `/locations` near Delhi and `/sensors/{id}/days` |
| `verify_s2.py` | → `verify_s2.json` (**skipped: GEE**) | S2 bands; Cloud Score+ linking; clear-pixel fraction per acquisition date over Sangrur, 2023 season |
| `verify_s1.py` | → `verify_s1.json` (**skipped: GEE**) | IW VV+VH; acquisitions, platforms and revisit gaps per season 2019–2024 (measures the effect of the Sentinel-1B loss) |
| `verify_worldcover.py` | → `verify_worldcover.json` (**skipped: GEE**) | Class 40 fraction; number of cropland cells at 300/500/1000 m for the candidate pilots, Punjab and Haryana (the denominator for class imbalance) |
| `verify_era5.py` | → `verify_era5.json` (**skipped: GEE**) | Band names, sample values, latency; derived RH and wind speed |
| `verify_boundaries.py` | → `verify_boundaries.json` (**skipped: GEE**) | geoBoundaries vs FAO GAUL 2025 district lists |
| `firms_eda.py` | → `firms_eda.json`, `firms_daily_counts_punjab_noaa20.csv`, 6 figures | Section 3 |
| `gee_cost_pilot.py` | → `gee_cost_pilot.json` (**not run**) | Section 4 |
| `cost_extrapolate.py` | → `gee_cost_extrapolation.json` (`not_measured`) | Section 4 |
| Literature review | `docs/literature_review.md` | Section 5 |
| Decision log / test log | `docs/DECISIONS.md`, `docs/TEST_LOG.md` | D-001…D-004; one test-log entry (HEAD-only check) |

## 2. Corrections to CLAUDE.md / PLAN.md (verified 2026-11-04)

1. **VIIRS S-NPP is retired.** NOAA ended S-NPP science-data delivery on 2026-11-02, so the 2026 test season has S-NPP data for only part of the season. This leads to the NOAA-20-only label recommendation in D-001.
2. **MODIS Terra and Aqua are being phased out** from late 2026 into 2027. CLAUDE.md already avoids MODIS, which is right. In our Punjab data, 95% of in-season MODIS detections come from Aqua (65,709 vs 3,766 Terra; `firms_eda.json`).
3. **FIRMS history doesn't need the archive tool or a MAP_KEY.** Public yearly country CSVs exist for S-NPP (`viirs-snpp`), NOAA-20 (filed as `viirs-jpss1`) and MODIS. They are Collection 2 (`version = 2`) and include `type`, which flags static industrial sources (`verify_firms_yearly.json`).
   - **There are no 2026 yearly files yet, and NOAA-21 has no yearly files at all** (HEAD returns 404).
   - So the 2026 test season (and any NOAA-21 use) needs the Area API (5-day maximum per call) or the archive tool, which means a MAP_KEY is needed before Phase 6.
4. **VIIRS and MODIS confidence fields really are on different scales.** VIIRS uses `l/n/h` and MODIS uses 0–100. The loader enforces this and tests cover it.
5. **ERA5-Land daily has no relative-humidity band.** RH is derived from `dewpoint_temperature_2m` and `temperature_2m` (`src/stubblecast/features/weather.py`, tested). Precipitation is `total_precipitation_sum`, in metres.
6. **Sentinel-1 coverage changes across seasons.** S-1B failed on 2021-12-23, and S-1C opened to users in March 2025. `verify_s1.py` will measure the change in revisit.
7. **S2 cloud masking:** QA60 is masked from Jan 2022 to Feb 2024 in the GEE collection, so use Cloud Score+ `cs_cdf`. Threshold 0.60 is set in config; the catalog suggests 0.50–0.65.
8. **WorldCover v200 is a single 2021 map**, so the cropland mask is static.
9. **The EE quota is now enforced monthly** (since 2026-04-27). Community tier is 150 EECU-h per month. Contributor tier is 1,000 EECU-h with a billing account, and noncommercial use is not charged.
10. **The PLAN.md window for features should start 60 days before 25 Sep**, i.e. 27 Jul. The cost pilot uses 27 Jul – 5 Dec.

## 3. FIRMS EDA findings (Punjab, 2019–2024, VIIRS NOAA-20, `type = 0`, 25 Sep – 5 Dec)

Source: `reports/metrics/firms_eda.json`. Figures are in `reports/figures/firms_*.png`.

**3.1 Timing: the expected late-Oct to mid-Nov peak is there.**

| Season | Detections | Peak day | 10% / 50% / 90% cumulative date | Days from 10% to 90% |
|---|---|---|---|---|
| 2019 | 44,808 | 4 Nov | 23 Oct / 3 Nov / 10 Nov | 18 |
| 2020 | 77,849 | 5 Nov | 20 Oct / 3 Nov / 11 Nov | 22 |
| 2021 | 77,412 | 7 Nov | 28 Oct / 7 Nov / 14 Nov | 17 |
| 2022 | 49,949 | 5 Nov | 24 Oct / 4 Nov / 13 Nov | 20 |
| 2023 | 33,448 | 7 Nov | 27 Oct / 6 Nov / 17 Nov | 21 |
| 2024 | 10,384 | 18 Nov (7-day-centred peak: 6 Nov) | 21 Oct / 7 Nov / 20 Nov | 30 |

- **The year-to-year shift in median timing is small at state level:** 4 days (day 39–43 of the season).
- **Spread within a season is much larger:** 17–30 days between the 10% and 90% dates.
- **Districts differ more than years do.** The median 50%-date (day of season) is about 29 for Amritsar, about 34 for Tarn Taran and Gurdaspur, 41 for Sangrur, and 45–46.5 for Moga, Muktsar and Fazilka.
  - So Majha (north-west) burns about 1.5–2.5 weeks before south-west Malwa.
  - This supports CLAUDE.md's preference for crop-stage features over calendar dates: a single calendar feature would mix these regimes.
- **A few days inside the peak have near-zero detections:** 1–2 Nov 2019, 8 Nov 2022, 10–11 Nov 2023, and eight days in 2024 (`low_days_in_core`). These are candidates for cloud/smoke cover or poor view geometry, to be checked against ERA5 and S2 cloud data in Phase 2/3. They matter because a "no detection" day isn't a "no fire" day.

**3.2 Volume is falling fast, and that may not all be real.**
- **NOAA-20 detections fell 87% from 2020 to 2024** (77,849 → 10,384). S-NPP and MODIS show the same direction.
- **The paddy season's share of each calendar year's detections fell** from 0.81–0.82 (2020–21) to 0.32 (2024).
- **The geostationary literature (§5) reports burning moved to late afternoon from 2022 on**, after the ~13:30 polar overpass.
  - Our own check of detection times inside the overpass window is **inconclusive**. In 2024 the median detection hour moved slightly later for NOAA-20 (13.72 h) but not for S-NPP (13.63 h); see `detection_time_drift`.
  - The window is too narrow (about 13:00–14:45 IST) to see a shift to 16:00–17:00.
- **Day vs night:** 99.84% of in-season VIIRS detections are daytime. Fires are almost never burning at the ~01:30 night pass.
- **Implication:**
  - 2024 (validation) and 2025–26 (test) labels may have lower recall than 2019–21 labels.
  - Phase 2's burn-scar labels and a per-season comparison of fire vs scar labels are essential, not optional (D-004).
  - Without them, a fall in recall@k could be a labelling artefact.

**3.3 Districts: concentrated but not extreme.**
- The 22 districts in this boundary set are listed in `firms_eda.json → districts_noaa20`.
- Sangrur has 13.2% of all 2019–2024 detections, and the top five districts have 43.7%.
- Between-season variation (CV) is 0.44–0.76 per district.
- Pathankot, Rupnagar, SAS Nagar, SBS Nagar and Hoshiarpur together have under 2.0%.

**3.4 The two VIIRS sensors see different fires** (`viirs_agreement_vs_cell_size`).
- NOAA-20 and S-NPP pass Punjab a median 50 minutes apart (IQR 49–51 min).
- Of NOAA-20 500 m cell-days, only **3.5–6.8% are also detected by S-NPP the same day**. Allowing ±1 day raises this to 6.4–12.9% (`viirs_sensor_agreement_500m`).
- Agreement rises steadily with cell size. In 2021 it is 4.4% at 375 m, 6.8% at 500 m, 15.7% at 1 km, 34.1% at 2 km and 65.2% at 5 km.
- **Interpretation:** most disagreement is not a location error. Individual field fires are shorter than the 50-minute gap, so each overpass samples a different subset of fields.
  - This matches Liu et al. (2020), which reports fires lasting about 30 minutes.
  - It means **active-fire labels at cell level have low recall**: a burned field is often never seen by any polar orbiter.
  - This is the strongest data-driven argument for the fused (fire + burn-scar) label in Phase 2.

**3.5 Persistent hot spots (kilns, industry) barely matter in season.**
- 126 cells at 500 m have off-season detections (outside Apr–May and 15 Sep – 15 Dec) in at least 3 years.
- They hold only 0.045% of in-season type-0 detections (`persistent_hotspots`).
- FIRMS flags 70 in-season NOAA-20 detections as `type = 2` (static land source), across 8 cells, all of which our persistence rule also flags.
- We will still mask them in Phase 2, but they are not a major source of noise for the paddy season.

**3.6 Class balance and label structure** (`cells_noaa20`; denominator = **all** land cells in Punjab, so these are lower bounds on the positive rate until WorldCover cropland counts arrive).

| Cell size | Burned cells per season (2019–2024) | 7-day positives per issue date (season mean) | 3-day positives per issue date (season mean) | Mean 7-day positive rate vs all land cells |
|---|---|---|---|---|
| 300 m | 9,983 – 68,881 | 1,083 – 7,883 | 440 – 3,258 | 0.19% – 1.41% |
| 500 m | 9,306 – 56,384 | 1,031 – 7,098 | 421 – 3,029 | 0.51% – 3.51% |
| 1 km | 7,710 – 30,177 | 932 – 5,238 | 389 – 2,479 | 1.85% – 10.37% |

- **At 500 m, most burned cells are detected on only one day per season.** The median is 1 day, and 4.9–24.5% are detected on 2+ days. In practice a cell burns once, so modelling should treat a cell as "done" after it burns (a Phase 2/4 design point).
- **Burning in the previous season is a weakening signal.** At 500 m, P(burn | burned last season) fell from 0.44 (2019→20) to 0.08 (2023→24). Baseline 1 (prior-season history) will be weaker for recent seasons, especially if detection recall is falling.

## 4. GEE cost: **not measured**

`gee_cost_pilot.py` is written and lint-clean but has not run, because the project is not registered. What it will measure:

- **District and season:** Sangrur, 2023 (a train season), window 27 Jul – 5 Dec.
- **Grids:** 300, 500 and 1000 m cropland grids, cells with at least 50% WorldCover class 40.
- **Exports**, each a separate `Export.table.toAsset` task writing compact per-cell tables (no imagery downloaded):
  - S2 5-day Cloud-Score+-masked NDVI/NBR/NDMI composites
  - S1 VV/VH per acquisition
  - ERA5 daily weather at cell centroids
  - S2 for October only at 300/500/1000 m, to show how cost scales with cell size
- **Cost reading:** EECU-seconds come from each task's status (`batch_eecu_usage_seconds`) or operation metadata (`batchEecuUsageSeconds`). The exact field name will be confirmed from the live response.
- **Extrapolation:** `cost_extrapolate.py` scales linearly by cropland area and season count (8 seasons) to three scopes: the candidate pilots, all of Punjab, and Punjab + Haryana. It reports both EECU-hours and months of Community quota.
- **Assumption, labelled in its output:** burn-scar labels are costed as one extra S2 pass.

I deliberately give **no estimate** here. The only figure I could give would be a guess, and rule 3 forbids that.

**Design point, true by construction (no measurement needed):** issue frequency (daily vs every 3 days) does not change GEE cost. Features are exported once per composite period or acquisition, and each issue date's window is assembled offline from those tables.

## 5. Literature gap (details in `docs/literature_review.md`)

- **Existing work covers:**
  - seasonal regional totals predicted from September NDVI (Jethva 2022)
  - 1–3-day gridded deep-learning forecasts across India (Gaikwad et al. 2023/24)
  - after-the-fact Sentinel-2 burn mapping at field scale (Anand et al. 2025; Walker et al. 2022 preprint)
- **In a targeted search, I found no peer-reviewed work forecasting which ~500 m cropland cells will burn in the next 7 days** from optical + radar crop-stage time series, evaluated against an enforcement team's daily visit budget.
- **Two papers change the plan:**
  1. Jethva 2026 (*Remote Sensing* 18:1506) shows burning moved to late afternoon from 2022, after polar overpasses. An ISRO SEVIRI study reports the same, but its venue is not verified.
  2. Walker et al. note burn scars can disappear within 2–3 days.
- Together these mean neither label source alone is reliable over time, and label quality has to be measured per season in Phase 2.

## 6. Recommendations for the Phase 1 decisions

**6.1 Pilot districts. Recommend Sangrur + Tarn Taran for training/validation, and Bathinda as the never-seen spatial holdout.**
- **Sangrur:** the largest share of detections (13.2%), mid-season timing (median 50% day 41), and also the cost-pilot district.
- **Tarn Taran:** early-timing Majha regime (median 50% day 34) with enough fires (5.8% share). Amritsar is earlier (day 29) but has only 3.2% of fires.
- **Bathinda:** second-largest share (9.6%), late Malwa timing (median day 43), and not adjacent to either training district. That makes the holdout a real spatial generalisation test rather than a neighbouring-field test.
- **Trade-off:**
  - A holdout similar to the training districts (e.g. Barnala or Patiala, both next to Sangrur) would give a flattering score.
  - Bathinda is harder but more honest.
  - Two training districts give less spatial variety than three. A cheap upgrade is adding Moga or Muktsar to training later, which the GEE budget will decide.
- **Caveat:** Sangrur in this boundary set includes Malerkotla (D-003).

**6.2 Cell size. Recommend 500 m.**
- **For:**
  - Close to the VIIRS 375 m pixel, so one detection doesn't spread across many cells, as it would at 300 m.
  - Still field-cluster scale (25 ha) for an inspection team.
  - Keeps the positive rate workable: 7-day mean 0.5–3.5% vs all land cells (a lower bound).
- **1 km:**
  - Labels are less noisy: sensor agreement is 8.6–15.7% vs 3.5–6.8%.
  - More balanced: 15–60% of all land cells burn in a season.
  - But a 100 ha cell is too coarse to direct a visit, and the task becomes close to "will this village burn", which is easy and less useful.
- **300 m:** matches Sentinel-2 better, but the active-fire label noise is worse: at 375 m (the closest measured size), only 2.2–4.4% agreement.
- **Cost:** the S2 October scaling runs will show the cost difference between sizes. I expect cost to track area more than cell count, but that is unmeasured.

**6.3 Forecast horizon. Recommend 7 days (keep 3 days as a secondary report).**
- **Positives:** 7 days gives 2.3–2.5× more positives per issue date than 3 days (e.g. 2024: 1,031 vs 421 mean at 500 m). That makes recall@k at k = 200–1000 much less noisy, especially in the low-count 2024 validation season.
- **Fit to the task:**
  - Matches a weekly enforcement or awareness planning cycle.
  - The harvest-to-burn gap of days to about two weeks means crop-stage signals should be informative at 7 days.
  - Separates this project from existing 1–3-day work.
- **Costs:**
  - Coarser timing.
  - Daily issue dates with a 7-day window produce heavily overlapping labels, so Phase 4 bootstrap CIs must be **block bootstrap by week**, not by day.

**6.4 Issue frequency. Recommend daily issue dates for validation and test, and every 3rd day for training.**
- **GEE cost:** issue frequency doesn't affect it (§4).
- **Validation and test:** daily matches how a deployed system would be used and gives about 65 issue dates per season (`h7.issue_days`).
- **Training on every 3rd day:**
  - cuts rows by about 3× and reduces near-duplicate rows
  - the upper bound at 500 m over all Punjab land is 202,044 cells × 65 × 8 seasons ≈ 105 M rows
  - pilot districts are a small fraction of that
- **Trade-off:** slightly less training data per season; a cheap test in Phase 4 is training on daily data and checking whether it helps.

## 7. Problems and open questions for the owner

1. **Register the GEE project** at https://console.cloud.google.com/earth-engine/configuration?project=stubblecast (noncommercial, Community tier).
   - Check that `stubblecast-runner@stubblecast.iam.gserviceaccount.com` has the *Earth Engine Resource Writer* role.
   - Then I run `run_all.py` and update §4 and §6.2 with measured numbers.
2. **Rotate the service-account key** after this session. It was pasted into the chat, so it is in the transcript. In future, set it as an environment secret (`GEE_SERVICE_ACCOUNT_KEY`).
3. **Get a FIRMS MAP_KEY before Phase 6.** No yearly file exists for 2026, and none for NOAA-21 at all.
4. **Decide D-001** (label sensor), **D-002** (§6), and look at **D-004** (late-afternoon burning).
   - D-004 is the biggest scientific risk found so far: the fall in detections from 2022 on may be partly fewer *detections* rather than less burning, and the validation and test seasons fall in that period.
5. **Optional:** add a geostationary fire product (GK2A or Himawari) as a third label source in Phase 2. It would directly measure what polar orbiters miss, at about 2–4 km resolution.
