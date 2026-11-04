# Tasks

## 1. Relocate primary_2026

- [x] 1.1 Copy the committed `data/primary_2026/*.csv.gz` to the scratchpad as regression baselines; verify both files are present there
- [x] 1.2 `git mv primary_2026 ap_results/primary_2026`, move `district_reference.csv` to `ap_results/district_reference.csv`, and `git mv data/primary_2026 data/ap_results/primary_2026`; verify `git status` shows renames, not delete+add, and no root `primary_2026/` remains

## 2. Shared package and CLI

- [x] 2.1 Create `ap_results/__init__.py` and `normalize.py` with `OFFICE_META`, AP office map, `ordinal`, `ap_district_name`, `district_key`, `build_reference`, `first_last`, and the AP party map (`Dem`/`GOP`/`Unr`/`Ind`/other); verify `uv run python -c "from ap_results.normalize import build_reference; build_reference('ap_results/district_reference.csv')"` succeeds
- [x] 2.2 Create `feed.py` (fetch with empty-response guard, gzip snapshot read/write, missing-snapshot error, state/town reporting-unit helpers) and `verify.py` (vote-sum, precinct-sum, key-uniqueness checks taking the event's office scope); verify by importing both modules
- [x] 2.3 Create `incumbency.py` from `enrich_incumbency`, parameterized by election date and an overrides set; verify import
- [x] 2.4 Create `events.py` registry and `__main__.py` with `build <event> [--fetch]` and `list`; verify `uv run python -m ap_results list` prints the registered events and `uv run python -m ap_results build nope` exits non-zero listing them

## 3. Rewire primary_2026 onto the shared package

- [x] 3.1 Convert `ap_results/primary_2026/build_primary_2026.py` to `candidates.py` and `build_primary_2026_results.py` to `results.py`, importing from the shared modules and moving the two incumbent overrides into the registry entry; remove `primary_2026/__pycache__`; verify no file in `ap_results/primary_2026/` defines `district_key`, `build_reference` or `first_last`
- [x] 3.2 Run `uv run python -m ap_results build primary_2026` and compare both outputs with the 1.1 baselines via `pandas.testing.assert_frame_equal`; verify both comparisons pass and row counts are 340 and 2,751
- [x] 3.3 Split `primary_2026/README.md` into `ap_results/README.md` (feed, granularity, snapshots, verification, adding an event, retirement steps) and `ap_results/primary_2026/README.md` (SEC transcription, overrides, primary-specific coverage); verify every build command in both READMEs runs as written

## 4. general_2026 event

- [x] 4.1 Add the `general_2026` registry entry (date `2026-11-03`, stage `general`, one feed request with no `party` param, offices `State House` and `State Senate`) and fetch with `uv run python -m ap_results build general_2026 --fetch`; verify `ap_results/general_2026/snapshots/ap_2026-11-03.json.gz` exists and lists 160 State House and 40 State Senate races
- [x] 4.2 Implement `general_2026/results.py` producing the municipality file for contested races with each candidate's own `party`, `party_abbr` and `party_ap`; verify the shared vote-sum and precinct-sum checks pass and Boston rows appear once per State House district
- [x] 4.3 Produce the race-level file: one row per district with winner, dem, gop and top third-party columns, `is_uncontested`, blank votes for uncontested races, blank winner for uncalled races, `race_call_status`, precinct and `eevp` fields; verify 200 rows, 3rd Bristol shows 9,068 D / 6,490 R with `percent_dem` about 0.583, and 26th Middlesex shows `is_uncontested = 1` with a winner and blank votes
- [x] 4.4 Add incumbency (`id/name/party_incumbent`, `incumbent_election_date`, `incumbent_running`, per-candidate `is_incumbent` and `is_incumbent_ap`) using `data/ma_general_election_summaries.csv.gz`; verify the build prints the AP-disagreement warning list, review each entry, and add overrides until only genuine disagreements remain
- [x] 4.5 Add the cross-file reconciliation check (race votes equal summed municipality votes per candidate) to the general build; verify it passes on the snapshot and fails when one municipality vote is altered in a scratch copy
- [x] 4.6 Write `ap_results/general_2026/README.md` covering scope, both files' columns, uncontested and uncalled handling, the AP-excludes-blanks/write-ins caveat, and the snapshot time; verify the documented row counts match the build output

## 5. Project docs and integration

- [x] 5.1 Update `CLAUDE.md` (new `ap_results` stage under Architecture, output files list) and `.gitignore` if needed for `__pycache__` under the package; verify `grep -rn "primary_2026/" CLAUDE.md` only shows `ap_results/` paths
- [x] 5.2 Run `make all` and verify it completes without invoking `ap_results` and that `sqlite3 data/ma_elections.sqlite ".tables"` lists no AP-derived table
- [x] 5.3 Run `openspec validate ap-results-general-2026 --strict`; verify it passes

## Workflow follow-up

- Commit the relocation and the general_2026 build as separate commits; refresh the general snapshot as AP updates (one commit per refresh).
- When electionstats publishes certified 2026-11-03 results, run `make general_elections && make all`, reconcile winners against `ma_general_2026_races.csv.gz`, and record the comparison in the commit message.
- Archive the change after review.
