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
