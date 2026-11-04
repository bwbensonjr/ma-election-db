# Interim AP Election Results

Certified results take weeks to reach electionstats.state.ma.us. In the
meantime this package pulls the Associated Press feed behind the Boston
Globe's election coverage, snapshots it, and normalizes it to ma-election-db
conventions. Each election is an **event** with its own subdirectory.

| Event | Date | Outputs (`data/ap_results/<event>/`) |
|---|---|---|
| [`primary_2026`](primary_2026/README.md) | 2026-09-01 | `ma_primary_2026_candidates.csv.gz`, `ma_primary_2026_results.csv.gz` |

## Build

```bash
uv run python -m ap_results list                        # registered events
uv run python -m ap_results build general_2026          # from checked-in snapshots, no network
uv run python -m ap_results build general_2026 --fetch  # refresh snapshots from the live feed first
```

None of this runs under `make all` and nothing is written to
`data/ma_elections.sqlite`. These are interim numbers that certified
electionstats results supersede.

## Layout

```
ap_results/
  __main__.py              CLI
  events.py                event registry (date, stage, feed requests, offices, overrides)
  feed.py                  fetch, snapshot I/O, reporting-unit helpers
  normalize.py             office, district, party and name normalization
  incumbency.py            most-recent-prior-winner lookup and name matching
  verify.py                fail-loud integrity checks
  district_reference.csv   2021-cycle districts, shared by every 2022-2030 event
  <event>/
    README.md              event-specific notes and columns
    *.py                   the event's output shaping
    snapshots/             gzipped raw AP responses, checked in
```

## Source

```
https://elections-api.bostonglobe.com/v2/elections/<date>?statePostal=MA&level=ru[&party=dem|gop]
```

Public and unauthenticated. Primaries need one request per party; a general
returns every race in a single request. `level=ru` is what produces sub-state
rows; `level` accepts only `ru` and `fipscode`, and `fipscode` returns nothing
for Massachusetts.

## Granularity

The finest grain is the **municipality within a district**
(`reportingunitLevel == 2`). There is no ward or precinct tier. A city split
across several districts appears once per district holding only that
district's precincts, so `city_town` rows are district-specific and must not
be summed across races to get a citywide total.

AP does not tabulate uncontested races: it reports them with every
`voteCount` at 0.

AP reports named candidates only, without blank ballots or write-ins, so its
vote totals and percentages run slightly different from the certified ones.

## Snapshots

The feed mutates in place, so every build reads the gzipped raw responses in
`<event>/snapshots/ap_<date>[_<party>].json.gz`. Refresh with `--fetch` and
commit each refresh (`data: refresh 2026 general results to <time> UTC
snapshot`). A fetch that returns no races aborts without overwriting the
existing snapshot.

## Normalization

`office`, `office_id`, `office_branch`, `district`, `district_display` and
`district_id` follow `general_election`, so outputs join directly to
`district_demographics`, `district_pvi` and the historical tables.

- AP `officeName` `State House` becomes `State Representative`.
- AP `seatName` arrives in display form (`"18th Essex"`); Governor's Council
  and U.S. House arrive as `"District N"`. Seats resolve through
  `district_reference.csv` under either the canonical or display spelling,
  treating `&` and `and` as equal.
- AP party codes map `Dem` -> Democratic/D, `GOP` -> Republican/R,
  `Unr` -> Unenrolled/U, `Ind` -> Independent/I; other codes become `Other`.
- U.S. Senate carries its Class (from the election year) as the district.

## Incumbency

The incumbent for a race is the winner of the most recent prior general or
special election for that `(office_id, district_id)` in
`data/ma_general_election_summaries.csv.gz`. AP carries no electionstats IDs,
so a candidate is flagged by first+last name match within the race. Matches
name-matching cannot make (nicknames, surname changes) go in the event's
`incumbent_overrides` in `events.py`. AP's own incumbent flag is kept as
`is_incumbent_ap`, and disagreements are printed as warnings.

## Verification

Builds fail without writing output if any in-scope seat does not resolve, if
a candidate's municipality votes do not sum to AP's race total, if
municipality precinct counts do not sum to the race total, or if an output
key repeats.

## Adding an event

1. Add an `Event` to `events.py`: name, date, stage, `feed_params`,
   in-scope AP offices, and `builder` (a module exposing
   `build(event, fetch)`). Reuse an existing stage's builder by reference
   when the shape matches; `general_2026.results` is written against the
   general stage, not the year.
2. Create `ap_results/<event>/` with a README.
3. `uv run python -m ap_results build <event> --fetch` and commit the
   snapshot and outputs.

If a redistricting changes the district map, give the new events their own
reference file rather than editing `district_reference.csv`.

## Retiring an event

Once electionstats carries certified results, run `make general_elections`
(or `make primary_elections`) and `make all`, reconcile winners and contested
race counts against the AP outputs, and record the comparison in the commit
message (see `bb32fc2` for the 2026 primary). Leave the AP files in place as a
record of what was known when.
