# PVI

Builds a multi-year district-level Partisan Voting Index (PVI) table for
Massachusetts legislative districts.

PVI compares a district's two-cycle average presidential vote against the
national two-cycle average. It is recalculated every 4 years after each
presidential election.

## Source of truth

The PVI calculation itself currently lives in the
[mapoli](https://github.com/bwbensonjr/mapoli) repo
(`pvi/ma_pvi_2024.R`, plus shared utilities in `R/pvi_utils.R` and
`R/precinct_utils.R`). This pipeline reads mapoli's already-computed PVI
CSVs and reshapes them into the unified ma-election-db schema. It does
not recompute PVI.

## Inputs

Read from a sibling mapoli checkout at `../mapoli/pvi/`:

- `ma_state_leg_pvi_2008_2024.csv` - State Representative + State Senate
  PVI for `pvi_year` in 2008, 2012, 2016, 2020, 2022, 2024 (1,200 rows;
  districts are post-2021 names).
- `ma_legislative_district_pvi_2024.csv` - 2024 PVI for all 4
  legislative offices (217 rows). Only the Governor's Council and U.S.
  House rows are taken from this file; State Rep and State Senate rows
  for 2024 already appear in the historical file above.

## Outputs

| File | Rows | Description |
|------|------|-------------|
| `data/pvi/ma_district_pvi.csv.gz` | ~1,217 | One row per (`pvi_year`, `office`, `district`). |

Schema:

| Column | Type | Notes |
|--------|------|-------|
| `pvi_year` | INTEGER | Year of the most recent presidential election in the calculation window. |
| `office` | TEXT | Canonical office name (`State Representative`, `State Senate`, `Governor's Council`, `U.S. House`). |
| `district` | TEXT | District name as used in `general_election.district`. |
| `district_display` | TEXT | Short display variant (e.g. `10th Bristol`). |
| `pvi_n` | REAL | Numeric PVI; positive = Dem lean, negative = Rep lean. |
| `pvi` | TEXT | Display PVI (`D+15`, `R+3`, `EVEN`). |

In the SQLite database the same data lives in the `district_pvi` table
with a unique index on (`pvi_year`, `office`, `district`).

## Running

```bash
make pvi              # just this pipeline
make all              # full rebuild (elections + demographics + pvi + sqlite)
```

The script fails fast if `../mapoli/pvi/...` is not present.

## Adding a new PVI vintage

After the next presidential election, mapoli will produce
`ma_state_leg_pvi_2008_2028.csv` (or similar) and an updated
`ma_legislative_district_pvi_2028.csv`. Update the file paths near the
top of `pvi/ma_pvi.R` and re-run `make pvi`. New rows will be inserted
under the new `pvi_year`; older rows are preserved.

## Out of scope (for now)

- `national_presidential_baseline` table - the hardcoded national totals
  in `mapoli/R/pvi_utils.R` are not yet stored in the database.
- `precinct_district` and `precinct_presidential_vote` tables - precinct-
  level inputs to PVI are still consumed directly in mapoli.
- Pre-2021 redistricting vintages - all rows currently use post-2021
  district names. Adding earlier district maps would require a
  `redistricting_year` column.
