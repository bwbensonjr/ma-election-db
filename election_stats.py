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

MIN_YEAR = 1990
MAX_YEAR = 2024


def main():
    elec_list = []
    cand_list = []
    for year_from in range(MIN_YEAR, MAX_YEAR, 5):
        year_to = year_from + 4
        for office in OFFICES:
            elecs, cands = query_elections(
                year_from, year_to, OFFICE_ID[office], "General"
            )
            if elecs is not None:
                elec_list.append(elecs)
            if cands is not None:
                cand_list.append(cands)
    elecs = pd.concat(elec_list, ignore_index=True)
    cands = pd.concat(cand_list, ignore_index=True)
    elecs.to_csv(f"data/ma_elections_{MIN_YEAR}_{MAX_YEAR}.csv.gz", index=False)
    cands.to_csv(f"data/ma_candidates_{MIN_YEAR}_{MAX_YEAR}.csv.gz", index=False)


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