# 2026 State General Election (`general_2026`)

Interim State Representative and State Senate results for the **November 3,
2026** Massachusetts general election, from the AP feed. Shared feed,
snapshot, normalization and verification behavior is described in
[`../README.md`](../README.md).

```bash
uv run python -m ap_results build general_2026          # from the snapshot
uv run python -m ap_results build general_2026 --fetch  # refresh first
```

Snapshot: `snapshots/ap_2026-11-03.json.gz`, taken 2026-11-04 20:01 UTC. One
feed request (no `party` parameter) returns every race on the ballot; only
`State House` and `State Senate` are kept. U.S. House, Governor's Council,
statewide offices and ballot questions are in the snapshot and can be added
by extending the event's `offices` in `events.py`.

Superseded once electionstats publishes certified results; see "Retiring an
event" in the shared README.

## Coverage on the current snapshot

| | State Rep | State Senate | Total |
|---|---|---|---|
| Seats | 160 | 40 | 200 |
| Contested | 47 | 10 | 57 |
| Uncontested | 113 | 30 | 143 |

- 190 races called, 10 `Too Early to Call` (9 State Rep, plus the First
  Bristol and Plymouth Senate seat).
- Called seats: 167 Democratic, 22 Republican, 1 Independent.
- 5 seats change hands versus the most recent prior winner, but one of them
  is an artifact. Susannah Whipps (Second Franklin) is listed as `Unenrolled`
  in electionstats and `Ind` by AP, so she shows up as a party change even
  though she held her own seat.
- 182 of 200 seats have the incumbent on the ballot.
- 544 municipality rows across 260 race-municipality pairs, 1,416,193 votes.

## Caveats

- **Uncontested seats** keep AP's declared winner but leave `votes_*`,
  `percent_*` and `total_votes` blank. AP reports them at 0 votes, and a 0
  would distort margins and averages. They are absent from the municipality
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

One row per (office, district): 200 rows. Columns follow `general_election`
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
