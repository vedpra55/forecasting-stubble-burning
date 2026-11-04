"""Download and cache FIRMS yearly India CSVs for the EDA seasons (pre-filtered to bbox)."""

from stubblecast import config
from stubblecast.data import firms

SENSORS = ["viirs_noaa20", "viirs_snpp", "modis"]


def main() -> None:
    years = config.load("seasons")["eda_seasons"]
    for sensor in SENSORS:
        for y in years:
            df = firms.load_year(sensor, y, allowed_years=years)
            print(f"{sensor} {y}: {len(df):,} detections in bbox")


if __name__ == "__main__":
    main()
