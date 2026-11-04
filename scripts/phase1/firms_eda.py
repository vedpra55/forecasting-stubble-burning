"""Phase 1 FIRMS exploratory analysis for Punjab, EDA seasons only (2019-2024).

Outputs:
  reports/metrics/firms_eda.json
  reports/figures/firms_*.png

Conventions:
  - Season window from configs/seasons.yaml (25 Sep - 5 Dec, inclusive).
  - Primary sensor: VIIRS NOAA-20 (continuous 2018-present; see DECISIONS.md D-001).
  - "Fires" = FIRMS type 0 (presumed vegetation fire) unless stated otherwise.
  - Local time = UTC + 5:30 (IST).
"""

from __future__ import annotations

from datetime import date, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from stubblecast import config, plotting
from stubblecast.data import boundaries, firms, grid
from stubblecast.metrics_io import write_metrics

SENSORS = ["viirs_noaa20", "viirs_snpp", "modis"]
SENSOR_LABEL = {"viirs_noaa20": "VIIRS NOAA-20", "viirs_snpp": "VIIRS S-NPP",
                "modis": "MODIS (Terra+Aqua)"}
PRIMARY = "viirs_noaa20"
CELL_SIZES = config.load("grid")["candidate_cell_sizes_m"]
HORIZONS = [3, 7]
PERSISTENT_MIN_YEARS = 3  # off-season detections in >= this many years -> persistent candidate


def season_bounds(season: int) -> tuple[date, date]:
    cfg = config.load("seasons")
    m0, d0 = map(int, cfg["season_start"].split("-"))
    m1, d1 = map(int, cfg["season_end"].split("-"))
    return date(season, m0, d0), date(season, m1, d1)


def load_all(seasons: list[int], punjab_fc: dict, haryana_fc: dict) -> pd.DataFrame:
    frames = []
    for sensor in SENSORS:
        for y in seasons:
            df = firms.load_year(sensor, y, allowed_years=seasons)
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["year"] = pd.to_datetime(df["acq_date"]).dt.year
    pb = firms.assign_districts(df, punjab_fc)
    pb["state"] = np.where(pb["district"].notna(), "Punjab", None)
    hr = firms.assign_districts(pb[pb["state"].isna()].drop(columns="district"), haryana_fc)
    pb.loc[hr.index, "district"] = hr["district"]
    pb.loc[hr.index[hr["district"].notna()], "state"] = "Haryana"
    return pb[pb["state"].notna()].copy()


def in_season_mask(df: pd.DataFrame) -> pd.Series:
    cfg = config.load("seasons")
    return df["acq_date"].map(
        lambda d: firms.in_season(d, d.year, cfg["season_start"], cfg["season_end"]))


# ----------------------------------------------------------------------------- analyses

def sensor_summary(df: pd.DataFrame) -> dict:
    out = {}
    for sensor in SENSORS:
        s = df[(df.sensor == sensor) & (df.state == "Punjab")]
        ins = s[s.in_season]
        entry = {
            "type_counts_in_season": {str(k): int(v) for k, v in
                                      ins["type"].value_counts().sort_index().items()},
            "season_totals_type0": {int(k): int(v) for k, v in
                                    ins[ins["type"] == 0].groupby("season").size().items()},
            "share_of_calendar_year_in_season_type0": {
                int(y): round(float((g.in_season).mean()), 4)
                for y, g in s[s["type"] == 0].groupby("year")},
            "daynight_share_in_season": {k: round(float(v), 4) for k, v in
                                         ins["daynight"].value_counts(normalize=True).items()},
        }
        if sensor.startswith("viirs"):
            entry["confidence_share_in_season"] = {
                k: round(float(v), 4)
                for k, v in ins["confidence_class"].value_counts(normalize=True).items()}
            entry["version_values"] = sorted(ins["version"].astype(str).unique().tolist())
        else:
            entry["confidence_pct_quantiles"] = {
                q: float(ins["confidence_pct"].astype(float).quantile(q))
                for q in (0.1, 0.5, 0.9)}
            entry["satellite_counts_in_season"] = {
                k: int(v) for k, v in ins["satellite"].value_counts().items()}
        out[sensor] = entry
    return out


def timing(fires: pd.DataFrame, seasons: list[int]) -> tuple[dict, pd.DataFrame]:
    """Daily counts per season, peak and cumulative-quantile dates."""
    rows, out = [], {}
    for s in seasons:
        d0, d1 = season_bounds(s)
        days = pd.date_range(d0, d1, freq="D").date
        counts = fires[fires.season == s].groupby("acq_date").size().reindex(days, fill_value=0)
        roll = counts.rolling(7, center=True, min_periods=1).mean()
        cum = counts.cumsum() / counts.sum()
        q = {f"q{int(p * 100)}": str(cum.index[np.argmax(cum.values >= p)]) for p in
             (0.1, 0.5, 0.9)}
        out[s] = {
            "total": int(counts.sum()),
            "peak_day": str(counts.idxmax()), "peak_day_count": int(counts.max()),
            "peak_7day_mean_center": str(roll.idxmax()),
            **q,
            "days_q10_to_q90": (date.fromisoformat(q["q90"]) -
                                date.fromisoformat(q["q10"])).days,
            "zero_fire_days": int((counts == 0).sum()),
            # days inside the q10-q90 core with < 10% of the peak-day count: candidates for
            # cloud/smoke cover or unfavourable overpass geometry (tested in Phase 2/3)
            "low_days_in_core": [str(d) for d, c in counts.items()
                                 if q["q10"] <= str(d) <= q["q90"] and c < 0.1 * counts.max()],
        }
        for i, (d, c) in enumerate(counts.items()):
            rows.append({"season": s, "date": d, "day_of_season": i, "count": int(c),
                         "cum_frac": float(cum.iloc[i])})
    daily = pd.DataFrame(rows)
    q50_doy = [daily[(daily.season == s) & (daily.cum_frac >= 0.5)].day_of_season.min()
               for s in seasons]
    out["q50_day_of_season_range"] = [int(min(q50_doy)), int(max(q50_doy))]
    out["q50_shift_days_max_minus_min"] = int(max(q50_doy) - min(q50_doy))
    return out, daily


def district_table(fires: pd.DataFrame, seasons: list[int]) -> tuple[dict, pd.DataFrame]:
    tab = (fires.groupby(["district", "season"]).size().unstack(fill_value=0)
           .reindex(columns=seasons, fill_value=0))
    tab = tab.loc[tab.sum(axis=1).sort_values(ascending=False).index]
    share = tab.sum(axis=1) / tab.values.sum()
    q50 = {}
    for dname, g in fires.groupby("district"):
        per = []
        for s in seasons:
            gs = g[g.season == s].sort_values("acq_date")
            if len(gs) >= 50:
                cum = np.arange(1, len(gs) + 1) / len(gs)
                d50 = gs["acq_date"].iloc[np.argmax(cum >= 0.5)]
                per.append((d50 - season_bounds(s)[0]).days)
        if per:
            q50[dname] = {"median_q50_day_of_season": float(np.median(per)),
                          "seasons_used": len(per)}
    out = {
        "totals": {d: {int(s): int(v) for s, v in row.items()} for d, row in tab.iterrows()},
        "share_of_state_total": {d: round(float(v), 4) for d, v in share.items()},
        "cv_across_seasons": {d: round(float(row.std() / row.mean()), 3) if row.mean() else None
                              for d, row in tab.iterrows()},
        "top5_share": round(float(share.iloc[:5].sum()), 4),
        "q50_timing": q50,
        "n_districts": int(len(tab)),
    }
    return out, tab


def sensor_agreement(df: pd.DataFrame, cell_m: int = 500) -> dict:
    """At cell-day level: how often does one VIIRS sensor see what the other sees?"""
    sub = df[(df.state == "Punjab") & df.in_season & (df["type"] == 0)
             & df.sensor.isin(["viirs_noaa20", "viirs_snpp"])].copy()
    sub["cell"] = grid.cell_id(sub.longitude.values, sub.latitude.values, cell_m)
    out = {}
    for s, g in sub.groupby("season"):
        a, b = g[g.sensor == "viirs_noaa20"], g[g.sensor == "viirs_snpp"]
        n20 = set(zip(a.cell, a.acq_date, strict=True))
        snpp = set(zip(b.cell, b.acq_date, strict=True))
        both = n20 & snpp
        # tolerant match: same cell, other sensor within +/-1 day
        snpp_cells = {}
        for c, d in snpp:
            snpp_cells.setdefault(c, set()).add(d)
        n20_cells = {}
        for c, d in n20:
            n20_cells.setdefault(c, set()).add(d)

        def tol(a, other):
            hits = 0
            for c, d in a:
                ds = other.get(c, ())
                if any(abs((d - x).days) <= 1 for x in ds):
                    hits += 1
            return hits / len(a) if a else float("nan")

        # season-level: cells ever detected
        c20 = {c for c, _ in n20}
        cnp = {c for c, _ in snpp}
        out[int(s)] = {
            "n20_cell_days": len(n20), "snpp_cell_days": len(snpp), "both_same_day": len(both),
            "p_snpp_given_n20_same_day": round(len(both) / len(n20), 4),
            "p_n20_given_snpp_same_day": round(len(both) / len(snpp), 4),
            "p_snpp_given_n20_pm1day": round(tol(n20, snpp_cells), 4),
            "p_n20_given_snpp_pm1day": round(tol(snpp, n20_cells), 4),
            "season_cells_n20": len(c20), "season_cells_snpp": len(cnp),
            "season_cells_jaccard": round(len(c20 & cnp) / len(c20 | cnp), 4),
        }
    return out


def agreement_vs_scale(df: pd.DataFrame, sizes=(375, 500, 1000, 2000, 5000)) -> dict:
    """Same-day NOAA-20 -> S-NPP agreement as a function of cell size, plus overpass gap.

    If agreement rises steeply with cell size, disagreement is mostly fires that are
    short-lived relative to the ~50 min gap between the two overpasses (each sensor sees a
    different subset of fields), not geolocation error.
    """
    sub = df[(df.state == "Punjab") & df.in_season & (df["type"] == 0)
             & df.sensor.isin(["viirs_noaa20", "viirs_snpp"])].copy()
    sub["local_h"] = (sub.acq_hour_utc + 5.5) % 24
    gap = (sub.groupby(["acq_date", "sensor"]).local_h.median().unstack().dropna())
    gap_min = ((gap["viirs_noaa20"] - gap["viirs_snpp"]).abs() * 60)
    out = {"overpass_gap_minutes_median": round(float(gap_min.median()), 1),
           "overpass_gap_minutes_iqr": [round(float(gap_min.quantile(0.25)), 1),
                                        round(float(gap_min.quantile(0.75)), 1)]}
    for cell_m in sizes:
        sub["cell"] = grid.cell_id(sub.longitude.values, sub.latitude.values, cell_m)
        per = {}
        for s, g in sub.groupby("season"):
            a, b = g[g.sensor == "viirs_noaa20"], g[g.sensor == "viirs_snpp"]
            n20 = set(zip(a.cell, a.acq_date, strict=True))
            snpp = set(zip(b.cell, b.acq_date, strict=True))
            per[int(s)] = round(len(n20 & snpp) / len(n20), 4)
        out[f"p_snpp_given_n20_same_day_{cell_m}m"] = per
    return out


def detection_time_drift(df: pd.DataFrame) -> dict:
    """Does the local time of detections drift later across seasons?

    Polar orbiters see Punjab only near ~13:00-14:45 IST. If burning shifts to late
    afternoon (reported from 2022 on using geostationary data), detections should
    concentrate in the later part of each sensor's overpass window. This is a weak,
    indirect check; geostationary data are needed for a direct one.
    """
    sub = df[(df.state == "Punjab") & df.in_season & (df["type"] == 0)
             & df.sensor.str.startswith("viirs")].copy()
    sub["local_h"] = (sub.acq_hour_utc + 5.5) % 24
    out = {}
    for sensor, g in sub.groupby("sensor"):
        day = g[g.daynight == "D"]
        # normalise by overpass: per day, fires per overpass vs that day's overpass time
        per_day = day.groupby("acq_date").agg(n=("local_h", "size"), t=("local_h", "median"))
        per_day["season"] = [d.year for d in per_day.index]
        out[sensor] = {
            int(s): {
                "median_local_detection_hour": round(float(gs.local_h.median()), 3),
                "share_detections_after_14h_ist": round(float((gs.local_h >= 14).mean()), 4),
                "corr_daily_count_vs_overpass_hour": round(float(
                    per_day[per_day.season == s][["n", "t"]].corr().iloc[0, 1]), 3),
            }
            for s, gs in day.groupby(day.acq_date.map(lambda d: d.year))
        }
    return out


def persistent_hotspots(df: pd.DataFrame, cell_m: int = 500) -> dict:
    """Cells with fire detections outside both crop-residue windows in many years.

    Off-season = not in Apr-May (wheat residue) and not 15 Sep - 15 Dec (paddy residue).
    These are candidates for industrial sources / brick kilns, to be masked in Phase 2.
    """
    sub = df[(df.state == "Punjab") & (df.sensor == PRIMARY)].copy()
    sub["cell"] = grid.cell_id(sub.longitude.values, sub.latitude.values, cell_m)
    dt = pd.to_datetime(sub["acq_date"])
    md = dt.dt.month * 100 + dt.dt.day
    off = ~(dt.dt.month.isin([4, 5]) | ((md >= 915) & (md <= 1215)))
    years_off = sub[off].groupby("cell")["year"].nunique()
    persistent = set(years_off[years_off >= PERSISTENT_MIN_YEARS].index)
    ins = sub[sub.in_season]
    ins_t0 = ins[ins["type"] == 0]
    return {
        "cell_m": cell_m, "min_offseason_years": PERSISTENT_MIN_YEARS,
        "n_persistent_cells": len(persistent),
        "in_season_type0_detections_in_persistent_cells": int(ins_t0.cell.isin(persistent).sum()),
        "share_in_season_type0_in_persistent_cells": round(
            float(ins_t0.cell.isin(persistent).mean()), 5),
        "in_season_type2_detections": int((ins["type"] == 2).sum()),
        "type2_cells_also_flagged_persistent": int(
            len(set(ins[ins["type"] == 2].cell) & persistent)),
        "type2_cells_total": int(ins[ins["type"] == 2].cell.nunique()),
    }


def cell_stats(fires: pd.DataFrame, seasons: list[int], punjab_area_km2: float) -> dict:
    """Burned-cell counts per season, positives per issue day, between-season persistence."""
    out = {}
    for cell_m in CELL_SIZES:
        f = fires.copy()
        f["cell"] = grid.cell_id(f.longitude.values, f.latitude.values, cell_m)
        total_cells_upper = punjab_area_km2 / (cell_m / 1000) ** 2
        per_season, cells_by_season = {}, {}
        for s in seasons:
            g = f[f.season == s]
            cells_by_season[s] = set(g.cell)
            d0, d1 = season_bounds(s)
            cell_days = g.groupby("acq_date")["cell"].apply(set)
            horizon = {}
            for h in HORIZONS:
                pos = []
                t = d0
                while t + timedelta(days=h) <= d1:
                    window = set()
                    for k in range(1, h + 1):
                        window |= cell_days.get(t + timedelta(days=k), set())
                    pos.append(len(window))
                    t += timedelta(days=1)
                pos = np.array(pos)
                horizon[f"h{h}"] = {
                    "issue_days": int(len(pos)),
                    "positives_per_issue_day_mean": round(float(pos.mean()), 1),
                    "positives_per_issue_day_median": float(np.median(pos)),
                    "positives_per_issue_day_max": int(pos.max()),
                    "positive_rate_vs_all_state_cells_mean": round(
                        float(pos.mean() / total_cells_upper), 5),
                }
            n_days = g.groupby("cell")["acq_date"].nunique()
            per_season[int(s)] = {
                "burned_cells": int(len(cells_by_season[s])),
                "share_of_state_cells_upper_bound_denominator": round(
                    len(cells_by_season[s]) / total_cells_upper, 4),
                "median_distinct_fire_days_per_burned_cell": float(n_days.median()),
                "share_burned_cells_with_ge2_fire_days": round(float((n_days >= 2).mean()), 4),
                **horizon,
            }
        persist = {}
        for a, b in zip(seasons[:-1], seasons[1:], strict=True):
            prev, cur = cells_by_season[a], cells_by_season[b]
            persist[f"{a}->{b}"] = {
                "p_burn_given_burned_prev": round(len(cur & prev) / len(prev), 4),
                "share_of_current_burned_cells_that_burned_prev": round(
                    len(cur & prev) / len(cur), 4),
            }
        out[cell_m] = {"total_state_cells_upper_bound": int(total_cells_upper),
                       "per_season": per_season, "season_to_season_persistence": persist}
    return out


# ----------------------------------------------------------------------------- figures

def fig_daily(daily: pd.DataFrame, seasons: list[int], path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.2), sharex=True, sharey=True)
    for ax, s in zip(axes.flat, seasons, strict=True):
        d = daily[daily.season == s]
        ax.bar(d.day_of_season, d["count"], width=0.85, color=plotting.CAT[0], linewidth=0)
        ax.set_title(str(s), fontsize=10)
    d0 = season_bounds(2000)[0]
    ticks = [0, 20, 36, 51, 66]
    for ax in axes[-1]:
        ax.set_xticks(ticks)
        ax.set_xticklabels([(d0 + timedelta(days=t)).strftime("%d %b") for t in ticks])
    for ax in axes[:, 0]:
        ax.set_ylabel("Detections per day")
    fig.suptitle("Punjab daily VIIRS NOAA-20 fire detections, 25 Sep - 5 Dec",
                 x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_cumulative(daily: pd.DataFrame, seasons: list[int], path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.6))
    for i, s in enumerate(seasons):
        d = daily[daily.season == s]
        ax.plot(d.day_of_season, d.cum_frac, color=plotting.BLUE_ORDINAL[i], label=str(s))
        # direct label at the 50% crossing
        x50 = d[d.cum_frac >= 0.5].day_of_season.min()
        ax.plot([x50], [0.5], marker="o", ms=4, color=plotting.BLUE_ORDINAL[i])
    ax.axhline(0.5, color=plotting.AXIS, lw=0.8, zorder=0)
    d0 = season_bounds(2000)[0]
    ticks = [0, 6, 20, 36, 51, 66]
    ax.set_xticks(ticks)
    ax.set_xticklabels([(d0 + timedelta(days=t)).strftime("%d %b") for t in ticks])
    ax.set_ylabel("Cumulative share of season detections")
    ax.set_ylim(0, 1.01)
    ax.legend(title="Season", loc="upper left", ncol=2)
    ax.set_title("Cumulative timing of detections by season (Punjab, VIIRS NOAA-20)")
    fig.savefig(path)
    plt.close(fig)


def fig_district_heatmap(tab: pd.DataFrame, path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 8))
    im = ax.imshow(tab.values, aspect="auto", cmap=plotting.seq_cmap())
    ax.set_xticks(range(tab.shape[1]))
    ax.set_xticklabels(tab.columns)
    ax.set_yticks(range(tab.shape[0]))
    ax.set_yticklabels(tab.index, fontsize=8)
    ax.grid(False)
    vmax = tab.values.max()
    for i in range(tab.shape[0]):
        for j in range(tab.shape[1]):
            v = tab.values[i, j]
            ax.text(j, i, f"{v:,}", ha="center", va="center", fontsize=7,
                    color="#ffffff" if v > 0.55 * vmax else plotting.INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7, colors=plotting.MUTED)
    ax.set_title("In-season VIIRS NOAA-20 detections by district and season")
    fig.savefig(path)
    plt.close(fig)


def fig_sensor_totals(summary: dict, seasons: list[int], path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.2))
    w = 0.26
    x = np.arange(len(seasons))
    for i, sensor in enumerate(SENSORS):
        vals = [summary[sensor]["season_totals_type0"].get(s, 0) for s in seasons]
        ax.bar(x + (i - 1) * (w + 0.02), vals, width=w, color=plotting.CAT[i],
               label=SENSOR_LABEL[sensor], linewidth=0)
    ax.set_xticks(x)
    ax.set_xticklabels(seasons)
    ax.set_ylabel("In-season detections (type 0)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.legend(loc="upper right")
    ax.set_title("Detections per season by sensor, Punjab")
    fig.savefig(path)
    plt.close(fig)


def fig_overpass(df: pd.DataFrame, path) -> None:
    sub = df[(df.state == "Punjab") & df.in_season & (df["type"] == 0)]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2), sharey=False)
    bins = np.arange(0, 24.25, 0.25)
    for ax, (i, sensor) in zip(axes, enumerate(SENSORS), strict=True):
        local = (sub[sub.sensor == sensor].acq_hour_utc + 5.5) % 24
        ax.hist(local, bins=bins, color=plotting.CAT[i], linewidth=0)
        ax.set_title(SENSOR_LABEL[sensor], fontsize=10)
        ax.set_xlim(0, 24)
        ax.set_xticks([0, 6, 12, 18, 24])
        ax.set_xlabel("Local time (IST, h)")
    axes[0].set_ylabel("Detections")
    fig.suptitle("Detection time of day: each sensor sees Punjab only at fixed overpasses",
                 x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_positives(fires: pd.DataFrame, seasons: list[int], path, cell_m: int = 500) -> None:
    f = fires.copy()
    f["cell"] = grid.cell_id(f.longitude.values, f.latitude.values, cell_m)
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.2), sharex=True, sharey=True)
    for ax, s in zip(axes.flat, seasons, strict=True):
        g = f[f.season == s]
        d0, d1 = season_bounds(s)
        cell_days = g.groupby("acq_date")["cell"].apply(set)
        for i, h in enumerate(HORIZONS):
            xs, ys = [], []
            t = d0
            while t + timedelta(days=h) <= d1:
                w = set()
                for k in range(1, h + 1):
                    w |= cell_days.get(t + timedelta(days=k), set())
                xs.append((t - d0).days)
                ys.append(len(w))
                t += timedelta(days=1)
            ax.plot(xs, ys, color=plotting.CAT[i], label=f"{h}-day window")
        ax.set_title(str(s), fontsize=10)
    for ax in axes[:, 0]:
        ax.set_ylabel(f"Positive {cell_m} m cells")
    d0 = season_bounds(2000)[0]
    ticks = [0, 20, 36, 51, 66]
    for ax in axes[-1]:
        ax.set_xticks(ticks)
        ax.set_xticklabels([(d0 + timedelta(days=t)).strftime("%d %b") for t in ticks])
    axes.flat[0].legend(loc="upper left")
    fig.suptitle(f"Positive cells per issue date (fire in (t, t+h]), {cell_m} m grid, NOAA-20",
                 x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ----------------------------------------------------------------------------- main

def main() -> None:
    plotting.apply_style()
    seasons = config.load("seasons")["eda_seasons"]
    punjab = boundaries.districts_for_state("Punjab")
    haryana = boundaries.districts_for_state("Haryana")
    df = load_all(seasons, punjab, haryana)
    df["in_season"] = in_season_mask(df)
    df["season"] = np.where(df.in_season, df.year, -1)

    fires = df[(df.state == "Punjab") & (df.sensor == PRIMARY) & df.in_season
               & (df["type"] == 0)].copy()

    from pyproj import Geod  # noqa: PLC0415 - geodesic area, only needed here
    from shapely.geometry import shape

    geod = Geod(ellps="WGS84")
    punjab_area = sum(abs(geod.geometry_area_perimeter(shape(f["geometry"]))[0])
                      for f in punjab["features"]) / 1e6

    summary = sensor_summary(df)
    timing_out, daily = timing(fires, seasons)
    district_out, tab = district_table(fires, seasons)
    agree = sensor_agreement(df)
    agree_scale = agreement_vs_scale(df)
    hot = persistent_hotspots(df)
    drift = detection_time_drift(df)
    cells = cell_stats(fires, seasons, punjab_area)
    haryana_tot = (df[(df.state == "Haryana") & (df.sensor == PRIMARY) & df.in_season
                      & (df["type"] == 0)].groupby("season").size())

    figs = config.FIGURES_DIR
    figs.mkdir(parents=True, exist_ok=True)
    fig_daily(daily, seasons, figs / "firms_daily_counts_by_season.png")
    fig_cumulative(daily, seasons, figs / "firms_cumulative_timing.png")
    fig_district_heatmap(tab, figs / "firms_district_season_heatmap.png")
    fig_sensor_totals(summary, seasons, figs / "firms_sensor_totals.png")
    fig_overpass(df, figs / "firms_overpass_time.png")
    fig_positives(fires, seasons, figs / "firms_positives_per_issue_day.png")

    daily.to_csv(config.METRICS_DIR / "firms_daily_counts_punjab_noaa20.csv", index=False)
    write_metrics("firms_eda", {
        "punjab_area_km2_geodesic": round(punjab_area, 1),
        "n_punjab_districts": len(punjab["features"]),
        "sensors": summary,
        "timing_noaa20": timing_out,
        "districts_noaa20": district_out,
        "viirs_sensor_agreement_500m": agree,
        "viirs_agreement_vs_cell_size": agree_scale,
        "persistent_hotspots": hot,
        "detection_time_drift": drift,
        "cells_noaa20": {str(k): v for k, v in cells.items()},
        "haryana_season_totals_noaa20_type0": {int(k): int(v) for k, v in haryana_tot.items()},
    }, params={"seasons": seasons, "primary_sensor": PRIMARY,
               "season_window": [config.load("seasons")["season_start"],
                                 config.load("seasons")["season_end"]],
               "boundaries": f"geoBoundaries gbOpen IND ADM2 @ {boundaries.GB_COMMIT}",
               "cell_binning": "local equirectangular, lat0=31"})
    print("done")


if __name__ == "__main__":
    main()
