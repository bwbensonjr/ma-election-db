"""Build the 2026 MA state primary municipality-level results dataset.

Reads the Associated Press election feed that fronts the Boston Globe's 2026
primary coverage and normalizes it to ma-election-db conventions: office /
office_id / office_branch, canonical district names, and district_id /
district_display joined from `district_reference.csv`.

The AP feed's finest granularity is the municipality *within a district*
(`reportingunitLevel == 2`), so a city split across several districts appears
once per district holding only that district's precincts. There is no ward or
precinct tier; `level` accepts only `ru` and `fipscode`, and `fipscode` returns
nothing for Massachusetts.

Only contested races carry vote data. AP does not tabulate uncontested
primaries -- it reports them with every voteCount at 0 -- so those races are
dropped rather than written out as spurious zeros.

Results are preliminary and the upstream feed mutates, so the raw responses are
snapshotted under `primary_2026/snapshots/` and checked in. The build reads
those snapshots by default; pass --fetch to refresh them from the network.

Output: data/primary_2026/ma_primary_2026_results.csv.gz
"""

import argparse
import gzip
import json
import sys
from pathlib import Path

import pandas as pd
import requests

from build_primary_2026 import (
    OFFICE_META,
    PARTY_ABBR,
    US_SENATE_DISTRICT,
    US_SENATE_DISTRICT_ID,
    build_reference,
    district_key,
    first_last,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
REF_FILE = HERE / "district_reference.csv"
SNAPSHOT_DIR = HERE / "snapshots"
CANDIDATES_FILE = REPO / "data" / "primary_2026" / "ma_primary_2026_candidates.csv.gz"
OUT_FILE = REPO / "data" / "primary_2026" / "ma_primary_2026_results.csv.gz"

ELECTION_DATE = "2026-09-01"

API_URL = f"https://elections-api.bostonglobe.com/v2/elections/{ELECTION_DATE}"

# The feed splits the two primaries into separate responses.
API_PARTIES = {"dem": "Democratic", "gop": "Republican"}

# AP office names -> the office names ma-election-db uses. Offices absent from
# this map (District Attorney, Attorney General, Lieutenant Governor,
# Secretary of State, Treasurer, Auditor) are outside the existing schema and
# are skipped, matching build_primary_2026.py.
AP_OFFICE = {
    "U.S. Senate": "U.S. Senate",
    "Governor": "Governor",
    "U.S. House": "U.S. House",
    "Governor's Council": "Governor's Council",
    "State Senate": "State Senate",
    "State House": "State Representative",
}

# Statewide offices have no district lookup (see build_primary_2026.STATEWIDE);
# U.S. Senate carries its Class as the district.
AP_STATEWIDE = {"Governor", "U.S. Senate"}

# AP reporting-unit levels: 1 is the whole state, 2 is a municipality.
RU_STATE = 1
RU_TOWN = 2


def ordinal(n):
    """1 -> '1st', 2 -> '2nd', 3 -> '3rd', 4 -> '4th', ..."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def ap_district_name(office, seat_name):
    """Translate an AP seatName into a spelling build_reference() can key on.

    State House / State Senate seats already arrive in display form ("18th
    Essex", "5th Middlesex"). The two numbered offices arrive as "District N",
    which the reference records as an ordinal ("6th") for Governor's Council
    and as a bare number ("7") for U.S. House.
    """
    if seat_name is None:
        sys.exit(f"missing seatName for {office!r}")
    seat_name = seat_name.strip()
    if office in ("Governor's Council", "U.S. House"):
        if not seat_name.lower().startswith("district "):
            sys.exit(f"unexpected {office} seatName: {seat_name!r}")
        number = int(seat_name.split()[-1])
        return ordinal(number) if office == "Governor's Council" else str(number)
    return seat_name


def fetch(party_code, out_path):
    """Fetch one party's races at municipality granularity and snapshot them."""
    params = {"statePostal": "MA", "party": party_code, "level": "ru"}
    resp = requests.get(API_URL, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("races"):
        sys.exit(f"empty race list for party {party_code!r} -- refusing to snapshot")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(payload, f)
    return payload


def load_snapshot(path):
    if not path.exists():
        sys.exit(f"missing snapshot {path.relative_to(REPO)} -- run with --fetch")
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def candidate_name(cand):
    """AP splits names into first/middle/last; rebuild the display form."""
    parts = [cand.get("first"), cand.get("middle"), cand.get("last")]
    return " ".join(p for p in parts if p)


def extract_rows(payload, party, ref):
    """Yield one dict per (contested in-scope race, municipality, candidate)."""
    snapshot_time = payload.get("lastUpdated")
    for wrapper in payload["races"]:
        race = wrapper["raceResponse"]
        office = AP_OFFICE.get(race["officeName"])
        if office is None or race.get("uncontested"):
            continue

        branch, office_id = OFFICE_META[office]
        if office == "Governor":
            district = district_display = None
            district_id = None
        elif office == "U.S. Senate":
            district = district_display = US_SENATE_DISTRICT
            district_id = US_SENATE_DISTRICT_ID
        else:
            key = district_key(ap_district_name(office, race.get("seatName")))
            match = ref.get(office, {}).get(key)
            if match is None:
                yield {"_unmatched": (party, office, race.get("seatName"))}
                continue
            district, district_display, district_id = match

        state_unit = next(
            (u for u in race["reportingUnits"] if u["reportingunitLevel"] == RU_STATE),
            None,
        )
        results_final = bool(state_unit["final"]) if state_unit else False

        for unit in race["reportingUnits"]:
            if unit["reportingunitLevel"] != RU_TOWN:
                continue
            town_total = sum(c.get("voteCount", 0) for c in unit["candidates"])
            for cand in unit["candidates"]:
                votes = cand.get("voteCount", 0)
                yield {
                    "election_date": ELECTION_DATE,
                    "is_special": 0,
                    "party": party,
                    "party_abbr": PARTY_ABBR[party],
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


def join_candidates(df):
    """Attach candidate residence and incumbency from the nominations dataset.

    The AP feed carries no electionstats IDs, so candidates are matched within
    a race on normalized first+last -- the same approach build_primary_2026.py
    uses against the Secretary of the Commonwealth listings.
    """
    if not CANDIDATES_FILE.exists():
        sys.exit(
            f"missing {CANDIDATES_FILE.relative_to(REPO)} -- "
            "run build_primary_2026.py first"
        )
    cand = pd.read_csv(CANDIDATES_FILE)
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


def verify(df, payloads):
    """Fail loudly on any integrity problem. Preliminary data is still data."""
    problems = []

    # Every candidate's town votes must sum to AP's own statewide total.
    # Sum of per-town precinct counts must likewise equal the race total --
    # this is what confirms a split city is counted once per district.
    for payload in payloads:
        for wrapper in payload["races"]:
            race = wrapper["raceResponse"]
            if AP_OFFICE.get(race["officeName"]) is None or race.get("uncontested"):
                continue
            units = race["reportingUnits"]
            state = next(
                (u for u in units if u["reportingunitLevel"] == RU_STATE), None)
            if state is None:
                problems.append(f"race {race['raceID']}: no statewide unit")
                continue
            towns = [u for u in units if u["reportingunitLevel"] == RU_TOWN]

            by_cand = {}
            for unit in towns:
                for c in unit["candidates"]:
                    by_cand[c["candidateID"]] = (
                        by_cand.get(c["candidateID"], 0) + c.get("voteCount", 0))
            for c in state["candidates"]:
                want = c.get("voteCount", 0)
                got = by_cand.get(c["candidateID"], 0)
                if want != got:
                    problems.append(
                        f"race {race['raceID']} ({race['officeName']} "
                        f"{race.get('seatName')}) candidate {c['last']}: "
                        f"towns sum to {got}, statewide says {want}")

            want_p = state.get("precinctsTotal")
            got_p = sum(u.get("precinctsTotal", 0) for u in towns)
            if want_p != got_p:
                problems.append(
                    f"race {race['raceID']} ({race['officeName']} "
                    f"{race.get('seatName')}): town precincts sum to {got_p}, "
                    f"statewide says {want_p}")

    key = ["party", "office", "district", "city_town", "candidate_name"]
    dupes = df[df.duplicated(subset=key, keep=False)]
    if not dupes.empty:
        problems.append(f"{len(dupes)} duplicate rows on {key}")

    if problems:
        print("ERROR: verification failed:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fetch", action="store_true",
                    help="refresh the snapshots from the live AP feed")
    args = ap.parse_args()

    ref = build_reference(REF_FILE)

    payloads = []
    rows = []
    unmatched = []
    for code, party in API_PARTIES.items():
        path = SNAPSHOT_DIR / f"ap_{ELECTION_DATE}_{code}.json.gz"
        if args.fetch:
            payload = fetch(code, path)
            print(f"Fetched {party} races -> {path.relative_to(REPO)}")
        else:
            payload = load_snapshot(path)
        payloads.append(payload)
        for row in extract_rows(payload, party, ref):
            if "_unmatched" in row:
                unmatched.append(row["_unmatched"])
            else:
                rows.append(row)

    if unmatched:
        print("ERROR: districts that did not match the reference:", file=sys.stderr)
        for party, office, seat in unmatched:
            print(f"  [{party}] {office}: {seat!r}", file=sys.stderr)
        sys.exit(1)

    if not rows:
        sys.exit("no contested in-scope races found -- check the snapshots")

    df = pd.DataFrame(rows)
    df["district_id"] = df["district_id"].astype("Int64")
    df = join_candidates(df)
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

    verify(df, payloads)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_FILE, index=False, compression="gzip")

    races = df[["party", "office_id", "district_id", "district"]].drop_duplicates()
    print(f"Wrote {len(df)} rows to {OUT_FILE.relative_to(REPO)}")
    print(f"{len(races)} contested races, "
          f"{df[['party', 'office', 'district', 'city_town']].drop_duplicates().shape[0]} "
          f"race-municipality rows, {int(df['votes'].sum()):,} votes")

    print("\nRows by office and party:")
    print(df.groupby(["office", "party"]).size().to_string())

    all_races = df[["party", "ap_race_id"]].drop_duplicates()
    final_races = df[df["results_final"] == 1][
        ["party", "ap_race_id"]].drop_duplicates()
    print("\nReporting status:")
    print(f"  races AP calls final: {len(final_races)} of {len(all_races)}")
    print(f"  precincts reporting: {int(df.drop_duplicates(['party', 'ap_race_id', 'city_town'])['precincts_reporting'].sum()):,}"
          f" of {int(df.drop_duplicates(['party', 'ap_race_id', 'city_town'])['precincts_total'].sum()):,}")
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


if __name__ == "__main__":
    main()
