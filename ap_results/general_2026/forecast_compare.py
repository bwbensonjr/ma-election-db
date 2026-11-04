"""Join interim AP general-election results to the 2026 legislative forecast.

The forecast is the election-modeling 14d-r2 snapshot (money cutoff
2026-10-20), as pinned by the massnumbers blog post
posts/2026-10-29-contested-races (blog commit 703da84). Copies live in
ap_results/general_2026/forecast/ because the 14d-r2 snapshot is not checked
in to election-modeling.

The model's margin is the Democrat's two-candidate margin, in points, against
the comparison candidate (the Republican, or the strongest non-Democrat where
no Republican ran): 100 * (D - comparison) / (D + comparison). The actual
margin here is computed the same way from AP's district totals.

Run after `uv run python -m ap_results build general_2026`:

    uv run python -m ap_results.general_2026.forecast_compare

Output: data/ap_results/general_2026/ma_general_2026_forecast_comparison.csv.gz
"""

import sys
from pathlib import Path

import pandas as pd

from .. import rel
from ..events import EVENTS
from ..normalize import first_last

EVENT = EVENTS["general_2026"]
FORECAST_DIR = Path(__file__).resolve().parent / "forecast"
RESULTS_FILE = EVENT.out_dir / "ma_general_2026_results.csv.gz"
RACES_FILE = EVENT.out_dir / "ma_general_2026_races.csv.gz"
OUT_FILE = EVENT.out_dir / "ma_general_2026_forecast_comparison.csv.gz"

KEY = ["office", "district"]


def load_forecast():
    races = pd.read_csv(FORECAST_DIR / "forecast_14d_r2_races.csv")
    intervals = pd.read_csv(FORECAST_DIR / "forecast_14d_r2_intervals.csv")
    target = pd.read_csv(FORECAST_DIR / "forecast_14d_r2_target.csv")
    finance = pd.read_csv(FORECAST_DIR / "forecast_14d_r2_finance.csv")

    target = target[["target_id", "dem_candidate_incumbent",
                     "comparison_candidate_party",
                     "comparison_candidate_incumbent", "incumbent_status",
                     "PVI_N", "ballot_timing"]]
    money = finance.pivot_table(index="target_id", columns="role",
                                values=["receipts", "expenditures"])
    money.columns = [f"{role}_{what}" for what, role in money.columns]
    money = money.rename(columns=lambda c: c.replace("opp_", "comparison_"))

    fc = (races[["target_id", "office", "district", "dem_candidate_name",
                 "comparison_candidate_name", "point_margin", "lower_90",
                 "upper_90", "dem_win_probability"]]
          .merge(intervals, on="target_id", how="left")
          .merge(target, on="target_id", how="left")
          .merge(money.reset_index(), on="target_id", how="left"))
    if fc["target_id"].duplicated().any() or fc[KEY].duplicated().any():
        sys.exit("forecast files have duplicate races")
    return fc.rename(columns={"point_margin": "forecast_margin"})


def candidate_totals():
    """District-level votes per candidate, summed from the municipality file
    (the general build already verifies these equal AP's race totals)."""
    if not RESULTS_FILE.exists():
        sys.exit(f"missing {rel(RESULTS_FILE)} -- run "
                 "`uv run python -m ap_results build general_2026` first")
    t = pd.read_csv(RESULTS_FILE)
    return (t.groupby(KEY + ["candidate_name", "party", "party_abbr",
                             "is_race_winner"], as_index=False)["votes"].sum())


def match_candidate(cands, name, fallback_mask=None):
    """Row in `cands` whose first+last name matches `name`."""
    hit = cands[cands["candidate_name"].map(first_last) == first_last(name)]
    if len(hit) == 1:
        return hit.iloc[0]
    if fallback_mask is not None and fallback_mask.sum() == 1:
        return cands[fallback_mask].iloc[0]
    return None


def main():
    fc = load_forecast()
    cands = candidate_totals()
    races = pd.read_csv(RACES_FILE)[
        KEY + ["district_display", "district_id", "ap_race_id",
               "race_call_status", "precincts_reporting_pct", "eevp",
               "name_winner", "party_winner", "snapshot_time"]]

    rows, problems = [], []
    for _, f in fc.iterrows():
        rc = cands[(cands["office"] == f["office"])
                   & (cands["district"] == f["district"])]
        if rc.empty:
            problems.append(f"{f['district']}: no AP results")
            continue
        dem = match_candidate(rc, f["dem_candidate_name"],
                              rc["party_abbr"] == "D")
        comp = match_candidate(rc, f["comparison_candidate_name"])
        if dem is None or comp is None:
            problems.append(f"{f['district']}: could not match "
                            f"{f['dem_candidate_name']!r} / "
                            f"{f['comparison_candidate_name']!r} in AP")
            continue
        pair = dem["votes"] + comp["votes"]
        rows.append({
            "target_id": f["target_id"],
            "office": f["office"],
            "district": f["district"],
            "dem_votes": int(dem["votes"]),
            "comparison_votes": int(comp["votes"]),
            "other_votes": int(rc["votes"].sum() - pair),
            "actual_margin": 100 * (dem["votes"] - comp["votes"]) / pair
            if pair else None,
        })
    if problems:
        print("ERROR: forecast races that did not join to AP:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        sys.exit(1)

    df = (fc.merge(pd.DataFrame(rows), on=["target_id"] + KEY)
            .merge(races, on=KEY, how="left"))

    called = df["name_winner"].notna()
    df["is_called"] = called.astype(int)
    df["dem_leading"] = (df["actual_margin"] > 0).astype(int)
    df["dem_won"] = df["dem_leading"].where(called).astype("Int64")
    df["forecast_dem_favored"] = (df["dem_win_probability"] > 0.5).astype(int)
    df["forecast_correct"] = (
        (df["forecast_dem_favored"] == df["dem_leading"]).astype(int)
        .where(called).astype("Int64"))
    df["margin_error"] = df["actual_margin"] - df["forecast_margin"]
    df["in_75"] = df["actual_margin"].between(df["lower_75"], df["upper_75"]).astype(int)
    df["in_90"] = df["actual_margin"].between(df["lower_90"], df["upper_90"]).astype(int)
    df["brier"] = (df["dem_win_probability"] - df["dem_won"]).pow(2)

    df = df[[
        "target_id", "office", "district", "district_display", "district_id",
        "PVI_N", "incumbent_status", "ballot_timing",
        "dem_candidate_name", "dem_candidate_incumbent",
        "comparison_candidate_name", "comparison_candidate_party",
        "comparison_candidate_incumbent",
        "dem_receipts", "comparison_receipts",
        "dem_expenditures", "comparison_expenditures",
        "forecast_margin", "lower_75", "upper_75", "lower_90", "upper_90",
        "dem_win_probability", "forecast_dem_favored",
        "ap_race_id", "race_call_status", "is_called",
        "precincts_reporting_pct", "eevp",
        "dem_votes", "comparison_votes", "other_votes", "actual_margin",
        "dem_leading", "dem_won", "name_winner", "party_winner",
        "forecast_correct", "margin_error", "in_75", "in_90", "brier",
        "snapshot_time",
    ]].sort_values("dem_win_probability").reset_index(drop=True)

    df.to_csv(OUT_FILE, index=False, compression="gzip")
    print(f"Wrote {len(df)} races to {rel(OUT_FILE)}")

    c = df[df["is_called"] == 1]
    err = df["margin_error"]
    print(f"\nCalled: {len(c)} of {len(df)}")
    print(f"Favored side won: {int(c['forecast_correct'].sum())} of {len(c)} called")
    print(f"Margin error (actual - forecast, all {len(df)}): mean {err.mean():+.1f}, "
          f"RMSE {(err ** 2).mean() ** 0.5:.1f}, MAE {err.abs().mean():.1f}")
    print(f"Inside 75% interval: {int(df['in_75'].sum())} of {len(df)}; "
          f"inside 90%: {int(df['in_90'].sum())} of {len(df)}")
    print(f"Brier score (called): {c['brier'].mean():.3f}")

    miss = c[c["forecast_correct"] == 0]
    if not miss.empty:
        print("\nFavored side lost:")
        print(miss[["district", "dem_win_probability", "forecast_margin",
                    "actual_margin", "name_winner"]].round(2).to_string(index=False))
    print("\nLargest misses:")
    big = df.reindex(err.abs().sort_values(ascending=False).index).head(8)
    print(big[["district", "forecast_margin", "actual_margin",
               "margin_error", "race_call_status"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
