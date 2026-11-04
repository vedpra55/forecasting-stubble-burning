"""Weather feature helpers."""

from __future__ import annotations

import math

# Magnus coefficients over water (Alduchov & Eskridge 1996).
MAGNUS_A = 17.625
MAGNUS_B = 243.04


def rh_from_dewpoint(t_k: float, td_k: float) -> float:
    """Relative humidity (%) from 2 m temperature and dewpoint, both in Kelvin."""
    t, td = t_k - 273.15, td_k - 273.15
    return 100 * math.exp(MAGNUS_A * td / (MAGNUS_B + td) - MAGNUS_A * t / (MAGNUS_B + t))
