# Proposal

## Why

The November 3, 2026 general election is over, but electionstats.state.ma.us
will not carry certified State Representative and State Senate results for
weeks. We need usable interim results now, as we did for the September
primary with `primary_2026/`. That pipeline was written as a one-off: its
AP-feed fetching, snapshotting, district normalization and verification live
inside primary-specific scripts, so a second event would mean copying them.
This is the moment to turn the one-off into a reusable home for interim AP
data, before a second copy exists.

## What Changes

- Introduce a top-level `ap_results/` domain directory for interim Associated
  Press results pulled from the Boston Globe elections API
  (`https://elections-api.bostonglobe.com/v2/elections/<date>`).
- Factor the reusable parts of `primary_2026/build_primary_2026_results.py`
  and `build_primary_2026.py` (feed fetch and gzip snapshot, AP office and
  seat-name normalization, district reference lookup, name matching for
  incumbency, AP vote-sum and precinct-sum verification) into a shared module
  under `ap_results/`.
- Add a per-event registry so each interim event (`primary_2026`,
  `general_2026`, future specials or 2028 cycles) is a small configuration
  entry plus its own subdirectory of checked-in snapshots and any
  event-specific inputs.
- **BREAKING (paths only)**: move `primary_2026/` to `ap_results/primary_2026/`
  and its outputs from `data/primary_2026/` to `data/ap_results/primary_2026/`.
  Output file names, columns and row contents stay identical. The build
  commands change to `uv run python -m ap_results ...`.
- Move the shared `district_reference.csv` (2021-cycle districts) up to
  `ap_results/` so every 2022-2030 event uses one copy.
- Add `general_2026`: State Representative and State Senate results for the
  2026-11-03 general election, written as two outputs under
  `data/ap_results/general_2026/`:
  - a race-level file, one row per district, covering all 200 seats
    (including the ~143 uncontested ones, which AP reports with a winner
    but zero votes), with winner, incumbent and per-party candidate columns
    shaped like `general_election`;
  - a municipality-level file, one row per (district, municipality,
    candidate) for contested races, shaped like the primary results file.
- Incumbency for the general is derived the same way as the primary: winner
  of the most recent prior general or special election for the
  (office, district), matched by name, cross-checked against AP's own flag.
- Not in scope for SQLite or `make all`, matching the primary precedent: these
  are interim numbers superseded once `make general_elections` picks up
  certified results.

## Capabilities

### New Capabilities

- `ap-interim-results`: the shared pipeline for interim AP election results -
  per-event layout, snapshotting and offline rebuild, normalization to
  ma-election-db office/district conventions, and fail-loud verification.
  Covers the relocated 2026 primary as one event.
- `general-election-interim-results`: the general-election event output -
  race-level and municipality-level State Rep / State Senate results with
  winners, party columns, uncontested-seat handling and incumbency.

### Modified Capabilities

None. `openspec/specs/` is empty; no existing capability changes.

## Impact

- **Moved**: `primary_2026/` -> `ap_results/primary_2026/`;
  `data/primary_2026/` -> `data/ap_results/primary_2026/`. Any notebook,
  query or blog post that reads the old CSV paths must be updated (a search
  of this repo and `../../massnumbers/blog` found no references outside
  `primary_2026/` itself).
- **New**: `ap_results/` package (shared module, event registry, CLI entry
  point, README), `ap_results/general_2026/snapshots/`,
  `data/ap_results/general_2026/*.csv.gz`.
- **Docs**: `CLAUDE.md` gains an `ap_results` stage description;
  `primary_2026/README.md` content is split between `ap_results/README.md`
  (shared behavior) and `ap_results/primary_2026/README.md` (event notes).
- **Reads**: `data/ma_general_election_summaries.csv.gz` for incumbency (must
  include the 2026-03-31 special, which it currently does).
- **Dependencies**: none new (pandas, requests already in `pyproject.toml`).
- **Unchanged**: `build_sqlite.R`, `Makefile` `all` target, R pipelines.
