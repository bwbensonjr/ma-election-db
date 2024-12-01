"""Use the `electionstats.state.ma.us` website to query election
results for a given range of years and set of offices producing a
flattened representation of the elections and candidates as an output."""

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
    "CandidateToElection.is_winner": "winner",
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


def main():
    extract_elections(stage="General")
    # extract_elections(
    #     min_year=1996,
    #     max_year=2024,
    #     stage="Primaries",
    # )


def extract_elections(min_year=1990, max_year=2024, stage="General"):
    if stage == "General":
        file_id = ""
    elif stage == "Primaries":
        file_id = "primary_"
    elec_list = []
    cand_list = []
    for year_from in range(min_year, max_year, 5):
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
    # Write elections
    elecs = pd.concat(elec_list, ignore_index=True)
    elecs_file = f"data/ma_{file_id}elections_{min_year}_{max_year}.csv.gz"
    print(f"Writing elections {elecs_file}...")
    elecs.to_csv(elecs_file, index=False)
    # Write candidates
    cands = pd.concat(cand_list, ignore_index=True)
    cands_file = f"data/ma_{file_id}candidates_{min_year}_{max_year}.csv.gz"
    print(f"Writing candidates {cands_file}...")
    cands.to_csv(cands_file, index=False)
    print("Done.")


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
