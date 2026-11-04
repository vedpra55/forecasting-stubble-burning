"""Run every Phase 1 step in order (one command per phase).

    uv run python scripts/phase1/run_all.py            # everything
    uv run python scripts/phase1/run_all.py --no-pilot # skip the GEE batch cost pilot
"""

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
STEPS = ["download_firms.py", "verify_firms.py", "verify_openaq.py", "verify_boundaries.py",
         "verify_s2.py", "verify_s1.py", "verify_worldcover.py", "verify_era5.py",
         "firms_eda.py"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pilot", action="store_true")
    args = ap.parse_args()
    steps = STEPS + ([] if args.no_pilot else ["gee_cost_pilot.py"]) + ["cost_extrapolate.py"]
    for s in steps:
        print(f"== {s}", flush=True)
        r = subprocess.run([sys.executable, str(HERE / s)])
        if r.returncode != 0:
            print(f"step {s} exited with {r.returncode}", flush=True)
            if s == "gee_cost_pilot.py":
                continue
            sys.exit(r.returncode)


if __name__ == "__main__":
    main()
