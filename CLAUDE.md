# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Massachusetts Election Database - Tools for querying MA election results from electionstats.state.ma.us and producing a structured database of elections and candidates from 1990-2024.

The project follows a two-stage data pipeline:
1. **Python extraction** (election_stats.py) - Queries raw election data from the MA state API
2. **R transformation** (elections.R) - Processes raw data into analysis-ready formats and SQLite database

## Common Commands

### Full data pipeline
```bash
# Extract election data from state API (takes several minutes)
python election_stats.py

# Transform and summarize into database (takes a few minutes)
Rscript elections.R
```

### Primary elections processing (work in progress)
```bash
# Process primary election data
Rscript primary_elections.R
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
  - `data/ma_elections.sqlite` - SQLite database with tables: general_election, election_candidate

### Critical Data Quality Checks

**Candidate duplicate detection (find_dup_candidates.py)**
- Uses fuzzy string matching (fuzzywuzzy) to find potential duplicate candidates with different IDs
- Manual review required - outputs to `data/possible-candidate-dupes.csv` for classification
- Confirmed duplicates go to `data/reported-duplicates.csv`

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
- pandas, requests (see requirements.txt)
- fuzzywuzzy (for find_dup_candidates.py)

**R:**
- tidyverse (dplyr, tidyr, readr, stringr, purrr)
- lubridate
- DBI, RSQLite

## Output Files

- `data/ma_general_election_summaries.csv.gz` - Analysis-ready election summaries (1 row per election)
- `data/ma_general_election_candidates.csv.gz` - All candidates with incumbency flags
- `data/ma_elections.sqlite` - Queryable database via [sqlime.org playground](https://sqlime.org/#https://bwbensonjr.github.io/ma-election-db/data/ma_elections.sqlite)
