"""Use the `electionstats.state.ma.us` website to query election
results for a given range of years and set of offices producing a
flattened representation of the elections and candidates as an output."""

import argparse
import datetime
import os
import shutil
import pandas as pd
import requests
import sys

JSON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

BASE_URL = "http://electionstats.state.ma.us/elections/"
SEARCH_URL = BASE_URL + (
    "search/year_from:{year_from}/year_to:{year_to}/"
    "office_id:{office_id}/stage:{stage}"
)
ELECTION_URL = BASE_URL + "view/{election_id}/"
DOWNLOAD_URL = (
    BASE_URL + "download/{election_id}/precincts_include:{precincts_include}/"
)

OFFICE_ID = {
    "President": 1,
    "Governor": 3,
    "US House": 5,
    "US Senate": 6,
    "State Rep": 8,
    "State Senate": 9,
    "Gov Council": 529,
}

OFFICES = list(OFFICE_ID.keys())

STAGES = [
    "General",
    "Primaries",
    "Democratic",
    "Republican",
]

ELECTION_COL_NAMES = {
    "Office.branch": "office_branch",
    "Office.id": "office_id",
    "Office.name": "office",
    "District.name": "district",
    "District.display_name": "district_display",
    "District.id": "district_id",
    "Election.id": "election_id",
    "Election.date": "election_date",
    "Election.party_primary": "party_primary",
    "Election.is_special": "is_special",
    "Election.n_all_other_votes": "all_other_votes",
    "Election.n_blank_votes": "blank_votes",
    "Election.n_total_votes": "total_votes",
}

CAND_COL_NAMES = {
    "CandidateToElection.election_id": "election_id",
    "id": "candidate_id",
    "display_name": "name",
    "first_name": "first_name",
    "middle_name": "middle_name",
    "last_name": "last_name",
    "n_elections": "num_elections",
    "CandidateToElection.is_winner": "is_winner",
    "CandidateToElection.is_write_in": "is_write_in",
    "CandidateToElection.n_votes": "num_votes",
    "CandidateToElection.party": "party",
    "CandidateToElection.address1": "street_addr",
    "CandidateToElection.address2": "city_state",
}

OFFICES = [
    "State Rep",
    "State Senate",
    "US House",
    "US Senate",
    "Gov Council",
    "Governor",
    "President",
]

CURRENT_YEAR = datetime.datetime.now().year

def main():
    parser = argparse.ArgumentParser(
        description="Query election data and put into flat format."
    )
    parser.add_argument("--min-year", default=1990, type=int)
    parser.add_argument("--max-year", default=CURRENT_YEAR, type=int)
    parser.add_argument("--stage", default="General", choices=STAGES)
    args = parser.parse_args()
        
    extract_elections(
        min_year=args.min_year,
        max_year=args.max_year,
        stage=args.stage,
    )

def backup_file(file_path, backup_path):
    """Copy file_path to backup_path. Skip silently if file_path doesn't exist."""
    if not os.path.exists(file_path):
        return
    shutil.copy2(file_path, backup_path)
    print(f"Backed up {file_path} → {backup_path}")


def diff_csv_files(current_path, last_path, key_columns):
    """Read current and last CSV files and print a summary of differences."""
    if not os.path.exists(last_path):
        print(f"No previous file {last_path} to diff.")
        return

    current = pd.read_csv(current_path)
    last = pd.read_csv(last_path)

    print(f"\n--- Diff: {current_path} ---")
    n_last = len(last)
    n_current = len(current)
    delta = n_current - n_last
    sign = "+" if delta >= 0 else ""
    print(f"Rows: {n_last} → {n_current} ({sign}{delta})")

    # Ensure key columns are lists
    if isinstance(key_columns, str):
        key_columns = [key_columns]

    # Build key-indexed DataFrames
    current_keys = current.set_index(key_columns)
    last_keys = last.set_index(key_columns)

    current_idx = set(current_keys.index)
    last_idx = set(last_keys.index)

    new_keys = current_idx - last_idx
    removed_keys = last_idx - current_idx
    common_keys = current_idx & last_idx

    has_diff = False

    # New rows
    for key in sorted(new_keys):
        has_diff = True
        row = current_keys.loc[key]
        print(f"+ {row.to_dict()}")

    # Removed rows
    for key in sorted(removed_keys):
        has_diff = True
        row = last_keys.loc[key]
        print(f"- {row.to_dict()}")

    # Changed rows
    if common_keys:
        common_list = sorted(common_keys)
        cur_common = current_keys.loc[common_list]
        last_common = last_keys.loc[common_list]
        diff_mask = (cur_common != last_common) & ~(cur_common.isna() & last_common.isna())
        for key in diff_mask[diff_mask.any(axis=1)].index:
            has_diff = True
            print(f"- {last_common.loc[key].to_dict()}")
            print(f"+ {cur_common.loc[key].to_dict()}")

    if not has_diff:
        print("No changes.")

    print()


def extract_elections(min_year=1990, max_year=2025, stage="General"):
    if stage == "General":
        file_id = ""
    elif stage == "Primaries":
        file_id = "primary_"
    elecs, cands = query_election_years(min_year, max_year, stage)
    # Write elections
    elecs_file = f"data/ma_{file_id}elections.csv.gz"
    elecs_last = f"data/ma_{file_id}elections_last.csv.gz"
    print(f"Backing up {elecs_file} to {elecs_last}...")
    backup_file(elecs_file, elecs_last)
    print(f"Writing elections {elecs_file}...")
    elecs.to_csv(elecs_file, index=False)
    # Write candidates
    cands_file = f"data/ma_{file_id}candidates.csv.gz"
    cands_last = f"data/ma_{file_id}candidates_last.csv.gz"
    print(f"Backing up {cands_file} to {cands_last}...")
    backup_file(cands_file, cands_last)
    print(f"Writing candidates {cands_file}...")
    cands.to_csv(cands_file, index=False)
    # Diff against previous versions
    print(f"Elections file difference...")
    diff_csv_files(elecs_file, elecs_last, "election_id")
    print(f"Candidates file difference...")
    diff_csv_files(cands_file, cands_last, ["election_id", "candidate_id"])
    print("Done.")

def query_election_years(min_year, max_year, stage):
    elec_list = []
    cand_list = []
    for year_from in range(min_year, (max_year+1), 5):
        year_to = year_from + 4
        for office in OFFICES:
            elecs, cands = query_elections(
                year_from,
                year_to,
                OFFICE_ID[office],
                stage,
            )
            if elecs is not None:
                elec_list.append(elecs)
            if cands is not None:
                cand_list.append(cands)
    elecs = pd.concat(elec_list, ignore_index=True)
    cands = pd.concat(cand_list, ignore_index=True)
    return elecs, cands
    
def query_elections(year_from, year_to, office_id, stage):
    search_url = SEARCH_URL.format(
        year_from=year_from, year_to=year_to, office_id=office_id, stage=stage
    )
    print(f"Requesting url '{search_url}'")
    r = requests.get(search_url, headers=JSON_HEADERS)
    rj = r.json()
    if rj["output"]:
        elecs = pd.json_normalize(rj["output"]).rename(columns=ELECTION_COL_NAMES)[
            ELECTION_COL_NAMES.values()
        ]
        num_elecs = len(elecs)
        cands = pd.json_normalize(rj["output"], record_path=["Candidate"]).rename(
            columns=CAND_COL_NAMES
        )[CAND_COL_NAMES.values()]
        num_cands = len(cands)
        print(f"Found {num_elecs} elections with {num_cands} candidates.")
    else:
        elecs = None
        cands = None
        print(f"No elections or candidates found.")
    return elecs, cands


if __name__ == "__main__":
    main()
