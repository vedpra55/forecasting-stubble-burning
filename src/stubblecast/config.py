"""Load YAML configs from configs/. All run parameters come from here, not from code."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"
DATA_DIR = REPO_ROOT / "data"
REPORTS_DIR = REPO_ROOT / "reports"
METRICS_DIR = REPORTS_DIR / "metrics"
FIGURES_DIR = REPORTS_DIR / "figures"


@cache
def load(name: str) -> dict[str, Any]:
    """Load configs/<name>.yaml as a dict."""
    path = CONFIG_DIR / f"{name}.yaml"
    with path.open() as f:
        return yaml.safe_load(f)
