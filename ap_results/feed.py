"""Fetch and snapshot the AP election feed that backs the Boston Globe.

The feed is public and unauthenticated:

    https://elections-api.bostonglobe.com/v2/elections/<date>?statePostal=MA&level=ru

`level=ru` produces sub-state reporting units. `level` accepts only `ru` and
`fipscode`, and `fipscode` returns nothing for Massachusetts. The finest grain
is the municipality *within a district* (reportingunitLevel 2); there is no
ward or precinct tier.

The feed mutates in place, so raw responses are snapshotted (gzipped JSON)
and checked in. Builds read snapshots and touch the network only on --fetch.
"""

import gzip
import json
import sys

import requests

from . import rel

API_BASE = "https://elections-api.bostonglobe.com/v2/elections"

# AP reporting-unit levels: 1 is the whole state, 2 is a municipality.
RU_STATE = 1
RU_TOWN = 2


def snapshot_name(election_date, suffix=None):
    """ap_<date>[_<suffix>].json.gz"""
    tail = f"_{suffix}" if suffix else ""
    return f"ap_{election_date}{tail}.json.gz"


def fetch(election_date, params, out_path):
    """Fetch one feed response and snapshot it. Refuses to overwrite an
    existing snapshot with an empty race list."""
    query = {"statePostal": "MA", "level": "ru", **params}
    resp = requests.get(f"{API_BASE}/{election_date}", params=query, timeout=120)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("races"):
        sys.exit(f"empty race list for {query!r} -- refusing to snapshot")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(payload, f)
    return payload


def load_snapshot(path):
    if not path.exists():
        sys.exit(f"missing snapshot {rel(path)} -- run with --fetch")
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def load_payloads(event, fetch_live=False):
    """Return {suffix: payload} for every feed request the event declares."""
    payloads = {}
    for suffix, params in event.feed_params.items():
        path = event.snapshot_dir / snapshot_name(event.election_date, suffix)
        if fetch_live:
            payloads[suffix] = fetch(event.election_date, params, path)
            print(f"Fetched {suffix or 'all'} races -> {rel(path)}")
        else:
            payloads[suffix] = load_snapshot(path)
    return payloads


def races(payload):
    """Yield the raceResponse objects in a payload."""
    for wrapper in payload["races"]:
        yield wrapper["raceResponse"]


def state_unit(race):
    return next(
        (u for u in race["reportingUnits"] if u["reportingunitLevel"] == RU_STATE),
        None,
    )


def town_units(race):
    return [u for u in race["reportingUnits"] if u["reportingunitLevel"] == RU_TOWN]


def candidate_name(cand):
    """AP splits names into first/middle/last; rebuild the display form."""
    parts = [cand.get("first"), cand.get("middle"), cand.get("last")]
    return " ".join(p for p in parts if p)
