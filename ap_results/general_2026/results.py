"""Build interim general-election results from the AP feed.

Written against the general stage, not the year: any general-election event
whose `builder` points here gets the same two outputs, named after the event's
year:

- ma_general_<year>_races.csv.gz   one row per (office, district), every seat
  including uncontested ones, shaped like general_election
- ma_general_<year>_results.csv.gz one row per (office, district,
  municipality, candidate) for contested races, shaped like the primary
  results file

AP reports uncontested races with every voteCount at 0 but still marks the
winner, so uncontested seats keep their winner and leave votes blank.
"""

import sys

import pandas as pd

from .. import DISTRICT_REFERENCE, REPO, rel
from ..feed import (candidate_name, load_payloads, races, state_unit,
                    town_units)
from ..incumbency import enrich
from ..normalize import (AP_OFFICE, OFFICE_META, ap_district_name, ap_party,
                         build_reference, first_last, resolve_district)
from ..verify import (duplicate_problems, fail_on, fail_on_unmatched,
                      race_sum_problems)

PRIMARY_CANDIDATES = REPO / "data" / "ma_primary_election_candidates.csv.gz"

RACE_KEY = ["office_id", "district_id"]


def race_meta(race, event, ref):
    """Database office/district fields for a race, or None if unresolved."""
    office = AP_OFFICE[race["officeName"]]
    branch, office_id = OFFICE_META[office]
    seat = None
    if office not in ("Governor", "U.S. Senate"):
        seat = ap_district_name(office, race.get("seatName"))
    match = resolve_district(office, seat, ref, event.election_date)
    if match is None:
        return None
    district, district_display, district_id = match
    return {
        "election_date": event.election_date,
        "is_special": 0,
        "office_branch": branch,
        "office_id": office_id,
        "office": office,
        "district": district,
        "district_display": district_display,
        "district_id": district_id,
    }


def cand_fields(cand):
    party, abbr = ap_party(cand.get("party"))
    return {
        "party": party,
        "party_abbr": abbr,
        "party_ap": cand.get("party"),
        "candidate_name": candidate_name(cand),
        "first_name": cand.get("first"),
        "middle_name": cand.get("middle"),
        "last_name": cand.get("last"),
        "ap_candidate_id": cand.get("candidateID"),
        "is_incumbent_ap": int(bool(cand.get("incumbent"))),
        "is_race_winner": int(cand.get("winner") == "X"),
    }


def extract(payload, event, ref):
    """Return (race-candidate rows, municipality rows, unmatched seats).

    Race-candidate rows carry AP's statewide (district-level) counts, one per
    candidate per race; municipality rows exist only for contested races.
    """
    snapshot_time = payload.get("lastUpdated")
    race_rows, town_rows, unmatched = [], [], []
    for race in races(payload):
        if race["officeName"] not in event.offices:
            continue
        meta = race_meta(race, event, ref)
        if meta is None:
            unmatched.append(("general", AP_OFFICE[race["officeName"]],
                              race.get("seatName")))
            continue
        state = state_unit(race)
        if state is None:
            sys.exit(f"race {race['raceID']}: no statewide unit")
        uncontested = int(bool(race.get("uncontested")))
        race_info = {
            "ap_race_id": race["raceID"],
            "eevp": race.get("eevp"),
            "race_call_status": race.get("raceCallStatus"),
            "results_final": int(bool(state.get("final"))),
            "snapshot_time": snapshot_time,
        }
        for cand in state["candidates"]:
            race_rows.append({
                **meta, **cand_fields(cand), **race_info,
                "is_uncontested": uncontested,
                "votes": None if uncontested else cand.get("voteCount", 0),
                "precincts_reporting": state.get("precinctsReporting"),
                "precincts_total": state.get("precinctsTotal"),
                "precincts_reporting_pct": state.get("precinctsReportingPct"),
                "last_updated": state.get("lastUpdated"),
            })
        if uncontested:
            continue
        for unit in town_units(race):
            town_total = sum(c.get("voteCount", 0) for c in unit["candidates"])
            for cand in unit["candidates"]:
                votes = cand.get("voteCount", 0)
                town_rows.append({
                    **meta, **cand_fields(cand), **race_info,
                    "city_town": unit.get("reportingunitName"),
                    "county_fips": unit.get("fipsCode"),
                    "town_fips": unit.get("townFIPSCode"),
                    "precincts_reporting": unit.get("precinctsReporting"),
                    "precincts_total": unit.get("precinctsTotal"),
                    "precincts_reporting_pct": unit.get("precinctsReportingPct"),
                    "votes": votes,
                    "town_total_votes": town_total,
                    "percent": (votes / town_total) if town_total else None,
                    "last_updated": unit.get("lastUpdated"),
                })
    return race_rows, town_rows, unmatched


def join_nominees(cands, event):
    """Attach electionstats candidate_id and residence for party nominees.

    Democratic and Republican nominees won this cycle's primary, which
    electionstats already carries; match within (office, district, party) on
    first+last name. Unenrolled and other candidates stay blank.
    """
    year = event.election_date[:4]
    prim = pd.read_csv(PRIMARY_CANDIDATES)
    prim = prim[prim["election_date"].str.startswith(year)
                & (prim["is_winner"] == 1)]
    prim = prim.assign(
        _district=prim["district"].fillna(""),
        _name=prim["name"].map(first_last),
    )[["office", "_district", "party", "_name", "candidate_id", "city_town"]]
    prim = prim.rename(columns={"city_town": "candidate_city_town"})
    prim = prim.drop_duplicates(subset=["office", "_district", "party", "_name"])

    cands = cands.assign(
        _district=cands["district"].fillna(""),
        _name=cands["candidate_name"].map(first_last),
    )
    out = cands.merge(prim, how="left",
                      on=["office", "_district", "party", "_name"])
    out["candidate_id"] = out["candidate_id"].astype("Int64")
    return out.drop(columns=["_district", "_name"])


def pick(group, mask):
    """Highest-vote candidate row in `group` matching `mask`, or None."""
    sub = group[mask]
    if sub.empty:
        return None
    return sub.sort_values("votes", ascending=False, na_position="last").iloc[0]


def summarize_races(cands):
    """One row per race with winner / incumbent / dem / gop / third_party."""
    rows = []
    for _, g in cands.groupby(RACE_KEY, sort=False):
        first = g.iloc[0]
        uncontested = bool(first["is_uncontested"])
        total = None if uncontested else int(g["votes"].sum())
        row = {c: first[c] for c in [
            "election_date", "is_special", "office_branch", "office_id",
            "office", "district", "district_display", "district_id",
            "ap_race_id", "is_uncontested"]}
        row["num_candidates"] = len(g)
        row["total_votes"] = total
        for c in ["precincts_reporting", "precincts_total",
                  "precincts_reporting_pct", "eevp", "race_call_status",
                  "results_final"]:
            row[c] = first[c]

        roles = {
            "winner": pick(g, g["is_race_winner"] == 1),
            "incumbent": pick(g, g["is_incumbent"] == 1),
            "dem": pick(g, g["party_abbr"] == "D"),
            "gop": pick(g, g["party_abbr"] == "R"),
            "third_party": pick(g, ~g["party_abbr"].isin(["D", "R"])),
        }
        for role, c in roles.items():
            row[f"id_{role}"] = None if c is None else c["candidate_id"]
            row[f"name_{role}"] = None if c is None else c["candidate_name"]
            if role in ("winner", "incumbent", "third_party"):
                row[f"party_{role}"] = None if c is None else c["party"]
            if role != "incumbent":
                votes = None if c is None else c["votes"]
                row[f"votes_{role}"] = votes
                row[f"percent_{role}"] = (
                    votes / total if total and pd.notna(votes) else None)

        row["incumbent_running"] = int(first["incumbent_running"])
        row["prior_winner_name"] = first["incumbent_name"]
        row["prior_winner_id"] = first["incumbent_id"]
        row["prior_winner_party"] = first["incumbent_party"]
        row["prior_election_date"] = first["incumbent_election_date"]
        row["last_updated"] = first["last_updated"]
        row["snapshot_time"] = first["snapshot_time"]
        rows.append(row)

    df = pd.DataFrame(rows)
    for c in ["district_id", "total_votes", "id_winner", "id_incumbent",
              "id_dem", "id_gop", "id_third_party", "votes_winner",
              "votes_dem", "votes_gop", "votes_third_party",
              "prior_winner_id"]:
        df[c] = df[c].astype("Int64")
    return df


def reconcile_problems(cands, towns):
    """Race-level candidate votes must equal summed municipality votes."""
    key = RACE_KEY + ["ap_candidate_id"]
    want = cands[cands["is_uncontested"] == 0].set_index(key)["votes"]
    got = towns.groupby(key)["votes"].sum()
    both = pd.concat([want.rename("race"), got.rename("towns")], axis=1)
    bad = both[both["race"].fillna(-1) != both["towns"].fillna(-1)]
    return [
        f"office_id {o} district_id {d} candidate {c}: race file says "
        f"{r.race}, municipality file sums to {r.towns}"
        for (o, d, c), r in bad.iterrows()
    ]


def build(event, fetch=False):
    year = event.election_date[:4]
    ref = build_reference(DISTRICT_REFERENCE)
    payloads = load_payloads(event, fetch)

    race_rows, town_rows, unmatched = [], [], []
    for payload in payloads.values():
        r, t, u = extract(payload, event, ref)
        race_rows += r
        town_rows += t
        unmatched += u
    fail_on_unmatched(unmatched)
    if not race_rows:
        sys.exit("no in-scope races found -- check the snapshots")

    cands = pd.DataFrame(race_rows)
    cands["district_id"] = cands["district_id"].astype("Int64")
    cands = enrich(cands, event.election_date, event.incumbent_overrides,
                   name_col="candidate_name")
    cands = join_nominees(cands, event)

    towns = pd.DataFrame(town_rows)
    towns["district_id"] = towns["district_id"].astype("Int64")
    towns = towns.merge(
        cands[RACE_KEY + ["ap_candidate_id", "candidate_id",
                          "candidate_city_town", "is_incumbent"]],
        how="left", on=RACE_KEY + ["ap_candidate_id"])
    towns = towns[[
        "election_date", "is_special", "party", "party_abbr", "party_ap",
        "office_branch", "office_id", "office",
        "district", "district_display", "district_id",
        "city_town", "county_fips", "town_fips",
        "precincts_reporting", "precincts_total", "precincts_reporting_pct",
        "candidate_name", "first_name", "middle_name", "last_name",
        "ap_candidate_id", "candidate_id", "candidate_city_town",
        "is_incumbent", "is_incumbent_ap", "is_race_winner",
        "votes", "town_total_votes", "percent",
        "ap_race_id", "eevp", "race_call_status", "results_final",
        "last_updated", "snapshot_time",
    ]].sort_values(
        ["office_id", "district_id", "city_town", "candidate_name"],
    ).reset_index(drop=True)

    race_df = summarize_races(cands).sort_values(RACE_KEY).reset_index(drop=True)

    in_scope = lambda race: race["officeName"] in event.offices  # noqa: E731
    fail_on(
        race_sum_problems(payloads.values(), in_scope)
        + duplicate_problems(towns, RACE_KEY + ["city_town", "ap_candidate_id"])
        + duplicate_problems(race_df, RACE_KEY)
        + reconcile_problems(cands, towns)
    )

    event.out_dir.mkdir(parents=True, exist_ok=True)
    races_out = event.out_dir / f"ma_general_{year}_races.csv.gz"
    towns_out = event.out_dir / f"ma_general_{year}_results.csv.gz"
    race_df.to_csv(races_out, index=False, compression="gzip")
    towns.to_csv(towns_out, index=False, compression="gzip")

    report(race_df, towns, cands, races_out, towns_out)


def report(race_df, towns, cands, races_out, towns_out):
    contested = race_df[race_df["is_uncontested"] == 0]
    print(f"Wrote {len(race_df)} races to {rel(races_out)}")
    print(f"Wrote {len(towns)} rows to {rel(towns_out)}")
    print(f"{len(contested)} contested races, "
          f"{towns[['office_id', 'district_id', 'city_town']].drop_duplicates().shape[0]} "
          f"race-municipality rows, {int(towns['votes'].sum()):,} votes")

    print("\nRaces by office:")
    print(race_df.groupby(["office", "is_uncontested"]).size()
          .rename(index={0: "contested", 1: "uncontested"}).to_string())

    print("\nSeats by winning party:")
    print(race_df["party_winner"].fillna("(uncalled)").value_counts().to_string())

    uncalled = race_df[race_df["name_winner"].isna()]
    print(f"\nUncalled races: {len(uncalled)}")
    if not uncalled.empty:
        print(uncalled[["office", "district", "race_call_status",
                        "precincts_reporting_pct", "name_dem", "votes_dem",
                        "name_gop", "votes_gop", "name_third_party",
                        "votes_third_party"]].to_string(index=False))

    flips = race_df[race_df["name_winner"].notna()
                    & race_df["prior_winner_party"].notna()
                    & (race_df["party_winner"] != race_df["prior_winner_party"])]
    print(f"\nSeats changing party: {len(flips)}")
    if not flips.empty:
        print(flips[["office", "district", "prior_winner_name",
                     "prior_winner_party", "name_winner",
                     "party_winner"]].to_string(index=False))

    print(f"\nIncumbents running: {int(race_df['incumbent_running'].sum())} "
          f"of {len(race_df)} seats")
    print(f"Snapshot taken: {race_df['snapshot_time'].max()}")

    nominees = cands[cands["party_abbr"].isin(["D", "R"])]
    missing = nominees[nominees["candidate_id"].isna()]
    if not missing.empty:
        print(f"\nWARNING: {len(missing)} D/R candidates did not match a 2026 "
              f"primary winner (no candidate_id / residence):")
        print(missing[["office", "district", "party_abbr",
                       "candidate_name"]].to_string(index=False))

    disagree = cands[cands["is_incumbent"] != cands["is_incumbent_ap"]]
    if not disagree.empty:
        print(f"\nWARNING: {len(disagree)} candidates where AP incumbency "
              f"disagrees with ours:")
        print(disagree[["office", "district", "candidate_name",
                        "is_incumbent", "is_incumbent_ap",
                        "incumbent_name"]].to_string(index=False))
