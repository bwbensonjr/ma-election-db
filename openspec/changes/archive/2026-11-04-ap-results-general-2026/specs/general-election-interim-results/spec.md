# Spec Delta

## Purpose

Delivers interim race-level and municipality-level general-election results
for State Representative and State Senate from the AP feed, in shapes that
line up with `general_election` and the 2026 primary results, until certified
results reach electionstats.

## ADDED Requirements

### Requirement: General 2026 event scope
The `general_2026` event SHALL cover the 2026-11-03 general election for
State Representative (AP `State House`) and State Senate only, with
`election_date = "2026-11-03"` and `is_special = 0` on every row.

#### Scenario: Seat coverage
- **WHEN** `general_2026` is built from a snapshot that lists all 160 State
  House and 40 State Senate races
- **THEN** the race-level output has exactly 200 rows, one per district

### Requirement: Race-level output
The system SHALL write `data/ap_results/general_2026/ma_general_2026_races.csv.gz`
with one row per (office, district), carrying winner, Democratic, Republican
and highest-vote third-party candidate fields (name, votes, percent, party)
named like `general_election`.

#### Scenario: Contested race
- **WHEN** AP reports a Democrat with 9,068 votes and a Republican with 6,490
  in 3rd Bristol and calls the Democrat
- **THEN** that row has `votes_dem = 9068`, `votes_gop = 6490`,
  `percent_dem` about 0.583 as a 0-1 fraction, and `name_winner` set to the
  Democrat

#### Scenario: Three-candidate race
- **WHEN** a race has a Democrat, a Republican and an Unenrolled candidate
- **THEN** the Unenrolled candidate fills the `*_third_party` columns with
  `party_third_party = "Unenrolled"` (full party names, as in
  `general_election`)

### Requirement: Uncontested seats
Uncontested races SHALL appear in the race-level output with
`is_uncontested = 1`, the AP-declared winner populated, and vote and percent
columns left blank rather than zero. They SHALL NOT appear in the
municipality-level output.

#### Scenario: AP zero-vote uncontested race
- **WHEN** AP reports 26th Middlesex as uncontested with one candidate at 0
  votes and marked winner
- **THEN** the race row has `is_uncontested = 1`, that candidate as
  `name_winner`, and blank `votes_winner` and `percent_winner`

### Requirement: Uncalled races
Races AP has not called SHALL have blank winner columns, and the race row
SHALL carry AP's `race_call_status`.

#### Scenario: Too early to call
- **WHEN** a race's `raceCallStatus` is `"Too Early to Call"`
- **THEN** its `name_winner` is blank and `race_call_status` is
  `"Too Early to Call"`

### Requirement: Municipality-level output
The system SHALL write `data/ap_results/general_2026/ma_general_2026_results.csv.gz`
with one row per (office, district, municipality, candidate) for contested
races, using the columns of the primary results file, with `party` holding
each candidate's own party.

#### Scenario: City split across districts
- **WHEN** Boston appears in several State House races
- **THEN** each race has its own Boston rows containing only that district's
  precincts and votes

### Requirement: Party normalization
AP party codes SHALL map to the database's party names and abbreviations:
`Dem` to Democratic/D, `GOP` to Republican/R, `Unr` to Unenrolled/U, `Ind`
to Independent/I, and any other code to `Other`.

#### Scenario: Unmapped AP party code
- **WHEN** a candidate's AP party is `"Oth"`
- **THEN** `party_abbr` is `"Other"` and the raw AP code is kept in
  `party_ap`

### Requirement: Incumbency
Each race SHALL identify the incumbent as the winner of the most recent
general or special election for that office and district before 2026-11-03,
and flag the matching candidate by within-race name match. Disagreement
with AP's incumbent flag SHALL be reported as a warning.

#### Scenario: Special-election winner defending
- **WHEN** the most recent prior election for a district is a 2026 special
  election
- **THEN** that special's winner is the race's incumbent

#### Scenario: AP disagrees on incumbency
- **WHEN** our name match flags a candidate as incumbent and AP does not
- **THEN** the build prints a warning listing the race and candidate and
  still writes output

### Requirement: Race totals reconcile with municipality rows
For every contested race, the race-level candidate votes SHALL equal the
sum of that candidate's municipality-level votes.

#### Scenario: Cross-file reconciliation
- **WHEN** both outputs are written
- **THEN** grouping the municipality file by race and candidate reproduces
  the race file's vote columns exactly
