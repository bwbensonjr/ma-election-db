"""Fail-loud integrity checks. Interim data is still data."""

import sys

from .feed import races, state_unit, town_units


def race_sum_problems(payloads, in_scope):
    """Check every in-scope, contested race in the payloads.

    Each candidate's municipality votes must sum to AP's statewide total for
    the race, and municipality precinct counts must sum to the race total --
    the latter confirms a split city is counted once per district.
    `in_scope(race)` decides which races are checked.
    """
    problems = []
    for payload in payloads:
        for race in races(payload):
            if not in_scope(race) or race.get("uncontested"):
                continue
            label = (f"race {race['raceID']} ({race['officeName']} "
                     f"{race.get('seatName')})")
            state = state_unit(race)
            if state is None:
                problems.append(f"race {race['raceID']}: no statewide unit")
                continue
            towns = town_units(race)

            by_cand = {}
            for unit in towns:
                for c in unit["candidates"]:
                    by_cand[c["candidateID"]] = (
                        by_cand.get(c["candidateID"], 0) + c.get("voteCount", 0))
            for c in state["candidates"]:
                want = c.get("voteCount", 0)
                got = by_cand.get(c["candidateID"], 0)
                if want != got:
                    problems.append(
                        f"{label} candidate {c['last']}: "
                        f"towns sum to {got}, statewide says {want}")

            want_p = state.get("precinctsTotal")
            got_p = sum(u.get("precinctsTotal", 0) for u in towns)
            if want_p != got_p:
                problems.append(
                    f"{label}: town precincts sum to {got_p}, "
                    f"statewide says {want_p}")
    return problems


def duplicate_problems(df, key):
    dupes = df[df.duplicated(subset=key, keep=False)]
    if dupes.empty:
        return []
    return [f"{len(dupes)} duplicate rows on {key}"]


def fail_on(problems):
    if problems:
        print("ERROR: verification failed:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        sys.exit(1)


def fail_on_unmatched(unmatched):
    """unmatched: list of (label, office, seat) tuples."""
    if unmatched:
        print("ERROR: districts that did not match the reference:", file=sys.stderr)
        for label, office, seat in unmatched:
            print(f"  [{label}] {office}: {seat!r}", file=sys.stderr)
        sys.exit(1)
