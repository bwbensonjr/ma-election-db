# 2026 State General Election (`general_2026`)

Interim results for the **November 3, 2026** Massachusetts general election,
from the AP feed: Governor, U.S. Senate, U.S. House, Governor's Council, State
Senate and State Representative. Shared feed,
snapshot, normalization and verification behavior is described in
[`../README.md`](../README.md).

```bash
uv run python -m ap_results build general_2026          # from the snapshot
uv run python -m ap_results build general_2026 --fetch  # refresh first
```

Snapshot: `snapshots/ap_2026-11-03.json.gz`, taken 2026-11-08 00:50 UTC. One
feed request (no `party` parameter) returns every race on the ballot. The
event keeps the offices the database schema knows: Governor, U.S. Senate,
U.S. House, Governor's Council, State Senate and `State House`. Other
statewide offices (Secretary of State, Attorney General, Treasurer, Auditor),
District Attorneys and ballot questions are in the snapshot but outside the
schema.

Superseded once electionstats publishes certified results; see "Retiring an
event" in the shared README.

## Coverage on the current snapshot

| | Governor | U.S. Senate | U.S. House | Gov Council | State Senate | State Rep | Total |
|---|---|---|---|---|---|---|---|
| Seats | 1 | 1 | 9 | 8 | 40 | 160 | 219 |
| Contested | 1 | 1 | 6 | 3 | 10 | 47 | 68 |
| Uncontested | 0 | 0 | 3 | 5 | 30 | 113 | 151 |

- 218 races called, 1 `Too Early to Call` (Second Plymouth State Rep).
- Called seats: 191 Democratic, 26 Republican, 1 Independent.
- 6 seats change hands versus the most recent prior winner, but one of them
  is an artifact. Susannah Whipps (Second Franklin) is listed as `Unenrolled`
  in electionstats and `Ind` by AP, so she shows up as a party change even
  though she held her own seat.
- 200 of 219 seats have the incumbent on the ballot.
- 3,849 municipality rows across 1,358 race-municipality pairs, 9,403,314
  votes.

## Caveats

- **Uncontested seats** keep AP's declared winner but leave `votes_*`,
  `percent_*` and `total_votes` blank. AP reports most of them at 0 votes, and
  a 0 would distort margins and averages. AP does tabulate the three
  uncontested U.S. House races (2nd, 5th, 7th); those counts stay in the raw
  snapshot only. They are absent from the municipality
  file.
- **Uncalled races** have blank `*_winner` columns. `race_call_status` says
  why. Check `precincts_reporting_pct` before reading anything into the
  margin.
- **Totals exclude blanks and write-ins.** `total_votes` is the sum of named
  candidates, so `percent_*` runs slightly above what `general_election` will
  show for the same race once certified.
- **Party codes.** AP `Oth` becomes `Other`. AP does not say which minor
  party it means. `Unr` and `Ind` map to Unenrolled and Independent, but AP
  and electionstats do not always agree on which label a candidate gets.
- `candidate_id` and `candidate_city_town` come from matching Democratic and
  Republican candidates to this cycle's primary winners in
  `data/ma_primary_election_candidates.csv.gz`. Every D/R candidate on the
  current snapshot matched. Unenrolled, Independent and Other candidates have
  neither.

## Incumbency

Incumbency follows the shared rule: the incumbent is the most recent prior
winner of the seat, and the candidate is flagged by name match. It uses the
2026 cycle's two overrides, Joanne M. Comerford and Brandy Fluker Reid. With
those overrides in place, AP's incumbent flag agrees with ours on every
candidate.

## `ma_general_2026_races.csv.gz`

One row per (office, district): 219 rows. Governor has a blank `district`
and `district_id`; U.S. Senate is `Class 2`. Columns follow `general_election`
where an equivalent exists.

- `election_date` (`2026-11-03`), `is_special` (`0`)
- `office_branch`, `office_id`, `office`, `district`, `district_display`,
  `district_id` - match `general_election`
- `ap_race_id`, `is_uncontested`, `num_candidates`, `total_votes`
- `precincts_reporting`, `precincts_total`, `precincts_reporting_pct`,
  `eevp` - district-wide
- `race_call_status` (`Called`, `Too Early to Call`), `results_final`
- `{id,name,party,votes,percent}_winner`
- `{id,name,party}_incumbent` - the incumbent *if on the ballot*, as in
  `general_election`; blank for open seats
- `{id,name,votes,percent}_dem`, `{id,name,votes,percent}_gop`
- `{id,name,party,votes,percent}_third_party` - the highest-vote candidate
  who is neither D nor R
- `incumbent_running`
- `prior_winner_{name,id,party}`, `prior_election_date` - who last won the
  seat (general or special), whether or not they ran again
- `last_updated`, `snapshot_time`

`id_*` are electionstats candidate ids (blank where unmatched). `party_*` are
full party names as in `general_election`; `percent_*` are 0-1 fractions of
`total_votes`.

## `ma_general_2026_results.csv.gz`

One row per (office, district, municipality, candidate) for the 57 contested
races: 544 rows. Same columns as the primary results file, with these
differences:

- `party`, `party_abbr` are the candidate's own party, and `party_ap` is the
  raw AP code
- `candidate_id` is the electionstats id (see caveats)
- `is_race_winner` is AP's district-level call, repeated on every
  municipality row of the race. It is not a per-municipality result.

Race-level candidate votes equal the sum of that candidate's municipality
rows, and the build checks this.

## `ma_general_2026_forecast_comparison.csv.gz`

The 57 contested races joined to the 2026 legislative forecast from the
`election-modeling` repo (14d-r2 snapshot, money cutoff 2026-10-20). Built
from the general results above:

```bash
uv run python -m ap_results.general_2026.forecast_compare
```

The forecast inputs in `forecast/` are copies of the files pinned by the
massnumbers blog post `posts/2026-10-29-contested-races` (blog commit
`703da84`). The 14d-r2 snapshot is not checked in to `election-modeling`
itself. `forecast_14d_r2_intervals.csv` holds the 75% intervals the post
derived from the snapshot's per-race draws.

`actual_margin` uses the model's definition: the Democrat's margin in points
against the comparison candidate (the Republican, or the strongest
non-Democrat where no Republican ran) on that pair's own votes,
`100 * (D - comparison) / (D + comparison)`. Votes for any other candidate
are in `other_votes` and left out of the margin.

Columns:

- `target_id`, `office`, `district`, `district_display`, `district_id`
- Forecast inputs: `PVI_N`, `incumbent_status`, `ballot_timing`,
  `dem_candidate_*`, `comparison_candidate_*`, and receipts and expenditures
  for each side through the cutoff
- Forecast: `forecast_margin` (point estimate), `lower_75`/`upper_75`,
  `lower_90`/`upper_90`, `dem_win_probability`, `forecast_dem_favored`
- AP results: `race_call_status`, `is_called`, `precincts_reporting_pct`,
  `eevp`, `dem_votes`, `comparison_votes`, `other_votes`, `actual_margin`,
  `dem_leading`, `name_winner`, `party_winner`
- Scoring: `dem_won` and `forecast_correct` (blank until AP calls the race),
  `margin_error` (actual minus forecast), `in_75`, `in_90`, and `brier`
  (`(dem_win_probability - dem_won)^2`, blank until called)

On the 2026-11-04 20:01 UTC snapshot, 47 of the 57 races are called. The
favored side won 45 of the 47; the misses were 22nd Middlesex (14% Dem, Dem
won) and 8th Bristol (57% Dem, Rep won). Margin error averages +2.9 points
toward Democrats, with an RMSE of 8.4. 51 of 57 results fall inside the 75%
interval and 56 inside the 90% interval. The Brier score on called races is
0.040.
