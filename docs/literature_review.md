# Literature review (Phase 1)

Scope: what has been done on detecting, mapping and forecasting crop-residue fires in
NW India, and on ML fire forecasting generally, so the project's contribution can be stated
precisely. Citation metadata (title, authors, venue, volume, date) was checked against
Crossref on 2026-11-04. Where I could not read the full text, the summary is from the abstract
or the publisher page and is marked *(abstract only)*.

## Papers

| # | Paper | Task | Unit / resolution | Lead time | Inputs | Validation |
|---|---|---|---|---|---|---|
| 1 | Jethva, H. (2022). *Assessing predictability of post-monsoon crop residue fires in Northwestern India.* Frontiers in Earth Science 10:1047278. doi:10.3389/feart.2022.1047278 | Forecast **seasonal total** fire count | One region (74–77°E, 29–32°N), one number per season | ~1–2 weeks before season | September MODIS NDVI; linear regression | Fit 2002–2016, tested 2017–2021; MAE ≈4–7% of season total |
| 2 | Gaikwad, S. et al. (2023 online; 2024 issue). *Harnessing deep learning for forecasting fire-burning locations and unveiling PM2.5 emissions.* Modeling Earth Systems and Environment 10:927–941. doi:10.1007/s40808-023-01831-1 | Forecast fire **locations** | Gridded, India-wide (grid size not confirmed: full text not accessible) | 1–3 days | NDVI, temperature, wind, surface pressure, cloud cover; ConvLSTM vs ConvGRU | Correlation ≈0.8 on day 1, ≈0.5–0.55 on days 2–3 *(abstract only)* |
| 3 | Anand, A., Imasu, R., Dhaka, S., Patra, P. (2025). *Domain adaptation and fine-tuning of a deep learning segmentation model of small agricultural burn area detection using high-resolution Sentinel-2 observations: a case study of Punjab, India.* Remote Sensing 17:974. doi:10.3390/rs17060974 | **Map burned area after the fact** | Sentinel-2 pixels (10–20 m) | none (retrospective) | Sentinel-2; segmentation model pre-trained on Portuguese burn data, fine-tuned on Punjab annotations | Beats an NBR-threshold baseline on Punjab annotations |
| 4 | Walker, K. et al. (2022). *Detecting crop burning in India using satellite data.* arXiv:2209.10148 (preprint) | **Detect** burned vs unburned plots | Field plots; PlanetScope 3 m, Sentinel-2 | none (retrospective) | Spectral bands + burn indices; random forest | Ground-verified plots in Punjab; ≈82% accuracy. Notes burned plots can look unburned again within 2–3 days |
| 5 | Liu, T., Mickley, L., Singh, S., Jain, M., DeFries, R., Marlier, M. (2020). *Crop residue burning practices across north India inferred from household survey data: bridging gaps in satellite observations.* Atmospheric Environment: X 8:100091. doi:10.1016/j.aeaoa.2020.100091 | Emissions inventory correcting satellite gaps | Gridded daily (SAGE-IGP), 2003–2018 | none | MODIS FRP, VIIRS, household surveys | Bottom-up check for Punjab 2016–2017. Key point for us: fires are short (≈30 min) and are missed between overpasses *(abstract only)* |
| 6 | Jethva, H. (2026). *Timing the flames: geostationary satellite detection of diurnally shifting stubble burning in Northwestern India.* Remote Sensing 18:1506. doi:10.3390/rs18101506 | Measure **time of day** of burning | GK2A-AMI, ≈4 km, hourly | none | Geostationary fire detection, 2019–2025 | Finds burning shifted toward late afternoon (after the ~13:30 polar overpass) from 2022 onward, so MODIS/VIIRS under-report |
| 7 | ISRO/NRSC study, *Evidence of shift in stubble burning timing over North-West India from geostationary satellite observation* (2025). **Venue not verified** (known only from press coverage, e.g. The Tribune, ThePrint) | Time of day of burning | MSG-SEVIRI, 15-min | none | SEVIRI fire detections 2020–2024 | Reported: peak moved from ≈13:30 to ≈17:00; SEVIRI counts not declining while VIIRS counts fall. Treated as unverified until the paper is located |
| 8 | Huot, F. et al. (2022). *Next Day Wildfire Spread: a machine learning dataset to predict wildfire spreading from remote-sensing data.* IEEE TGRS 60:1–13. doi:10.1109/TGRS.2022.3192974 | Forecast next-day **wildfire spread** (US) | 1 km grid | 1 day | Topography, vegetation, weather, drought, population; CNN vs logistic regression / random forest | Method reference: the closest ML benchmark design (gridded remote-sensing inputs, fire-mask target, simple baselines) |

## The gap, stated as narrowly as the evidence allows

- **Seasonal or regional forecasts exist** (1), and **short-lead gridded deep-learning forecasts exist** (2).
- **After-the-fact burn mapping at field scale exists** (3, 4).
- I found **no peer-reviewed study** that forecasts *which ≈500 m cropland cells* will burn in the next week by combining:
  - crop-stage signals from Sentinel-2 and Sentinel-1 time series (harvest timing), and
  - fire-history and weather features,
  - with an evaluation built for an enforcement team's daily visit budget (precision@k / recall@k).
- This is "not found in a targeted search", not "proven absent". My searches covered MDPI Remote Sensing, Frontiers, Springer and arXiv through general web search; Scopus or Web of Science would be the next step.

## What the literature changes for this project

1. **Labels are a biased sample of burning, not ground truth** (5, 6, 7).
   - Fires last tens of minutes, and polar orbiters see Punjab only around 13:00–14:45 IST.
   - If burning moved to late afternoon from 2022 on, VIIRS-based labels become *less complete over time*. This affects 2022–2024 training/validation and the 2025–2026 test seasons.
   - Our Phase 1 EDA can't confirm or refute this with polar-orbiter data alone (see the phase report).
   - Burn-scar labels (Sentinel-2 dNBR, Phase 2) do not depend on the time of day, which makes them the main defence against this.
   - Geostationary fire products (GK2A, Himawari, SEVIRI) are worth evaluating as an extra label source in Phase 2.
2. **Burn scars fade fast** (4). Burned plots can look unburned after 2–3 days (tillage).
   - So 5-day Sentinel-2 revisits will miss some scars.
   - The dNBR window in Phase 2 must be short, and scar-label recall must be measured, not assumed.
3. **A simple seasonal model is strong at the regional level** (1).
   - Our cell-level baselines should include a "regional seasonal intensity" term. Otherwise a model could look good just by learning the season-wide level.
