# Design

## Context

`primary_2026/` holds two scripts. `build_primary_2026.py` parses the
hand-transcribed SEC candidate list and computes incumbency;
`build_primary_2026_results.py` fetches the Globe AP feed, snapshots it,
normalizes it and verifies it. The results script imports constants and
helpers (`OFFICE_META`, `PARTY_ABBR`, `district_key`, `build_reference`,
`first_last`) from the nominations script by relying on the script's own
directory being on `sys.path`.

A probe of the live feed on 2026-11-04 (`/v2/elections/2026-11-03?statePostal=MA&level=ru`,
no `party` parameter) returned all 234 races in one ~4.9 MB response:
160 State House (47 contested, 113 uncontested) and 40 State Senate (10
contested, 30 uncontested), plus out-of-scope offices and 9 ballot questions.
Reporting-unit levels are the same as the primary (1 = state, 2 =
municipality within district). Candidate parties seen: `Dem`, `GOP`, `Ind`,
`Unr`, `Oth`. Uncontested races have every `voteCount` at 0 but the sole
candidate carries `winner: "X"`. 10 races were still `Too Early to Call`.

## Goals / Non-Goals

**Goals:**
- One shared implementation of fetch / snapshot / normalize / verify.
- Adding the next event (a 2027 special, the 2028 primary) is a registry
  entry plus a directory.
- Primary outputs that compare equal as tables after the move.

**Non-Goals:**
- Precinct- or ward-level results (AP has none).
- Blank and write-in votes (AP does not report them; `total_votes` here is
  the sum of named candidates' votes and will be lower than electionstats').
- U.S. House, Governor's Council, statewide offices or ballot questions for
  the general. The office map makes adding them a one-line change later.
- SQLite tables, `make all`, or automatic reconciliation with certified data.

## Decisions

### Layout: a Python package with event subdirectories

```
ap_results/
  __init__.py
  __main__.py            # CLI: build <event> [--fetch], list
  feed.py                # fetch, snapshot I/O, reporting-unit helpers
  normalize.py           # office map, seat names, district reference, party map, name keys
  incumbency.py          # most-recent-prior-winner lookup + name matching
  verify.py              # vote-sum, precinct-sum, uniqueness checks
  events.py              # EVENTS registry
  district_reference.csv # 2021-cycle districts, shared
  README.md              # shared behavior, how to add an event, retirement
  primary_2026/
    README.md
    candidates_2026_raw.txt
    candidates.py        # SEC nominations parse (primary-only)
    results.py           # primary results shaping
    snapshots/ap_2026-09-01_{dem,gop}.json.gz
  general_2026/
    README.md
    results.py           # race + municipality shaping for a general
    snapshots/ap_2026-11-03.json.gz
data/ap_results/
  primary_2026/ma_primary_2026_{candidates,results}.csv.gz
  general_2026/ma_general_2026_{races,results}.csv.gz
```

Running as a module (`python -m ap_results build general_2026`) gives normal
package imports and removes the `sys.path` coupling. Alternatives: keeping
loose scripts with `sys.path` edits (fragile, the current pain), or a single
generic script with all logic driven by config (primaries and generals
shape output differently - per-party primaries with a nominations join vs.
one race with party columns - so forcing them into one code path costs more
than two small shaping modules).

The `results.py` shaper in `general_2026/` is written against election
*stage*, not year: the registry points `general_2026` at it, and a future
`general_2028` can reuse it by reference. Likewise for `primary_2026`. If a
second general appears, promote the shaper to `ap_results/stages/general.py`;
not done now to avoid speculative structure.

### Event registry

`events.py` holds a dict keyed by event name with: `election_date`,
`stage` (`primary` / `general`), `feed_params` (list of query-param sets,
one per snapshot - two party splits for the primary, one for the general),
`offices` (AP office names in scope), `district_reference` path, and the
shaper callable. Plain Python, not TOML/YAML, because entries reference
callables and the project has no config-file convention.

### Snapshot naming

`ap_<date>[_<party>].json.gz`. The primary keeps its existing names, so
`git log --follow` traces history through the move. The general snapshot is
the full feed response (~4.9 MB raw, ~290 KB gzipped); filtering
out-of-scope races before saving was rejected so that adding offices later
does not require a re-fetch of a feed that may have moved on.

### Uncontested and uncalled races

Kept in the race file with blank votes and AP's winner, because "who holds
every seat" is the main question for the general, unlike the primary where
uncontested nominations carried no information. Blank, not 0, so averages
and margins do not silently treat them as 0-0 races. Excluded from the
municipality file because their rows would be all zeros.

### Third-party column

The `*_third_party` columns take the non-Dem/GOP candidate with the most
votes, matching how `elections.R` fills `general_election`. With at most
three candidates per race on the current snapshot, no information is lost;
the municipality file keeps every candidate regardless.

### Incumbency source

Reuse the primary's rule and code path (`incumbency.py`): most recent prior
winner per `(office_id, district_id)` from
`data/ma_general_election_summaries.csv.gz`, joined by `first_last` name
key, with a per-event overrides set. The primary's two overrides (Comerford,
Fluker Reid) move into the primary registry entry; the general starts with
the same set and adds any the AP cross-check surfaces. Alternative
considered: trust AP's `incumbent` flag. Rejected as the primary source
because it carries no electionstats id; kept as `is_incumbent_ap` for
cross-checking, as in the primary.

## Risks / Trade-offs

- [Downstream readers of `data/primary_2026/` break] -> Searched this repo and
  the blog repo: no references. The commit message calls out the move;
  `git mv` keeps history.
- [Primary output drifts during refactor] -> Before moving, copy the
  committed CSVs aside and compare with pandas `assert_frame_equal` after
  rebuild (a spec scenario).
- [Feed mutates during recounts; snapshot goes stale] -> `--fetch` refresh
  plus a commit per snapshot, as done for the primary
  (`data: refresh 2026 general results to <time> UTC snapshot`).
- [AP seat names differ from primary spellings for a few districts] -> The
  reference lookup fails loudly and lists every unmatched seat; fix by
  extending `ap_district_name`, not by editing outputs.
- [AP percentages differ from certified ones] -> Documented: AP excludes
  blanks and write-ins. Readers comparing to `general_election.percent_*`
  should expect small differences.

## Migration Plan

1. `git mv primary_2026 ap_results/primary_2026`, move
   `district_reference.csv` up, `git mv data/primary_2026 data/ap_results/primary_2026`.
2. Extract shared modules; rewire primary; prove equivalence.
3. Add `general_2026`; fetch snapshot; build; commit.
4. Refresh snapshots as AP updates through certification.
5. Retirement: once electionstats has the 2026-11-03 results, run
   `make general_elections && make all`, reconcile seat winners against
   `ma_general_2026_races.csv.gz`, record the comparison in the commit
   message (as `bb32fc2` did for the primary), and leave the AP files in
   place as a historical record.

Rollback: revert the commit(s); no database or external state changes.
