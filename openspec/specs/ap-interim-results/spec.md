# ap-interim-results Specification

## Purpose

Provides interim Massachusetts election results from the Associated Press feed
behind the Boston Globe, normalized to ma-election-db conventions, for the
period between election night and certification on electionstats.state.ma.us.

## Requirements

### Requirement: Per-event directory layout
Each interim event SHALL live in `ap_results/<event>/` (e.g. `primary_2026`,
`general_2026`) holding its snapshots and event-specific inputs, with outputs
written to `data/ap_results/<event>/`. Shared code and the shared district
reference SHALL live directly under `ap_results/`.

#### Scenario: Primary relocated
- **WHEN** the change is applied
- **THEN** `primary_2026/` no longer exists at the repo root, its inputs and
  snapshots are under `ap_results/primary_2026/`, and its outputs are under
  `data/ap_results/primary_2026/`

#### Scenario: Adding a future event
- **WHEN** a maintainer adds an interim event for a new election date
- **THEN** it requires only a new event registry entry and a new
  `ap_results/<event>/` directory, with no copy of fetch, normalization or
  verification code

### Requirement: Event build command
The system SHALL build any registered event with
`uv run python -m ap_results build <event>` and SHALL reject unknown event
names with a non-zero exit listing the registered events.

#### Scenario: Build a registered event
- **WHEN** `uv run python -m ap_results build general_2026` is run
- **THEN** the event's outputs are written under `data/ap_results/general_2026/`

#### Scenario: Unknown event
- **WHEN** `uv run python -m ap_results build general_2027` is run
- **THEN** the command exits non-zero and prints the registered event names

### Requirement: Snapshot-based reproducible builds
The build SHALL read gzipped raw AP responses checked in under
`ap_results/<event>/snapshots/` by default and make no network request.
With `--fetch` it SHALL first refresh those snapshots from the live feed.

#### Scenario: Offline rebuild
- **WHEN** the build runs without `--fetch` and snapshots exist
- **THEN** it produces outputs without any network access

#### Scenario: Missing snapshot
- **WHEN** the build runs without `--fetch` and a snapshot is missing
- **THEN** it exits non-zero naming the missing file and suggesting `--fetch`

#### Scenario: Empty feed response
- **WHEN** `--fetch` receives a response with no races
- **THEN** it exits non-zero and leaves any existing snapshot untouched

### Requirement: Normalization to database conventions
Output rows SHALL carry `office`, `office_id`, `office_branch`, `district`,
`district_display` and `district_id` matching `general_election`. AP seat
names SHALL be resolved through the shared district reference, accepting
both canonical and display spellings and treating `&` and `and` as equal.

#### Scenario: Display-form seat name
- **WHEN** AP reports a State House seat as `"18th Essex"`
- **THEN** the row has `district = "Eighteenth Essex"` and that district's
  `district_display` and `district_id`

#### Scenario: Unresolvable seat
- **WHEN** an in-scope AP seat name matches no reference district
- **THEN** the build exits non-zero listing every unmatched seat and writes
  no output

### Requirement: Event office scope
Each event SHALL declare which AP offices it includes; races for other
offices SHALL be excluded from its outputs.

#### Scenario: General excludes out-of-scope offices
- **WHEN** the `general_2026` feed includes U.S. House, ballot questions and
  District Attorney races
- **THEN** none of them appear in `general_2026` outputs

### Requirement: Fail-loud vote verification
For every in-scope race with vote data, the build SHALL verify that each
candidate's municipality votes sum to AP's statewide total for that race,
that municipality precinct totals sum to the race's precinct total, and that
output keys are unique. Any failure SHALL abort without writing output.

#### Scenario: Municipality votes disagree with the race total
- **WHEN** a candidate's municipality votes sum to a number different from
  AP's race-level count
- **THEN** the build exits non-zero naming the race and candidate

### Requirement: Primary 2026 outputs preserved
After relocation, the `primary_2026` event SHALL produce
`ma_primary_2026_candidates.csv.gz` and `ma_primary_2026_results.csv.gz`
with the same columns and row contents as before the change.

#### Scenario: Regression against the committed outputs
- **WHEN** `primary_2026` is rebuilt from its checked-in snapshots
- **THEN** both outputs, read as tables, equal the versions committed at
  `data/primary_2026/` before the move

### Requirement: Interim data stays out of the database
Interim AP outputs SHALL NOT be written to `data/ma_elections.sqlite` and
SHALL NOT be built by `make all`.

#### Scenario: Full rebuild
- **WHEN** `make all` runs
- **THEN** no `ap_results` script runs and no AP-derived table exists in the
  SQLite database
