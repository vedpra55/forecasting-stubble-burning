# StubbleCast

Week-ahead forecasts of which cropland cells in Punjab are likely to see stubble burning,
from Sentinel-2, Sentinel-1, ERA5-Land weather and NASA FIRMS fire history.

**Status:** Phase 1 (scoping and data audit). See `docs/phase_reports/phase_1.md`.

## Reproduce Phase 1

```bash
uv sync
cp .env.example .env   # fill in GEE_PROJECT and a service-account key path
uv run python scripts/phase1/run_all.py
uv run pytest
```

All reported numbers are written to `reports/metrics/*.json` by the scripts above.
