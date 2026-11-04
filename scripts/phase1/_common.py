"""Shared runner for Phase 1 verification scripts.

Each check returns a dict. If Earth Engine (or an API key) is unavailable the check is
recorded as "skipped" with the reason - never as a pass.
"""

from __future__ import annotations

import io
import re
import time
import traceback
from collections.abc import Callable

from stubblecast import gee
from stubblecast.metrics_io import write_metrics


class Skipped(Exception):
    """Raise inside a check when a prerequisite (key, credential) is missing."""


def parse_profile(text: str) -> float | None:
    """Sum the EECU-seconds 'Compute' column of an ee.profilePrinting() table."""
    total, found = 0.0, False
    for line in text.splitlines():
        m = re.match(r"\s*(?P<eecu>[0-9.]+)\s+[0-9.]+[kMG]?\s+", line)
        if m:
            total += float(m.group("eecu"))
            found = True
    return total if found else None


def run_check(name: str, fn: Callable[[], dict], needs_gee: bool = True,
              params: dict | None = None) -> dict:
    t0 = time.time()
    profile_text = None
    try:
        if needs_gee:
            import ee

            gee.initialize()
            buf = io.StringIO()
            with ee.profilePrinting(destination=buf):
                result = fn()
            profile_text = buf.getvalue()
        else:
            result = fn()
        status = "pass" if result.pop("_ok", True) else "fail"
        payload = {"status": status, **result}
    except (gee.GEEUnavailable, Skipped) as e:
        payload = {"status": "skipped", "reason": str(e)[:500]}
    except Exception as e:  # noqa: BLE001 - record any failure honestly
        payload = {"status": "error", "error": f"{type(e).__name__}: {e}"[:2000],
                   "traceback": traceback.format_exc()[-3000:]}
    payload["wall_seconds"] = round(time.time() - t0, 1)
    if profile_text is not None:
        payload["interactive_eecu_seconds_profiled"] = parse_profile(profile_text)
        payload["profile_raw"] = profile_text[:4000]
    path = write_metrics(name, payload, params=params)
    print(f"{name}: {payload['status']} -> {path.relative_to(path.parents[2])}")
    return payload
