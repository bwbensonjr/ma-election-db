# Precinct

Reshapes mapoli's wide-format precinct CSVs into a normalized
multi-vintage schema. Produces three outputs that together let downstream
consumers (e.g., PVI calculation) operate from ma-election-db alone
without going back to mapoli.

This pipeline does not compute PVI itself. The district-level PVI values
are still produced by mapoli and reshaped by `pvi/ma_pvi.R`. What this
pipeline publishes is the precinct-level inputs needed to recompute PVI
from scratch.

## Inputs

Read from a sibling mapoli checkout at `../mapoli/pvi/`:

| File | Redistricting | Elections present |
|------|---------------|-------------------|
| `ma_precincts_districts_12_16_pres.csv` | 2011 (pre-2021) | 2012, 2016 |
| `ma_precincts_districts_16_20_pres.csv` | 2011 (pre-2021) | 2016, 2020 |
| `ma_precincts_districts_pres_2022.csv`  | 2021            | 2016, 2020 |
| `ma_precincts_districts_pres_2024.csv`  | 2021            | 2016, 2020, 2024 |

Pre-2021 files use headers like `City/Town`, `Ward`, `Pct`, `State Rep`;
post-2021 files use `city_town`, `ward`, `precinct`, `State_Rep`. The
script normalizes both to common snake_case columns.

Vote columns are candidate-named (`Biden_20`, `Trump_24`, `Clinton_16`,
...). The script pivots them into long format keyed by `election_year`.

National baseline totals are hardcoded in `ma_precincts.R`, lifted from
`../mapoli/R/pvi_utils.R` (2016, 2020, 2024) plus 2012 official certified
totals.

## Outputs

| File | Rows | Description |
|------|------|-------------|
| `data/precinct/ma_precinct_district.csv.gz` | ~4,556 | One row per `(redistricting_year, city_town, ward, precinct)`. Maps each precinct to its `state_rep`, `state_senate`, `us_house`, `gov_council` district under that redistricting cycle. |
| `data/precinct/ma_precinct_presidential_vote.csv.gz` | ~13,666 | One row per `(election_year, redistricting_year, city_town, ward, precinct)` with `dem_votes` and `gop_votes`. Vote totals are REAL because post-2021 split precincts hold fractional totals after areal interpolation. |
| `data/precinct/ma_national_presidential_baseline.csv` | 4 | National Dem/GOP totals for 2012, 2016, 2020, 2024. |

## Dedup convention

Within a redistricting cycle, where the same row appears in multiple
files, the most recent file wins:

- For `precinct_district`: `_16_20_pres` over `_12_16_pres`;
  `_pres_2024` over `_pres_2022`.
- For `precinct_presidential_vote`: same precedence applied per
  `(election_year, precinct)`.

The same `election_year` may legitimately appear under both
redistricting cycles when source files cover both maps (e.g., 2016
votes are present mapped to pre-2021 districts in `_16_20_pres` AND
mapped to post-2021 districts in `_pres_2024`). Both are preserved.

## Running

```bash
Rscript precinct/ma_precincts.R   # just this pipeline
make precincts                    # via Makefile
make all                          # full rebuild including this stage
```

Requires the mapoli repo checked out at `../mapoli`. No Census API key
or external API access is needed.
