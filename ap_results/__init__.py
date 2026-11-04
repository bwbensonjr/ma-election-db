"""Interim Massachusetts election results from the Associated Press feed.

The Boston Globe's election coverage is backed by a public AP feed. Between
election night and certification on electionstats.state.ma.us, this package
pulls that feed, snapshots it, and normalizes it to ma-election-db
conventions. Each election is an "event" registered in `events.py` with its
own subdirectory of snapshots and inputs.

Usage:
    uv run python -m ap_results list
    uv run python -m ap_results build <event> [--fetch]
"""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO = PACKAGE_DIR.parent
DATA_DIR = REPO / "data" / "ap_results"
DISTRICT_REFERENCE = PACKAGE_DIR / "district_reference.csv"
SUMMARIES_FILE = REPO / "data" / "ma_general_election_summaries.csv.gz"


def rel(path):
    """Path relative to the repo, for messages."""
    try:
        return Path(path).resolve().relative_to(REPO)
    except ValueError:
        return path
