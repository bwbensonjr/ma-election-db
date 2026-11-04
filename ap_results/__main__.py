"""CLI: uv run python -m ap_results {list | build <event> [--fetch]}"""

import argparse
import sys

from .events import EVENTS


def main():
    ap = argparse.ArgumentParser(prog="python -m ap_results",
                                 description="Interim AP election results")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list registered events")
    b = sub.add_parser("build", help="build one event's outputs")
    b.add_argument("event")
    b.add_argument("--fetch", action="store_true",
                   help="refresh the snapshots from the live AP feed first")
    args = ap.parse_args()

    if args.cmd == "list":
        for e in EVENTS.values():
            print(f"{e.name}\t{e.election_date}\t{e.stage}")
        return

    event = EVENTS.get(args.event)
    if event is None:
        print(f"unknown event {args.event!r}; registered events: "
              f"{', '.join(EVENTS)}", file=sys.stderr)
        sys.exit(2)
    event.build(fetch=args.fetch)


if __name__ == "__main__":
    main()
