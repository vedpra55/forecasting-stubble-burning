"""Verify OpenAQ API v3 (needed only in Phase 8): locations near Delhi + one sensor's data."""

from __future__ import annotations

import os

import requests
from _common import Skipped, run_check
from dotenv import load_dotenv

from stubblecast import config

DELHI = (28.6139, 77.2090)


def check() -> dict:
    load_dotenv(config.REPO_ROOT / ".env")
    key = os.environ.get("OPENAQ_API_KEY")
    if not key:
        raise Skipped("OPENAQ_API_KEY not set (only needed for Phase 8)")
    src = config.load("sources")["openaq"]
    h = {src["auth_header"]: key}
    r = requests.get(f"{src['base_url']}/locations", headers=h, timeout=60,
                     params={"coordinates": f"{DELHI[0]},{DELHI[1]}", "radius": 25000,
                             "parameters_id": 2, "limit": 100})
    r.raise_for_status()
    locs = r.json()["results"]
    sensor = next((s for loc in locs for s in loc.get("sensors", [])
                   if s.get("parameter", {}).get("name") == "pm25"), None)
    days = None
    if sensor:
        d = requests.get(f"{src['base_url']}/sensors/{sensor['id']}/days", headers=h,
                         timeout=60, params={"datetime_from": "2023-11-01",
                                             "datetime_to": "2023-11-08"})
        d.raise_for_status()
        days = [{"date": x["period"]["datetimeFrom"]["local"], "value": x["value"]}
                for x in d.json()["results"]]
    return {"_ok": bool(locs), "n_pm25_locations_25km": len(locs),
            "providers": sorted({loc.get("provider", {}).get("name", "?") for loc in locs}),
            "sample_sensor_id": sensor["id"] if sensor else None, "sample_daily": days,
            "rate_limit_headers": {k: v for k, v in r.headers.items()
                                   if k.lower().startswith("x-ratelimit")}}


if __name__ == "__main__":
    run_check("verify_openaq", check, needs_gee=False)
