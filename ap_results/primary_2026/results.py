"""Build the 2026 MA state primary municipality-level results dataset.

Normalizes the AP feed (see ap_results/feed.py) for the September 1, 2026
primaries, one row per (party, office, district, municipality, candidate).

Only contested races carry vote data. AP does not tabulate uncontested
primaries -- it reports them with every voteCount at 0 -- so those races are
dropped rather than written out as spurious zeros.

Building this event first rebuilds the nominations dataset (candidates.py),
which supplies candidate residence and incumbency.

Output: data/ap_results/primary_2026/ma_primary_2026_results.csv.gz
"""

import sys

import pandas as pd

from .. import DISTRICT_REFERENCE, rel
from ..feed import (RU_TOWN, candidate_name, load_payloads, races,
                    state_unit)
from ..normalize import (AP_OFFICE, OFFICE_META, ap_district_name,
                         build_reference, first_last, party_abbr,
                         resolve_district)
from ..verify import duplicate_problems, fail_on, fail_on_unmatched, race_sum_problems
from . import candidates

OUT_NAME = "ma_primary_2026_results.csv.gz"

# Snapshot suffix -> primary party.
SUFFIX_PARTY = {"dem": "Democratic", "gop": "Republican"}


def extract_rows(payload, party, ref, event):
    """Yield one dict per (contested in-scope race, municipality, candidate)."""
    snapshot_time = payload.get("lastUpdated")
    for race in races(payload):
        if race["officeName"] not in event.offices or race.get("uncontested"):
            continue
        office = AP_OFFICE[race["officeName"]]
        branch, office_id = OFFICE_META[office]

        seat = None
        if office not in ("Governor", "U.S. Senate"):
            seat = ap_district_name(office, race.get("seatName"))
        match = resolve_district(office, seat, ref, event.election_date)
        if match is None:
            yield {"_unmatched": (party, office, race.get("seatName"))}
            continue
        district, district_display, district_id = match

        state = state_unit(race)
        results_final = bool(state["final"]) if state else False

        for unit in race["reportingUnits"]:
            if unit["reportingunitLevel"] != RU_TOWN:
                continue
            town_total = sum(c.get("voteCount", 0) for c in unit["candidates"])
            for cand in unit["candidates"]:
                votes = cand.get("voteCount", 0)
                yield {
                    "election_date": event.election_date,
                    "is_special": 0,
                    "party": party,
                    "party_abbr": party_abbr(party),
                    "office_branch": branch,
                    "office_id": office_id,
                    "office": office,
                    "district": district,
                    "district_display": district_display,
                    "district_id": district_id,
                    "city_town": unit.get("reportingunitName"),
                    "county_fips": unit.get("fipsCode"),
                    "town_fips": unit.get("townFIPSCode"),
                    "precincts_reporting": unit.get("precinctsReporting"),
                    "precincts_total": unit.get("precinctsTotal"),
                    "precincts_reporting_pct": unit.get("precinctsReportingPct"),
                    "candidate_name": candidate_name(cand),
                    "first_name": cand.get("first"),
                    "middle_name": cand.get("middle"),
                    "last_name": cand.get("last"),
                    "ap_candidate_id": cand.get("candidateID"),
                    "is_incumbent_ap": int(bool(cand.get("incumbent"))),
                    "is_race_winner": int(cand.get("winner") == "X"),
                    "votes": votes,
                    "town_total_votes": town_total,
                    "percent": (votes / town_total) if town_total else None,
                    "ap_race_id": race["raceID"],
                    "eevp": race.get("eevp"),
                    "race_call_status": race.get("raceCallStatus"),
                    "results_final": int(results_final),
                    "last_updated": unit.get("lastUpdated"),
                    "snapshot_time": snapshot_time,
                }


def join_candidates(df, candidates_file):
    """Attach candidate residence and incumbency from the nominations dataset.

    The AP feed carries no electionstats IDs, so candidates are matched within
    a race on normalized first+last.
    """
    cand = pd.read_csv(candidates_file)
    cand["_district"] = cand["district"].fillna("")
    cand["_name"] = cand["name"].map(first_last)
    cand = cand[["office", "_district", "party_abbr", "_name", "city_town",
                 "is_incumbent"]].rename(columns={"city_town": "candidate_city_town"})
    cand = cand.drop_duplicates(subset=["office", "_district", "party_abbr", "_name"])

    df["_district"] = df["district"].fillna("")
    df["_name"] = df["candidate_name"].map(first_last)
    merged = df.merge(cand, how="left",
                      on=["office", "_district", "party_abbr", "_name"])
    return merged.drop(columns=["_district", "_name"])


def build(event, fetch=False):
    candidates.build(event)
    print()

    ref = build_reference(DISTRICT_REFERENCE)
    payloads = load_payloads(event, fetch)

    rows = []
    unmatched = []
    for suffix, payload in payloads.items():
        for row in extract_rows(payload, SUFFIX_PARTY[suffix], ref, event):
            if "_unmatched" in row:
                unmatched.append(row["_unmatched"])
            else:
                rows.append(row)
    fail_on_unmatched(unmatched)

    if not rows:
        sys.exit("no contested in-scope races found -- check the snapshots")

    df = pd.DataFrame(rows)
    df["district_id"] = df["district_id"].astype("Int64")
    df = join_candidates(df, candidates.out_file(event))
    df = df[[
        "election_date", "is_special", "party", "party_abbr",
        "office_branch", "office_id", "office",
        "district", "district_display", "district_id",
        "city_town", "county_fips", "town_fips",
        "precincts_reporting", "precincts_total", "precincts_reporting_pct",
        "candidate_name", "first_name", "middle_name", "last_name",
        "ap_candidate_id", "candidate_city_town",
        "is_incumbent", "is_incumbent_ap", "is_race_winner",
        "votes", "town_total_votes", "percent",
        "ap_race_id", "eevp", "race_call_status", "results_final",
        "last_updated", "snapshot_time",
    ]]
    df = df.sort_values(
        ["office_id", "district_id", "district", "party", "city_town",
         "candidate_name"],
        na_position="first",
    ).reset_index(drop=True)

    in_scope = lambda race: race["officeName"] in event.offices  # noqa: E731
    fail_on(
        race_sum_problems(payloads.values(), in_scope)
        + duplicate_problems(
            df, ["party", "office", "district", "city_town", "candidate_name"])
    )

    out = event.out_dir / OUT_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, compression="gzip")

    race_keys = df[["party", "office_id", "district_id", "district"]].drop_duplicates()
    print(f"Wrote {len(df)} rows to {rel(out)}")
    print(f"{len(race_keys)} contested races, "
          f"{df[['party', 'office', 'district', 'city_town']].drop_duplicates().shape[0]} "
          f"race-municipality rows, {int(df['votes'].sum()):,} votes")

    print("\nRows by office and party:")
    print(df.groupby(["office", "party"]).size().to_string())

    towns = df.drop_duplicates(["party", "ap_race_id", "city_town"])
    all_races = df[["party", "ap_race_id"]].drop_duplicates()
    final_races = df[df["results_final"] == 1][
        ["party", "ap_race_id"]].drop_duplicates()
    print("\nReporting status:")
    print(f"  races AP calls final: {len(final_races)} of {len(all_races)}")
    print(f"  precincts reporting: {int(towns['precincts_reporting'].sum()):,}"
          f" of {int(towns['precincts_total'].sum()):,}")
    print(f"  snapshot taken: {df['snapshot_time'].max()}")

    unmatched_cand = df[df["candidate_city_town"].isna()]
    if not unmatched_cand.empty:
        names = sorted(unmatched_cand["candidate_name"].unique())
        print(f"\nWARNING: {len(names)} candidates did not match the "
              f"nominations dataset (no residence/incumbency attached):")
        for n in names:
            print(f"  {n}")

    disagree = df[df["is_incumbent"].notna()
                  & (df["is_incumbent"] != df["is_incumbent_ap"])]
    if not disagree.empty:
        pairs = disagree[["office", "district", "candidate_name",
                          "is_incumbent", "is_incumbent_ap"]].drop_duplicates()
        print(f"\nWARNING: {len(pairs)} candidates where AP incumbency "
              f"disagrees with the nominations dataset:")
        print(pairs.to_string(index=False))
