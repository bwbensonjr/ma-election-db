# Analysis queries

Standalone SQL against `data/ma_elections.sqlite`. Each file runs as-is:

```bash
sqlite3 -header -box data/ma_elections.sqlite < queries/incumbent_primary_challenges.sql
```

They also paste directly into the
[sqlime.org playground](https://sqlime.org/#https://bwbensonjr.github.io/ma-election-db/data/ma_elections.sqlite).

| File | What it returns |
|---|---|
| `incumbent_primary_challenges.sql` | One row per party primary where a sitting State Rep or State Senator faced a same-party challenger: margin, challenger, incumbent tenure, district PVI |
| `incumbent_primary_challenge_rates.sql` | Challenge and defeat rates by year and office, with every primary a sitting member ran in as the denominator |

## Deriving incumbency in a primary

`primary_election_candidate` has no `is_incumbent` column, so both queries
reconstruct it from `general_election`: a candidate is the sitting member if
they won the most recent general election (regular or special) for that
office/district before the primary date. This mirrors how `elections.R`
assigns incumbency for general elections.

Two things make this harder than it looks, and both queries handle them:

- **Retired district names.** Redistricting retires a district name, and a
  retired district never sees another general election. Testing only "has
  anyone won this district since?" therefore leaves a member's old seat
  looking permanently unresolved, and double-counts them as an incumbent
  years later. Paul Donato won Thirty-Eighth Middlesex in 2000 and
  Thirty-Fifth Middlesex from 2002 on; without ranking a candidate's wins by
  date first, he appears twice in his own 2024 primary. The queries take each
  candidate's most recent win, then ask whether it still stands.
- **District switching.** Matching is on office + candidate, not office +
  district, so a legislator renumbered into a new district is still
  recognized. `incumbent_district_prev` reports the district they last won,
  which is what makes redistricting-driven challenges findable.

## Counting the field

Write-ins are kept. Massachusetts primaries are winnable on a sticker
campaign -- Kenneth Gordon beat Rep. Charles Murphy in the 2012 Twenty-First
Middlesex Democratic primary as a write-in -- so filtering `is_write_in = 1`
drops real defeats. Instead every candidate counts toward the field, and
`challenger_percent`, `challenger_is_write_in`, and
`num_serious_challengers` (5% or more of the vote) separate a real challenge
from a handful of stray write-in votes.

## Known data limits

- **2006 and 2016 are incomplete.** Those primary cycles are badly
  under-collected upstream in `data/ma_primary_elections.csv.gz`: about 19
  State Rep incumbents on the ballot in 2006 against ~140 in a normal cycle.
  Read them as missing data, not quiet cycles. `make primary_elections`
  re-fetches from the state API if you want to try backfilling.
- **PVI joins only resolve for 2024.** `district_pvi` keys every vintage to
  post-2021 district names, so the queries restrict the join to 2022+. Within
  that, 42 of 160 State Rep names in the 2008-2022 vintages are mangled
  upstream in `../mapoli/pvi/ma_state_leg_pvi_2008_2024.csv`
  (`1Eighth Middlesex` for Eighteenth, `3Fifth Middlesex` for Thirty-Fifth),
  so those rows return a NULL PVI until the mapoli file is fixed.
- **State Senate district names disagree between tables.** The election
  tables write `First Plymouth & Norfolk`, `district_pvi` writes
  `First Plymouth and Norfolk`. The queries normalize `&` to `and` when
  joining PVI; anything else joining these tables needs the same treatment.
