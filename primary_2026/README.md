# 2026 State Primary Candidates

One row per candidate on the ballot for the **September 1, 2026** Massachusetts
state primaries, for the six offices ma-election-db tracks: U.S. Senate,
Governor, U.S. House, Governor's Council, State Senate, and State
Representative. County-level offices listed on the source pages (Lieutenant
Governor, Attorney General, Secretary, Treasurer, Auditor, District Attorney,
Register of Probate, County Treasurer/Commissioner, Sheriff) are intentionally
excluded, since they are outside the existing schema.

Districts with no nominations for a party produce no rows.

## Sources

Transcribed from the Secretary of the Commonwealth candidate-listing pages
(fetched 2026-07-20):

- Democratic: <https://www.sec.state.ma.us/divisions/elections/research-and-statistics/dem-state-primary-candidates2026.htm>
- Republican: <https://www.sec.state.ma.us/divisions/elections/research-and-statistics/rep-state-primary-candidates2026.htm>

## Inputs (checked in)

- `candidates_2026_raw.txt` - the transcribed candidate list in a small
  line-based format (`[Party]` / `$ Office` / `@ District` / `Name, City`).
  This is the human-auditable source of truth; edit it to correct or update
  candidates, then re-run the build.
- `district_reference.csv` - the current-cycle district metadata
  (`office`, `district`, `district_display`, `district_id`) as the DB records
  it, derived from the 2022/2024 general-election summaries. Used to attach
  canonical district names and IDs.
- `data/ma_general_election_summaries.csv.gz` (produced by `elections.R`) -
  read at build time to determine the incumbent (most recent prior winner)
  for each race. The build depends on this file existing.

## Build

```bash
uv run python primary_2026/build_primary_2026.py
```

Output: `data/primary_2026/ma_primary_2026_candidates.csv.gz` (340 rows).

## Conventions and notes

- `office` / `office_id` / `office_branch` match `general_election`.
- **U.S. Senate**: 2026 is a Class 2 cycle (`(2026 - 1990) % 6 == 0`, per
  `elections.R`), so `district = "Class 2"`, `district_id = 2`.
- **Governor**: statewide, so `district`/`district_display`/`district_id` are
  blank.
- District names on the SEC pages use an inconsistent mix of `&` and `and`.
  The build joins them to the DB's canonical spelling using an
  `&`/`and`-insensitive key; the raw SEC spelling is preserved in the
  `district_sec` column for traceability. `district` holds the canonical DB
  spelling. The build fails loudly if any district fails to match.
- `city_town` is the candidate's city of residence (the text after the last
  comma on each source line, so name suffixes like `, Jr.` / `, III` stay in
  `name`).
- `display` is `"<name> (<party_abbr>)"`, matching `election_candidate.display`.
- `is_special = 0` (regular primary). No vote totals - these are nominations,
  not results.

## Incumbency

The **incumbent** for a race is the winner of the most recent prior general OR
special election for the same `(office_id, district_id)` (matching the
ma-election-db incumbency definition). This correctly picks up special-election
winners - e.g. Vanna Howard, who won the First Middlesex *Senate* seat in the
2026-03-03 special, is the incumbent for that 2026 primary.

Every race has a known incumbent. Because the SEC pages carry no electionstats
candidate IDs, `is_incumbent` is set by matching the candidate's name to the
prior winner's name **within the race**, comparing first+last (dropping middle
names/initials and suffixes). This resolves the common formatting differences
("Tara Thorn Hong" -> "Tara Hong", "William Macgregor" -> "William F.
MacGregor"). Two incumbents that name-matching cannot catch (a nickname and a
surname change) are handled by `INCUMBENT_OVERRIDES` in the build script:

- `Jo Comerford` -> `Joanne M. Comerford` (State Senate, Hampshire, Franklin
  and Worcester)
- `Brandy Fluker Oakley` -> `Brandy Fluker Reid` (State Representative, Twelfth
  Suffolk)

Result: 201 candidates flagged `is_incumbent`; 17 of 218 races are open seats
where the incumbent is not running (retired, or running for another office -
e.g. Seth Moulton vacating U.S. Senate Class 2, Vanna Howard having moved from
her House seat to the Senate).

## Columns

- `party`, `party_abbr` - `Democratic`/`Republican`, `D`/`R`
- `office_branch`, `office_id`, `office` - match `general_election`
- `district`, `district_display`, `district_id` - canonical DB district
  (blank for Governor)
- `district_sec` - district name exactly as printed on the SEC page
- `election_date` (`2026-09-01`), `is_special` (`0`)
- `name`, `display` (`"<name> (<abbr>)"`), `city_town`
- `is_incumbent` - 1 if this candidate is the incumbent of this seat
- `incumbent_running` - 1 if the incumbent is among this race's candidates
  (i.e., the seat is being defended)
- `incumbent_name`, `incumbent_party`, `incumbent_id` - the incumbent's name,
  party, and electionstats candidate id (the id links back to
  `election_candidate.candidate_id`)
- `incumbent_election_date` - date the incumbent last won the seat

---

# 2026 State Primary Results (municipality level)

Preliminary results for the September 1, 2026 primaries, one row per
**(party, office, district, municipality, candidate)**.

Output: `data/primary_2026/ma_primary_2026_results.csv.gz` (2,751 rows).

## Source

The Associated Press election feed that backs the Boston Globe's 2026 primary
coverage. It is public and unauthenticated:

```
https://elections-api.bostonglobe.com/v2/elections/2026-09-01?statePostal=MA&party={dem,gop}&level=ru
```

Two requests cover the whole state. The `level=ru` parameter is what produces
sub-state rows; `level` accepts only `ru` and `fipscode`, and `fipscode`
returns nothing for Massachusetts.

## Granularity

The finest grain the feed offers is the **municipality within a district**
(`reportingunitLevel == 2`). There is no ward or precinct tier.

A city split across several districts appears once per district, holding only
that district's precincts - Boston shows up in 16 separate Democratic State
House races, and its per-race precinct counts sum to the citywide 275. So
`city_town` rows are district-specific and must not be summed across races to
get a citywide total.

## Coverage, and the uncontested-race caveat

**AP does not tabulate uncontested primaries.** It reports them with every
`voteCount` at 0. Of 282 race records (212 Democratic, 70 Republican), 224 are
uncontested and carry no real data, so the build drops them.

What remains is **54 contested races** across the six offices ma-election-db
tracks - 48 Democratic, 6 Republican - covering 1,269 race-municipality rows
and about 2.48M votes. Four further contested races are excluded as
out-of-schema: Democratic District Attorney (Suffolk, Norfolk) and Republican
Lieutenant Governor and Secretary of State.

## Snapshots

Results are preliminary and the upstream feed mutates in place. The raw
responses are snapshotted to `primary_2026/snapshots/ap_2026-09-01_{dem,gop}.json.gz`
(~220 KB total) and checked in, so the CSV is reproducible from the repo
alone. The build reads the snapshots by default.

## Build

```bash
# rebuild from the checked-in snapshots (no network)
uv run python primary_2026/build_primary_2026_results.py

# refresh the snapshots from the live feed, then rebuild
uv run python primary_2026/build_primary_2026_results.py --fetch
```

Depends on `data/primary_2026/ma_primary_2026_candidates.csv.gz`, so run
`build_primary_2026.py` first.

## Verification

The build fails loudly rather than writing suspect data. It checks that each
candidate's municipality votes sum exactly to AP's own statewide total for the
race, that per-municipality precinct counts sum to the race total (this is what
confirms split cities are counted once per district), that every district
resolves against `district_reference.csv`, and that no
(party, office, district, municipality, candidate) key repeats. All four hold
on the current snapshot.

It also warns, without failing, when a candidate does not match the
nominations dataset or when AP's incumbency flag disagrees with ours. On the
current snapshot there are none of either: all 2,751 rows joined, and AP and
`ma_primary_2026_candidates.csv.gz` agree on every incumbent.

## Joining to the rest of the database

`office`, `office_id`, `office_branch`, `district`, `district_display`, and
`district_id` follow the same conventions as `general_election`, so results
join directly to `district_demographics`, `district_pvi`, and the historical
election tables.

AP's `seatName` arrives in display form (`"18th Essex"`, `"District 6"`,
`"Class II"`), which is why `build_reference()` in `build_primary_2026.py` now
keys each district under both its canonical name and its `district_display`.
Governor's Council and U.S. House `"District N"` values and the U.S. Senate
`"Class II"` are normalized in this script.

## Not in SQLite

These are preliminary numbers that official electionstats results will
supersede, so there is no `build_sqlite.R` table and no `Makefile` target yet.
Add both once the results are final.

## Columns

- `election_date` (`2026-09-01`), `is_special` (`0`)
- `party`, `party_abbr` - `Democratic`/`Republican`, `D`/`R`
- `office_branch`, `office_id`, `office` - match `general_election`
- `district`, `district_display`, `district_id` - canonical DB district
  (blank for Governor)
- `city_town` - the municipality the votes come from, within this district
- `county_fips`, `town_fips` - AP's FIPS codes for the county and municipality
- `precincts_reporting`, `precincts_total`, `precincts_reporting_pct` - for
  this municipality's portion of the district
- `candidate_name`, `first_name`, `middle_name`, `last_name`
- `ap_candidate_id` - AP `polID`; there is no electionstats id for these yet
- `candidate_city_town` - the candidate's city of residence (distinct from
  `city_town`, which is where the votes were cast)
- `is_incumbent` - from the nominations dataset
- `is_incumbent_ap` - AP's own flag, kept for cross-checking
- `is_race_winner` - AP's district-level call, repeated on every municipality
  row of the race; it is not a per-municipality result
- `votes` - this candidate's votes in this municipality
- `town_total_votes` - all candidates' votes in this municipality for this race
- `percent` - `votes / town_total_votes`, a 0-1 fraction matching the
  `percent_*` convention in `general_election`; blank where no votes are in yet
- `ap_race_id`, `eevp` - AP race id and expected-vote-percent
- `race_call_status`, `results_final` - AP's call status and whether the
  statewide unit is final
- `last_updated` - when AP last updated this municipality
- `snapshot_time` - when the snapshot this row was built from was taken
