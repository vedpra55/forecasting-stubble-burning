"""Write metric JSON files with provenance (timestamp, git SHA, script, parameters).

Every number reported in a doc must come from a file written by this module
(CLAUDE.md rule 3).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from stubblecast.config import METRICS_DIR, REPO_ROOT


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
        ).stdout.strip()
        return out.stdout.strip() + ("-dirty" if dirty else "")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _default(o: Any) -> Any:
    if hasattr(o, "item"):  # numpy scalars
        return o.item()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


def write_metrics(name: str, payload: dict[str, Any], params: dict[str, Any] | None = None) -> Path:
    """Write reports/metrics/<name>.json and return its path."""
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    doc = {
        "name": name,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": _git_sha(),
        "script": Path(sys.argv[0]).name if sys.argv and sys.argv[0] else None,
        "params": params or {},
        **payload,
    }
    path = METRICS_DIR / f"{name}.json"
    path.write_text(json.dumps(doc, indent=2, default=_default) + "\n")
    return path
