# StubbleCast — Build Plan

Claude Code builds each phase. You review at the gate, make the decision listed, then start the next phase. Expect roughly 6–8 weeks part-time.

**Who does what**
- **Claude Code:** writes code, runs pipelines, produces reports, recommends options.
- **You (reviewer):** check the gate items, make the decisions, and make sure the project owner understands every choice well enough to defend it in an interview.

**Seasons and splits (default, confirm in Phase 1)**
- Train: 2019–2023 · Validate: 2024 · Test: 2025 and 2026 (the 2026 season ends early December, so its data is complete around mid-December).
- Also report a spatial holdout: one district never seen during training.

**Where this sits relative to existing work** (Claude Code confirms in Phase 1)
- Deep learning on Sentinel-2 has been used to *map burn areas after the fact* in Punjab (Anand et al., *Remote Sensing* 2025).
- ConvLSTM models have *forecasted fire locations up to 3 days ahead on a coarse grid* (*Modeling Earth Systems and Environment*, 2023).
- **This project's angle:** field-scale (≈500 m), week-ahead forecasts driven by crop-stage signals from optical + radar time series, with explicit handling of noisy labels and an evaluation built around how enforcement teams would use it.

---

## Phase 0 — Setup (you, ~1 day)

Things only a human can do:
1. Google Cloud project registered for **noncommercial Earth Engine** use (Community tier is free; ~150 EECU-hours/month).
2. NASA Earthdata account and a **FIRMS MAP_KEY**.
3. **OpenAQ** API key (needed only in Phase 8).
4. A GitHub repo, with `CLAUDE.md` at the root and this file at `docs/PLAN.md`.
5. A free **Kaggle or Colab** account for GPU training.

**Gate:** keys in `.env`, `earthengine authenticate` works.

---

## Phase 1 — Scoping and data audit

**Claude Code builds**
- Repo skeleton, environment, config files, `.env.example`.
- Scripts that pull a small sample from every source and confirm the dataset IDs, bands, date coverage and API limits actually work.
- Exploratory analysis of FIRMS history for Punjab 2019–2025: fires per day, per district, per season; peak timing; year-to-year shift.
- A short literature review (5–10 papers) confirming the gap described above.
- A measured GEE cost for one pilot district and one season, extrapolated to full scope.

**Acceptance criteria:** every source verified with a working sample; EDA figures in `reports/figures/`; cost estimate in the phase report.

**Your review:** Do the EDA plots make sense (peak in late Oct–mid Nov)? Is the GEE estimate within budget?

**Decide:** pilot districts, cell size (300 m / 500 m / 1 km), forecast horizon (3 vs 7 days), issue frequency (daily vs every 3 days).

---

## Phase 2 — Labels (the hardest data-science part)

**Claude Code builds**
- Active-fire labels: VIIRS detections → cell-day labels; mask persistent non-agricultural hotspots.
- Burn-scar labels: Sentinel-2 dNBR between clear images before and after, with a dated window.
- A fused label rule, plus a table of how often the two sources agree and disagree.
- A small labelling tool (notebook or tiny web page) that shows you before/after imagery for 100–200 sampled cells so **you hand-check them**.

**Acceptance criteria:** label pipeline runs end to end for pilot districts; agreement statistics reported; hand-check results give an estimated label precision and recall.

**Your review:** do the hand-checks honestly. This sample becomes the evidence for "how good are the labels", which interviewers will ask about.

**Decide:** final label rule (active fires only, scars only, or fused) and how to treat uncertain cells (drop, down-weight, or keep).

---

## Phase 3 — Features

**Claude Code builds**
- GEE exports of per-cell time series for the ~60 days before each issue date: Sentinel-2 indices (NDVI, NBR, NDMI, etc., 5-day composites), Sentinel-1 VV/VH, ERA5-Land weather.
- Fire-history features: fires within 2 km / 5 km in the last 1, 3, 7 days; the cell's own burn history in previous seasons.
- Crop-stage features: estimated harvest date (from NDVI drop and radar change), days since harvest.
- `tests/test_leakage.py` that checks timestamps on real samples.
- `docs/DATA_CARD.md`: sources, coverage, missing-data rates, known biases.

**Acceptance criteria:** feature table for all train/validation seasons in the pilot districts; leakage test passes; missing-data rates reported.

**Your review:** look at 5 random cells' time series plotted next to their labels. Does a harvest show up before burns?

**Decide:** whether to expand from pilot districts to all of Punjab now, based on the GEE budget.

---

## Phase 4 — Evaluation harness and baselines

**Claude Code builds**
- Season-based and spatial splits.
- Metrics: PR-AUC; **precision@k and recall@k**, where k = cells an enforcement team could visit per day (for example 200, 500, 1000); Brier score and reliability plots.
- Baselines, simplest first:
  1. Cell's burn history in previous seasons.
  2. Recent nearby fire activity.
  3. Logistic regression on all features.
  4. LightGBM on all features.

**Acceptance criteria:** one results table, all baselines, validation season only, with confidence intervals (bootstrap over days).

**Your review:** this is the most important gate. If LightGBM is already very strong, the deep learning phase must show a clear reason to exist (better recall at fixed k, better calibration, or better behaviour under cloud cover).

**Decide:** the primary metric you will headline (recommendation: recall@k at a realistic k) and what improvement over LightGBM counts as meaningful.

---

## Phase 5 — Deep learning

**Claude Code builds**
1. **Per-cell temporal model:** a small temporal CNN or transformer over the Sentinel-2 + Sentinel-1 sequence, with weather and history features joined in.
2. **Spatiotemporal model:** operates on the grid of cells over time (ConvLSTM, or a U-Net with a temporal encoder) so neighbouring harvests and fires inform each prediction.
3. **Stretch — self-supervised pretraining:** masked reconstruction on unlabeled pixel time series, then a label-efficiency curve (performance with 5%, 10%, 25%, 50%, 100% of labels).
- **Ablations:** remove radar, remove optical, remove weather, remove fire history.
- **Calibration:** temperature scaling or isotonic regression fitted on validation data.

**Acceptance criteria:** all models evaluated on the same validation splits as Phase 4; ablation table; calibration before/after.

**Your review:** check that the gains are larger than the confidence intervals; check behaviour on cloudy days specifically.

**Decide:** one final model (plus LightGBM as reference) to take to the test seasons.

---

## Phase 6 — Final test and error analysis

**Claude Code builds**
- One evaluation of the final model and LightGBM on the 2025 and 2026 seasons and the spatial holdout district. Logged in `docs/TEST_LOG.md`.
- Error analysis by district, date in season, cloud cover, fire intensity, and label source.
- A "failure gallery": 10–20 missed fires and false alarms with imagery, each with a one-line explanation.
- `docs/MODEL_CARD.md`: intended use, performance, limitations, misuse risks (for example, penalising farmers based on a prediction rather than evidence).

**Your review:** read the failure gallery yourselves. The best interview answers come from here.

**Decide:** nothing; this phase reports.

---

## Phase 7 — Demo and write-up

**Claude Code builds**
- Interactive map (Streamlit, or a static web map with Leaflet/deck.gl): daily risk for a held-out season, a date slider, actual fires overlaid, and precision@k shown for each day.
- README with a 30-second summary, architecture diagram, results table, and how to reproduce.
- A technical write-up (~1,500–2,000 words): problem, data, labels, baselines, model, results, limitations.

**Your review:** can someone with no context understand the README in 60 seconds?

---

## Phase 8 (stretch) — Link to Delhi air quality

**Claude Code builds**
- A daily "upwind fire exposure" index for Delhi: fires weighted by wind direction and distance (or HYSPLIT back-trajectories if time allows).
- A regression of Delhi PM2.5 on that index with weather controls (wind speed, boundary-layer height, humidity), seasons held out.
- Language framed as association with stated assumptions, not proven causation.

---

## CV bullets (fill in only with real numbers from `reports/metrics/`)

- Built a week-ahead stubble-burning forecaster for Punjab at 500 m resolution, fusing Sentinel-2, Sentinel-1, ERA5 weather and NASA VIIRS fire data across 8 seasons (2019–2026).
- Designed a weak-label pipeline combining active-fire and burn-scar detections; hand-validated [N] cells to estimate label quality ([X]% precision).
- Spatiotemporal deep model reached [X] recall@500 on held-out 2025–26 seasons vs [Y] for a tuned LightGBM baseline; calibrated probabilities (Brier [Z]).
- Shipped an interactive daily risk map, with model card and failure analysis.
