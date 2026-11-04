# CLAUDE.md — StubbleCast: week-ahead stubble-burning forecasts from satellite data

Read this file fully at the start of every session. Then read `docs/PLAN.md` and the latest file in `docs/phase_reports/` to see where the project stands.

## What this project is

A flagship portfolio project for a data scientist. It forecasts **which cropland cells in Punjab (and later Haryana) are likely to see stubble burning in the next 7 days**, using Sentinel-2 optical imagery, Sentinel-1 radar, weather, and fire history.

It will be scrutinised by expert interviewers. Priorities, in order:
**correctness > rigor > clarity of reasoning > polish.**
A smaller, honest result beats a bigger, shaky one.

The human owner reviews every phase and makes all key decisions. You build; they decide. They must be able to defend every choice in an interview, so explain your reasoning in plain language as you go.

## Prediction task (fixed definition — change only via a logged decision)

- **Region:** start with 2–3 pilot districts set in `configs/region.yaml`; expand to all of Punjab, then Haryana, only after the pipeline is proven.
- **Unit:** grid cells (default 500 m) masked to cropland using ESA WorldCover.
- **Season:** roughly 25 Sep – 5 Dec each year. Seasons 2019–2026.
- **Issue date `t`:** every day of the season (or every 3 days if budget is tight).
- **Target:** `y = 1` if the cell burns in the window `(t, t+7]` under the label rules from Phase 2.
- **Inputs:** only information available at or before `t`. No exceptions.

## Data sources (verify every dataset ID and API detail against official docs before use — do not trust this list blindly)

| Purpose | Source | Notes |
|---|---|---|
| Optical time series | Sentinel-2 L2A via Google Earth Engine (`COPERNICUS/S2_SR_HARMONIZED`) | Mask clouds with Cloud Score+ (`GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`) |
| Radar (sees through clouds/smoke) | Sentinel-1 GRD via GEE (`COPERNICUS/S1_GRD`) | VV, VH, VH/VV ratio |
| Cropland mask | ESA WorldCover via GEE (`ESA/WorldCover/v200`) | Cropland class |
| Weather | ERA5-Land daily via GEE (`ECMWF/ERA5_LAND/DAILY_AGGR`) | Wind, humidity, temperature, precipitation |
| Active fire labels | NASA FIRMS (VIIRS 375 m) | Free MAP_KEY. Area API accepts only a short day range per call; use archive downloads for history. Check FIRMS notices for retired products; prefer NOAA-20 / NOAA-21 VIIRS for recent seasons |
| Burn-scar labels | Sentinel-2 dNBR (computed in GEE) | Complements active-fire detections |
| Air quality (Phase 8 only) | OpenAQ API v3 (CPCB stations) | Needs API key |

## Hard rules

1. **No leakage.** Every feature for issue date `t` uses only data timestamped `≤ t` (satellite acquisition date, weather date, fire detection date). Write and keep passing a test in `tests/test_leakage.py` that checks this on real samples.
2. **Splits are by season (year), never random rows.** Neighbouring cells are correlated; random splits inflate scores. Also report a spatial holdout (unseen districts).
3. **Never fabricate or estimate results.** Every number in any doc, README or report must come from a script in this repo and be saved under `reports/metrics/` as JSON. If something fails or a result is bad, say so plainly.
4. **Baselines first.** No deep learning model is reported without the Phase 4 baselines evaluated on identical splits.
5. **The test seasons are sacred.** Touch them only in Phase 6, once per final candidate, and log every touch in `docs/TEST_LOG.md`.
6. **Earth Engine budget.** The free Community tier is about 150 EECU-hours per month. Run a small pilot first, log each export's cost, reduce data server-side, and export compact per-cell tables. Never download full-resolution imagery for a whole state.
7. **Secrets** (`FIRMS_MAP_KEY`, `OPENAQ_API_KEY`, GEE project ID) live in `.env`, which is git-ignored. Provide `.env.example`.
8. **Stop at review gates.** At the end of each phase, write `docs/phase_reports/phase_N.md` (what was built, results, problems, open questions) and STOP. Do not start the next phase until the owner says so.
9. **Decisions with real trade-offs** go into `docs/DECISIONS.md` as: context → options → your recommendation → why. Then stop and ask. Once decided, record the outcome there.
10. **Explain the why.** Every non-obvious choice gets a short plain-language rationale in `DECISIONS.md` or the phase report.

## Repo layout

```
configs/            YAML configs (region, grid, seasons, model hyperparameters)
data/               git-ignored; raw/, interim/, processed/
docs/               PLAN.md, DECISIONS.md, TEST_LOG.md, DATA_CARD.md, MODEL_CARD.md, phase_reports/
notebooks/          exploration only; nothing the pipeline depends on
reports/            metrics/ (JSON), figures/
src/stubblecast/    data/, labels/, features/, models/, evaluation/, app/
tests/              unit tests, incl. test_leakage.py
```

## Engineering conventions

- Python 3.11+, environment managed with `uv` (pinned lockfile). Lint with `ruff`, test with `pytest`.
- All randomness seeded. Configs drive runs; no magic numbers in code.
- Pipelines are re-runnable steps with cached outputs (Parquet for tables, Zarr or NumPy for tensors).
- Training must run on a free Kaggle or Colab GPU, and the per-cell models on CPU.
- Keep functions small and tested. Prefer clear code over clever code.

## Known pitfalls to handle explicitly

- **Active fires are under-detected.** VIIRS sees each spot about once or twice a day; small, short or cloud/smoke-covered fires are missed, and fires lit after the satellite passes may not be seen. Burn scars (dNBR) catch some of these. Measure how much the two label sources disagree.
- **False fire detections** can come from hot surfaces such as industrial sites and brick kilns. Mask persistent non-agricultural hotspots.
- **Clouds and smoke** contaminate optical data; that is why Sentinel-1 is included.
- **Severe class imbalance.** Report PR-AUC, precision@k and recall@k, calibration. Never headline accuracy.
- **Harvest timing shifts each year.** Prefer season-relative and crop-stage features over raw calendar dates.
- **VIIRS and MODIS confidence fields use different scales.** Do not mix them.

## Definition of done (whole project)

- Reproducible pipeline from raw data to metrics with one command per phase.
- Honest comparison of baselines vs. deep learning, with ablations and calibration.
- Final evaluation on held-out seasons, with error analysis by district, cloud cover and date.
- An interactive risk map of a held-out season with actual fires overlaid.
- README, data card, model card, and a technical write-up stating limitations clearly.
