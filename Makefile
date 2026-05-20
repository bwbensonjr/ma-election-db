.PHONY: all general_elections primary_elections summaries demographics pvi sqlite clean

# Full rebuild: transform existing raw CSVs, refresh demographics, and
# assemble the SQLite database. Does NOT re-fetch from the MA state API
# or Census API by default; use `make general_elections` or
# `make demographics` (which force re-runs) to refresh those inputs.
all: summaries demographics pvi sqlite

# --- Stage 1: extraction from MA state API -----------------------------
# Re-fetches raw election/candidate CSVs. Run explicitly when new
# election results are published.
general_elections:
	uv run python election_stats.py

primary_elections:
	uv run python election_stats.py --stage Primaries --min-year=1996

# --- Stage 2: transform raw CSVs into summaries -----------------------
summaries: data/ma_general_election_summaries.csv.gz

data/ma_general_election_summaries.csv.gz \
data/ma_general_election_candidates.csv.gz \
data/ma_election_districts.csv: elections.R \
    data/ma_elections.csv.gz \
    data/ma_candidates.csv.gz \
    data/candidate-id-map.csv
	Rscript elections.R

# --- Stage 3: demographics (requires CENSUS_API_KEY) -------------------
# Always re-runs when invoked directly; takes 15-30 min on first run
# due to tigris geometry downloads (cached on subsequent runs).
demographics:
	Rscript demographics/ma_census.R

data/demographics/ma_district_demographics.csv.gz \
data/demographics/ma_precinct_demographics.csv.gz \
data/demographics/ma_city_town_demographics.csv.gz: demographics/ma_census.R \
    demographics/census_vars.csv \
    data/geometry/2021/house2021.geojson \
    data/geometry/2021/senate2021.geojson \
    data/geometry/2021/govcouncil2021.geojson \
    data/geometry/2021/congressma118.geojson \
    data/geometry/2021/wards_pcts_subs_2022.geojson
	Rscript demographics/ma_census.R

# --- Stage 3.5: PVI (district-level partisan voting index) -------------
# Reshapes mapoli's PVI outputs into the unified ma-election-db schema.
# Requires the mapoli repo to be checked out as a sibling directory.
pvi: data/pvi/ma_district_pvi.csv.gz

data/pvi/ma_district_pvi.csv.gz: pvi/ma_pvi.R \
    ../mapoli/pvi/ma_state_leg_pvi_2008_2024.csv \
    ../mapoli/pvi/ma_legislative_district_pvi_2024.csv
	Rscript pvi/ma_pvi.R

# --- Stage 4: assemble the SQLite database ----------------------------
sqlite: data/ma_elections.sqlite

data/ma_elections.sqlite: build_sqlite.R \
    data/ma_general_election_summaries.csv.gz \
    data/ma_general_election_candidates.csv.gz \
    data/demographics/ma_district_demographics.csv.gz \
    data/demographics/ma_precinct_demographics.csv.gz \
    data/pvi/ma_district_pvi.csv.gz
	Rscript build_sqlite.R

clean:
	rm -f data/ma_elections.sqlite
