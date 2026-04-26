# Demographics

Builds district- and precinct-level demographic tables for Massachusetts
legislative districts from the U.S. Census American Community Survey (ACS)
5-year data.

## Inputs

- `demographics/census_vars.csv` - mapping of Census variable codes (e.g.
  `B01003_001`) to internal column names and geography.
- `data/geometry/2021/*.geojson` - district boundaries for State Rep, State
  Senate, Governor's Council, U.S. House, and MA precincts (wards/pcts/subs).
- Census ACS API (queried via the `tidycensus` R package).

## Outputs

| File | Rows | Description |
|------|------|-------------|
| `data/demographics/ma_district_demographics.csv.gz` | 217 | One row per legislative district across all 4 offices, distinguished by an `office` column. |
| `data/demographics/ma_precinct_demographics.csv.gz` | ~2,383 | One row per MA precinct. |
| `data/demographics/ma_city_town_demographics.csv.gz` | ~351 | One row per MA city/town (county subdivision). |

Each output carries a `census_year` column indicating the ACS 5-year vintage
used (currently `2024` = ACS 2020-2024).

## Running

### Prerequisites

1. An R environment with this project's `renv` packages installed
   (`renv::restore()`).
2. A U.S. Census API key. Get one free at
   <https://api.census.gov/data/key_signup.html>.

### Setting the API key

Add a `.Renviron` file at the repo root (already gitignored):

```
CENSUS_API_KEY=your_key_here
```

R auto-loads this on startup. `tidycensus::get_acs()` reads it via
`Sys.getenv("CENSUS_API_KEY")`.

### Running the pipeline

```bash
Rscript demographics/ma_census.R
```

First run takes 15-30 minutes because `tigris` downloads block/block-group/tract
geometries from the Census TIGER/Line files. Subsequent runs are faster because
`options(tigris_use_cache = TRUE)` caches those geometries locally.

### As part of the full build

```bash
make demographics   # just this pipeline
make all            # full rebuild (elections + demographics + sqlite)
```

## Bumping the ACS vintage

Edit the `census_year <- 2024` line at the top of `demographics/ma_census.R`.
The variable is used as both the ACS endpoint year and the value written into
the `census_year` column of all outputs, so historical vintages coexist cleanly
in the unified dataset.
