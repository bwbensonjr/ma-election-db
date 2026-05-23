# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Massachusetts Election Database - Tools for querying MA election results from electionstats.state.ma.us and producing a structured database of elections, candidates, and district-level demographics.

The project is organized as a set of domain pipelines that each produce CSVs under `data/<domain>/`, followed by a single SQLite assembler (`build_sqlite.R`) that combines them into `data/ma_elections.sqlite`:

1. **Python extraction** (election_stats.py) - Queries raw election data from the MA state API
2. **R transformation** (elections.R) - Processes raw data into analysis-ready election summaries
3. **Demographics** (demographics/ma_census.R) - Builds district- and precinct-level Census ACS tables
4. **PVI** (pvi/ma_pvi.R) - Reshapes mapoli's district PVI outputs into a multi-year unified table
5. **SQLite assembly** (build_sqlite.R) - Reads the CSVs above and writes `data/ma_elections.sqlite`

## Common Commands

### Full rebuild
```bash
# Transform existing raw CSVs, refresh demographics, and assemble SQLite
make all
```

`make all` runs `elections.R`, `demographics/ma_census.R`, `pvi/ma_pvi.R`,
and `build_sqlite.R` in order. It does NOT re-fetch from the MA state API or
Census API - run `make general_elections` or `make demographics` directly
to refresh those inputs.

### Full data pipeline
```bash
# Extract election data from state API (takes several minutes)
# Default: general elections from 1990-2025
python election_stats.py

# Customize year range or stage
python election_stats.py --min-year 2000 --max-year 2024
python election_stats.py --stage Primaries

# Transform raw CSVs into election summaries
Rscript elections.R

# Assemble the SQLite database from the CSVs
Rscript build_sqlite.R
```

### Primary elections processing (work in progress)
```bash
# Process primary election data
Rscript primary_elections.R
```

### Demographics processing
```bash
# Requires CENSUS_API_KEY env var (see demographics/README.md).
# Takes 15-30 min on first run due to tigris geometry downloads.
Rscript demographics/ma_census.R
```

### PVI processing
```bash
# Reshapes mapoli's PVI outputs into the unified ma-election-db schema.
# Requires the mapoli repo checked out as a sibling (../mapoli). See pvi/README.md.
Rscript pvi/ma_pvi.R
```

### Candidate duplicate detection
```bash
# Find potential duplicate candidates by name matching
python find_dup_candidates.py
```

## Architecture

### Data Flow Pipeline

**Stage 1: Python Extraction (election_stats.py)**
- Queries `electionstats.state.ma.us` API for election results
- Fetches data in 5-year chunks for offices: State Rep, State Senate, US House, US Senate, Gov Council, Governor, President
- API endpoints:
  - Search: `/elections/search/year_from:{year}/year_to:{year}/office_id:{id}/stage:{stage}`
  - Download: `/elections/download/{election_id}/precincts_include:{bool}/`
- Outputs raw flattened data:
  - `data/ma_elections.csv.gz` - Election-level metadata
  - `data/ma_candidates.csv.gz` - Candidate-level results
  - `data/ma_primary_elections.csv.gz` - Primary election metadata (partial)
  - `data/ma_primary_candidates.csv.gz` - Primary candidates (partial)

**Stage 2: R Transformation (elections.R)**
- Reads raw election and candidate CSVs
- **Candidate ID mapping**: Applies global ID mapping from `data/candidate-id-map.csv` to handle duplicate candidate IDs caused by name spelling variations (e.g., "David Allen Robertson" vs "David A. Robertson")
- Applies data fixes for known errors in source data (candidate_fixes function)
- **First election cycle filtering**: Excludes the first election cycle per office from outputs (e.g., 1990 elections) since they lack valid incumbency data
- **Incumbency determination**: Checks if a candidate won the most recent previous election (regular or special) for that office/district
  - Groups by `(office_id, district_id)` to handle U.S. Senate Classes as separate offices
  - Includes special elections - winners of special elections are marked as incumbents in subsequent elections
  - Automatically handles career gaps - candidates not elected in most recent previous election are not incumbents
  - Tracks `district_id_prev` showing which district incumbent previously won (for redistricting analysis)
  - Supports multiple incumbents per race (can occur with redistricting)
- **U.S. Senate seat handling**: Differentiates two Senate seats by Class (1 or 2) based on election year cycles, treating Class as district_id
- **Nested data structure**: Creates elections_candidates with nested candidate dataframes
- **Flattening via extract_summaries**: Pivots nested candidates to create election-row summary with flattened fields:
  - `{dem,gop,third_party,write_in}_{name,votes,percent,party,city_town,id}`
  - `{winner,incumbent}_{name,id,party,city_town}`
  - `num_incumbents` - count of incumbents in race
  - When multiple incumbents exist, selects the one who served in the same district for summary display
- Outputs:
  - `data/ma_general_election_summaries.csv.gz` - Flattened election summaries
  - `data/ma_general_election_candidates.csv.gz` - Candidates with incumbency flags
  - `data/ma_election_districts.csv` - Distinct district metadata

**Stage 3: Demographics (demographics/ma_census.R)**
- Queries the U.S. Census ACS 5-year API via `tidycensus`
- Uses areal interpolation (`sf::interpolate_pw` via `tidycensus`) to map
  block-group and tract geographies into the legislative districts defined
  by the GeoJSON files in `data/geometry/2021/`
- Classifies census tracts by household density ("very low", "low",
  "medium", "high"); aggregates to a district-level `density_type`
- All outputs carry a `census_year` column (currently `2024`) so multiple
  ACS vintages can coexist in the unified dataset
- Outputs:
  - `data/demographics/ma_district_demographics.csv.gz` - 217 rows, one
    per legislative district across all 4 offices, distinguished by an
    `office` column
  - `data/demographics/ma_precinct_demographics.csv.gz` - ~2,383 rows
  - `data/demographics/ma_city_town_demographics.csv.gz` - ~351 rows

**Stage 3.5: PVI (pvi/ma_pvi.R)**
- Reshapes already-computed PVI CSVs from a sibling mapoli checkout
  (`../mapoli/pvi/`) into the unified ma-election-db schema. Does not
  recompute PVI; mapoli is the current source-of-truth for the
  calculation
- Inputs:
  - `../mapoli/pvi/ma_state_leg_pvi_2008_2024.csv` - State Rep + State
    Senate PVI for 2008, 2012, 2016, 2020, 2022, 2024 (post-2021 district names)
  - `../mapoli/pvi/ma_legislative_district_pvi_2024.csv` - 2024 PVI for
    Governor's Council and U.S. House (the offices missing from the
    historical file)
- Renames `PVI_N`/`PVI` to `pvi_n`/`pvi` (snake_case)
- Output:
  - `data/pvi/ma_district_pvi.csv.gz` - ~1,217 rows, one per
    `(pvi_year, office, district)`

**Stage 3.6: Precincts (precinct/ma_precincts.R)**
- Reshapes mapoli's wide-format precinct CSVs into a normalized
  multi-vintage schema. Reads four files from the sibling mapoli
  checkout (`../mapoli/pvi/`)
- Inputs:
  - `../mapoli/pvi/ma_precincts_districts_12_16_pres.csv` (pre-2021 districts; 2012, 2016)
  - `../mapoli/pvi/ma_precincts_districts_16_20_pres.csv` (pre-2021 districts; 2016, 2020)
  - `../mapoli/pvi/ma_precincts_districts_pres_2022.csv` (post-2021 districts; 2016, 2020)
  - `../mapoli/pvi/ma_precincts_districts_pres_2024.csv` (post-2021 districts; 2016, 2020, 2024)
- Normalizes pre-2021 headers (`City/Town`, `Pct`, `State Rep`, ...) and
  post-2021 headers (`city_town`, `precinct`, `State_Rep`, ...) to a
  common snake_case schema
- Pivots candidate-named vote columns (`Biden_20`, `Harris_24`, ...)
  into long format keyed by `election_year`
- Within a redistricting cycle, where the same row appears in multiple
  files, keeps the most recent file's value
- National baseline totals are hardcoded in the script (lifted from
  `../mapoli/R/pvi_utils.R` plus 2012 from official certified results)
- Outputs:
  - `data/precinct/ma_precinct_district.csv.gz` - ~4,556 rows, one per
    `(redistricting_year, city_town, ward, precinct)`
  - `data/precinct/ma_precinct_presidential_vote.csv.gz` - ~13,666
    rows, one per `(election_year, redistricting_year, city_town, ward, precinct)`
  - `data/precinct/ma_national_presidential_baseline.csv` - 4 rows, one
    per presidential election year

**Stage 4: SQLite assembly (build_sqlite.R)**
- Deletes `data/ma_elections.sqlite` and rebuilds it from the CSVs
  produced by the other stages
- Single writer for the SQLite file - no other script opens the database
- Writes tables: `general_election`, `election_candidate`,
  `district_demographics`, `precinct_demographics`, `district_pvi`,
  `precinct_district`, `precinct_presidential_vote`,
  `national_presidential_baseline`, `district_summary`
- Creates unique indexes for the logical primary keys on the demographics,
  PVI, precinct, and summary tables (SQLite does not enforce composite
  PKs via `dbWriteTable`)

### Critical Data Quality Checks

**Candidate ID mapping (data/candidate-id-map.csv)**
- Manual mapping of duplicate candidate IDs to canonical IDs
- Applied globally in elections.R to ensure same person always has consistent ID
- Format: `id_dup,id_canonical,name_canonical,note`
- Required for correct incumbency detection when candidates have spelling variations

**Candidate duplicate detection (find_dup_candidates.py)**
- Uses fuzzy string matching (fuzzywuzzy) to find potential duplicate candidates with different IDs
- Manual review required - outputs to `data/possible-candidate-dupes.csv` for classification
- Confirmed duplicates go to `data/reported-duplicates.csv`
- **Not part of standard pipeline** - run manually to identify new duplicates, then add to `candidate-id-map.csv`

### Key Data Transformations

**Party abbreviation mapping** (elections.R:108-119, primary_elections.R:21-31)
- Democratic → D, Republican → R, Libertarian → L, etc.
- Standardization for Green-Rainbow variants

**Date fixes** (primary_elections.R:5-11)
- Corrects misaligned primary election dates in source data

**Senate seat classification** (elections.R:73-93, primary_elections.R:37-43)
- Class 1: (year - 1994) % 6 == 0, plus 2010-01-19 special
- Class 2: (year - 1990) % 6 == 0, plus 2013-06-25 special

## Data Model

### Incumbency Model

**Definition**: A candidate is incumbent if they won the most recent previous election (regular or special) for that office/district.

**Key features:**
- **Election-based**: Checks the most recent previous election (of any type) for each office/district
- **Office-specific**: Tracks by `(office_id, district_id)` where `district_id` differentiates U.S. Senate Classes
- **Special election handling**: Winners of special elections are marked as incumbents in subsequent elections
- **Career gap handling**: Candidates who did not win the most recent previous election are not incumbents
- **Multi-incumbent support**: Multiple incumbents can exist per race (e.g., after redistricting merges districts)
- **District tracking**: `district_id_prev` records which district incumbent previously won

**Special cases:**
- **Special elections**: Winners of special elections are marked as incumbents in the next election (regular or special)
- **Statewide offices**: Governor, President have `district_id = NA` but incumbency still calculated correctly
- **U.S. Senate**: Classes 1 and 2 treated as separate offices via `district_id` (1 or 2)
- **First cycles**: Elections in the first cycle per office (mostly 1990) are excluded from outputs as they lack incumbency data

**Output data range**: Starts from 1990-11-06 (State Senate) or 1992+ (most other offices), excluding first cycles

### Database Schema

**general_election table** (from election_summaries)
- Election metadata: office, district, date, special election flag
- Vote totals: total_votes, blank_votes, all_other_votes, num_candidates, num_incumbents
- Flattened candidate info: winner, incumbent, dem, gop, third_party, write_in
- Each candidate role has: id, name, display, city_town, votes, percent, party

**election_candidate table** (from candidates_w_inc)
- Links candidates to elections with full details
- Includes is_incumbent, is_winner, is_write_in, district_id_prev flags

## Dependencies

**Python:**
- Managed via pyproject.toml and uv package manager
- Core: pandas>=2.3.3, requests>=2.32.5
- Requires Python >=3.12
- Install with: `uv pip install -e .`
- fuzzywuzzy (for find_dup_candidates.py)

**R:**
- tidyverse (dplyr, tidyr, readr, stringr, purrr)
- lubridate
- DBI, RSQLite
- tidycensus, tigris, sf, here (demographics pipeline only)
- Managed via `renv` - run `renv::restore()` to install locked versions
- Demographics requires a `CENSUS_API_KEY` env var; set via `.Renviron` at
  repo root (gitignored). See `demographics/README.md`.

## Output Files

- `data/ma_general_election_summaries.csv.gz` - Analysis-ready election summaries (1 row per election)
- `data/ma_general_election_candidates.csv.gz` - All candidates with incumbency flags
- `data/demographics/ma_district_demographics.csv.gz` - District-level demographics (217 rows across 4 offices)
- `data/demographics/ma_precinct_demographics.csv.gz` - Precinct-level demographics
- `data/demographics/ma_city_town_demographics.csv.gz` - City/town-level demographics
- `data/pvi/ma_district_pvi.csv.gz` - Multi-year district PVI (~1,217 rows, `pvi_year` 2008-2024)
- `data/precinct/ma_precinct_district.csv.gz` - Precinct-to-district mapping by redistricting cycle (~4,556 rows)
- `data/precinct/ma_precinct_presidential_vote.csv.gz` - Precinct-level presidential votes 2012-2024 (~13,666 rows)
- `data/precinct/ma_national_presidential_baseline.csv` - National Dem/GOP totals per presidential election (4 rows, used by PVI calc)
- `data/district_summaries.csv` - LLM-generated narrative summary per district, keyed by `effective_date` (217 rows)
- `data/geometry/2021/*.geojson` - District and precinct boundaries for the 2021 redistricting cycle
- `data/ma_elections.sqlite` - Queryable database via [sqlime.org playground](https://sqlime.org/#https://bwbensonjr.github.io/ma-election-db/data/ma_elections.sqlite)

## SQLite Schema 

```sql
-- One row per general election
CREATE TABLE `general_election` (
  `office_branch` TEXT,
  `office_id` INTEGER,
  `office` TEXT,
  `district` TEXT,
  `district_display` TEXT,
  `district_id` INTEGER,
  `election_id` INTEGER,
  `election_date` TEXT,
  `is_special` INTEGER,
  `total_votes` INTEGER,
  `blank_votes` INTEGER,
  `all_other_votes` INTEGER,
  `num_candidates` INTEGER,
  `num_incumbents` INTEGER,
  `id_winner` INTEGER,
  `name_winner` TEXT,
  `display_winner` TEXT,
  `city_town_winner` TEXT,
  `votes_winner` INTEGER,
  `percent_winner` REAL,
  `party_winner` TEXT,
  `id_incumbent` INTEGER,
  `name_incumbent` TEXT,
  `display_incumbent` TEXT,
  `city_town_incumbent` TEXT,
  `party_incumbent` TEXT,
  `id_dem` INTEGER,
  `name_dem` TEXT,
  `display_dem` TEXT,
  `city_town_dem` TEXT,
  `votes_dem` INTEGER,
  `percent_dem` REAL,
  `id_gop` INTEGER,
  `name_gop` TEXT,
  `display_gop` TEXT,
  `city_town_gop` TEXT,
  `votes_gop` INTEGER,
  `percent_gop` REAL,
  `id_third_party` INTEGER,
  `name_third_party` TEXT,
  `display_third_party` TEXT,
  `city_town_third_party` TEXT,
  `votes_third_party` INTEGER,
  `percent_third_party` REAL,
  `party_third_party` TEXT,
  `id_write_in` INTEGER,
  `name_write_in` TEXT,
  `display_write_in` TEXT,
  `city_town_write_in` TEXT,
  `votes_write_in` INTEGER,
  `percent_write_in` REAL,
  `party_write_in` TEXT
);

-- District-level demographics: one row per (census_year, office, district).
-- The office column matches `general_election.office` for the 4 legislative
-- offices (State Representative, State Senate, Governor's Council, U.S. House).
-- A unique index enforces the logical composite key.
CREATE TABLE `district_demographics` (
  `census_year` INTEGER,
  `office` TEXT,
  `district` TEXT,
  -- ... ~115 demographic columns (see
  --     data/demographics/ma_district_demographics.csv.gz headers):
  --     total_population, race_{white,black,asian,hispanic,...},
  --     race_{...}_pct, median_age, median_household_income,
  --     ed_college_degree(_pct), ancestry_{...},
  --     below_poverty(_pct), wwc_pct, vote_eligible, density_type,
  --     area_m2, ...
  `area_m2` REAL,
  `density_type` TEXT
);
CREATE UNIQUE INDEX idx_district_demographics_pk
    ON district_demographics (census_year, office, district);

-- Precinct-level demographics: one row per (census_year, city_town, ward, precinct).
CREATE TABLE `precinct_demographics` (
  `census_year` INTEGER,
  `name` TEXT,
  `city_town` TEXT,
  `ward` TEXT,
  `precinct` TEXT,
  -- ... same demographic columns as district_demographics
  `area_m2` REAL
);
CREATE UNIQUE INDEX idx_precinct_demographics_pk
    ON precinct_demographics (census_year, city_town, ward, precinct);

-- District-level PVI: one row per (pvi_year, office, district).
-- Sourced from mapoli's already-computed PVI files; reshaped here.
-- pvi_n is numeric (positive = Dem lean); pvi is the display string ("D+5", "R+3", "EVEN").
CREATE TABLE `district_pvi` (
  `pvi_year` INTEGER,
  `office` TEXT,
  `district` TEXT,
  `district_display` TEXT,
  `pvi_n` REAL,
  `pvi` TEXT
);
CREATE UNIQUE INDEX idx_district_pvi_pk
    ON district_pvi (pvi_year, office, district);

-- Precinct-to-district mapping, keyed by redistricting cycle.
-- Pre-2021 districts use `redistricting_year = 2011`;
-- post-2021 districts use `redistricting_year = 2021`.
-- Ward is "-" for unwarded municipalities.
CREATE TABLE `precinct_district` (
  `redistricting_year` INTEGER,
  `city_town` TEXT,
  `ward` TEXT,
  `precinct` TEXT,
  `state_rep` TEXT,
  `state_senate` TEXT,
  `us_house` TEXT,
  `gov_council` TEXT
);
CREATE UNIQUE INDEX idx_precinct_district_pk
    ON precinct_district (redistricting_year, city_town, ward, precinct);

-- Precinct-level presidential votes. One row per
-- (election_year, redistricting_year, precinct). The same election year
-- may appear under both redistricting cycles where source data covers
-- both maps (e.g., 2016 votes mapped to pre-2021 vs post-2021 districts).
-- Vote totals are REAL because post-2021 split precincts hold
-- fractional totals after areal interpolation.
CREATE TABLE `precinct_presidential_vote` (
  `election_year` INTEGER,
  `redistricting_year` INTEGER,
  `city_town` TEXT,
  `ward` TEXT,
  `precinct` TEXT,
  `dem_votes` REAL,
  `gop_votes` REAL
);
CREATE UNIQUE INDEX idx_precinct_presidential_vote_pk
    ON precinct_presidential_vote
       (election_year, redistricting_year, city_town, ward, precinct);

-- National Dem/GOP totals per presidential election (used by PVI calc).
CREATE TABLE `national_presidential_baseline` (
  `election_year` INTEGER PRIMARY KEY,
  `dem_votes` INTEGER,
  `gop_votes` INTEGER
);

-- District summary text (LLM-generated narrative).
-- Keyed by effective_date so summaries can be revised after redistricting,
-- special elections, or other events without losing prior versions.
-- Lookup pattern: most recent effective_date <= target date (e.g., today).
CREATE TABLE `district_summary` (
  `office` TEXT,
  `district` TEXT,
  `effective_date` TEXT,    -- ISO 'YYYY-MM-DD'
  `summary` TEXT
);
CREATE UNIQUE INDEX idx_district_summary_pk
    ON district_summary (office, district, effective_date);

-- One row per candidate, per election 
CREATE TABLE `election_candidate` (
  `office_branch` TEXT,
  `office_id` REAL,
  `office` TEXT,
  `district` TEXT,
  `district_display` TEXT,
  `district_id` REAL,
  `election_id` INTEGER,
  `election_date` DATE,
  `party_primary` INTEGER,
  `is_special` INTEGER,
  `all_other_votes` REAL,
  `blank_votes` REAL,
  `total_votes` REAL,
  `first_cycle_date` DATE,
  `candidate_id` INTEGER,
  `name` TEXT,
  `first_name` TEXT,
  `middle_name` TEXT,
  `last_name` TEXT,
  `num_elections` INTEGER,
  `is_winner` INTEGER,
  `is_write_in` INTEGER,
  `num_votes` INTEGER,
  `party` TEXT,
  `street_addr` TEXT,
  `city_state` TEXT,
  `party_abbr` TEXT,
  `city_town` TEXT,
  `display` TEXT,
  `party_role` TEXT,
  `is_incumbent` INTEGER,
  `district_id_prev` REAL
);
```

### Office and District Values

| `office` | `office_id` | Example `district` values |
|---|---|---|
| President | 1 | *(no district)* |
| Governor | 3 | *(no district)* |
| U.S. House | 5 | `1`, `2`, ..., `10` |
| U.S. Senate | 6 | `Class 1`, `Class 2` |
| State Representative | 8 | `First Suffolk`, `Eighteenth Essex`, `Barnstable, Dukes and Nantucket` |
| State Senate | 9 | `First Essex`, `Cape and Islands`, `Berkshire, Hampshire, Franklin & Hampden` |
| Governor's Council | 529 | `First`, `Second`, ..., `Eighth` |

The `district_demographics.office` column uses the same four legislative
values as `general_election.office`: `State Representative`, `State Senate`,
`U.S. House`, `Governor's Council`.

## Extensibility Convention

New data domains (PVI, precinct-district mapping, precinct presidential
votes, district summaries, ...) follow a consistent shape so that each
addition is local and doesn't disturb existing pipelines:

1. **One subdirectory per domain at the repo root** (`demographics/`,
   later `pvi/`, `precinct_district/`, ...). Each owns its scripts and
   any static inputs (variable maps, etc.).
2. **Data outputs go under `data/<domain>/`** as gzipped CSVs. Include a
   year key column where the data is temporal: `census_year` for
   demographics, `pvi_year` for PVI, `redistricting_year` for precinct-
   district mapping and geometry. This lets new vintages be inserted as
   new rows rather than schema changes.
3. **Geometry goes under `data/geometry/<redistricting_year>/`** as
   GeoJSON (not in SQLite - SpatiaLite would break the sqlime.org
   playground).
4. **SQLite tables are added only by appending `dbWriteTable` calls to
   `build_sqlite.R`.** No domain script opens the SQLite file directly.
   Add a `CREATE UNIQUE INDEX` for the logical primary key after each
   `dbWriteTable` - SQLite does not enforce composite PKs via
   `dbWriteTable`.

See `../mapoli/DATA-UNIFICATION-PLAN.md` for the full roadmap of domains
still to migrate.
