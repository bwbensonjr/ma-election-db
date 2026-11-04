"""Build the 2026 MA state primary candidate dataset.

Parses the hand-curated `candidates_2026_raw.txt` (transcribed from the two
Secretary of the Commonwealth candidate-listing pages) and normalizes it to
ma-election-db conventions: office/office_id/office_branch, canonical district
names, and district_id/district_display joined from the shared
`ap_results/district_reference.csv`.

Output: data/ap_results/primary_2026/ma_primary_2026_candidates.csv.gz
"""

import sys

import pandas as pd

from .. import DISTRICT_REFERENCE, rel
from ..incumbency import enrich
from ..normalize import OFFICE_META, build_reference, party_abbr, resolve_district

RAW_NAME = "candidates_2026_raw.txt"
OUT_NAME = "ma_primary_2026_candidates.csv.gz"


def out_file(event):
    return event.out_dir / OUT_NAME


def parse_raw(path):
    """Yield dict rows (party, office, district_sec, name, city) from the raw file."""
    party = office = district = None
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                party = stripped[1:-1]
                office = district = None
            elif stripped.startswith("$ "):
                office = stripped[2:].strip()
                district = None
            elif stripped.startswith("@ "):
                district = stripped[2:].strip()
            else:
                # "Name, City" -- split on the LAST comma so name suffixes
                # (", Jr." / ", III") stay in the name.
                if "," not in stripped:
                    sys.exit(f"line {lineno}: candidate line missing city: {stripped!r}")
                name, city = stripped.rsplit(",", 1)
                yield {
                    "party": party,
                    "office": office,
                    "district_sec": district,
                    "name": name.strip(),
                    "city_town": city.strip(),
                }


def build(event):
    rows = list(parse_raw(event.event_dir / RAW_NAME))
    ref = build_reference(DISTRICT_REFERENCE)

    out = []
    unmatched = []
    for r in rows:
        office = r["office"]
        if office not in OFFICE_META:
            sys.exit(f"unknown office: {office!r}")
        branch, office_id = OFFICE_META[office]

        match = resolve_district(office, r["district_sec"], ref, event.election_date)
        if match is None:
            unmatched.append((r["party"], office, r["district_sec"]))
            continue
        district, district_display, district_id = match

        party = r["party"]
        abbr = party_abbr(party)
        out.append({
            "party": party,
            "party_abbr": abbr,
            "office_branch": branch,
            "office_id": office_id,
            "office": office,
            "district": district,
            "district_display": district_display,
            "district_id": district_id,
            "district_sec": r["district_sec"],
            "election_date": event.election_date,
            "is_special": 0,
            "name": r["name"],
            "display": f"{r['name']} ({abbr})",
            "city_town": r["city_town"],
        })

    if unmatched:
        print("ERROR: districts that did not match the reference:", file=sys.stderr)
        for party, office, d in unmatched:
            print(f"  [{party}] {office}: {d!r}", file=sys.stderr)
        sys.exit(1)

    df = pd.DataFrame(out)
    df["district_id"] = df["district_id"].astype("Int64")
    df = enrich(df, event.election_date, event.incumbent_overrides)
    df = df[[
        "party", "party_abbr", "office_branch", "office_id", "office",
        "district", "district_display", "district_id", "district_sec",
        "election_date", "is_special", "name", "display", "city_town",
        "is_incumbent", "incumbent_running", "incumbent_name",
        "incumbent_party", "incumbent_id", "incumbent_election_date",
    ]]
    df = df.sort_values(
        ["office_id", "district_id", "district", "party", "name"],
        na_position="first",
    ).reset_index(drop=True)

    path = out_file(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, compression="gzip")

    print(f"Wrote {len(df)} candidate rows to {rel(path)}")
    print("\nRows by party:")
    print(df["party"].value_counts().to_string())
    print("\nRows by office and party:")
    print(df.groupby(["office", "party"]).size().to_string())

    n_inc = int(df["is_incumbent"].sum())
    races = df[["office_id", "district_id"]].drop_duplicates().shape[0]
    open_races = races - df[df["is_incumbent"] == 1][
        ["office_id", "district_id"]].drop_duplicates().shape[0]
    print(f"\nIncumbents running: {n_inc} candidates flagged is_incumbent")
    print(f"Open seats (incumbent not running): {open_races} of {races} races")
