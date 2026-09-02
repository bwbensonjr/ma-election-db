"""Build the 2026 MA state primary candidate dataset.

Parses the hand-curated `candidates_2026_raw.txt` (transcribed from the two
Secretary of the Commonwealth candidate-listing pages) and normalizes it to
ma-election-db conventions: office/office_id/office_branch, canonical district
names, and district_id/district_display joined from `district_reference.csv`
(the current-cycle districts as the DB records them).

Output: data/primary_2026/ma_primary_2026_candidates.csv.gz
"""

import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
RAW_FILE = HERE / "candidates_2026_raw.txt"
REF_FILE = HERE / "district_reference.csv"
SUMMARIES_FILE = REPO / "data" / "ma_general_election_summaries.csv.gz"
OUT_FILE = REPO / "data" / "primary_2026" / "ma_primary_2026_candidates.csv.gz"

ELECTION_DATE = "2026-09-01"

# Incumbent = winner of the most recent prior general OR special election for
# the same (office_id, district_id). We flag a 2026 candidate as the incumbent
# when their name matches that winner. The SEC pages carry no electionstats
# candidate IDs, so matching is by name: within a race we compare
# first+last (dropping middle names/initials and suffixes), which resolves the
# common formatting differences ("Tara Thorn Hong" -> "Tara Hong",
# "William Macgregor" -> "William F. MacGregor").
#
# INCUMBENT_OVERRIDES lists the incumbents that name-matching cannot catch
# (nicknames, surname changes) -- the same manual-mapping approach the project
# uses in data/candidate-id-map.csv. Each entry is (office, district, name),
# where name is the 2026 candidate's name as it appears in the raw file.
INCUMBENT_OVERRIDES = {
    # "Jo Comerford" (electionstats) -> "Joanne M. Comerford" (2026 ballot)
    ("State Senate", "Hampshire, Franklin and Worcester", "Joanne M. Comerford"),
    # "Brandy Fluker Oakley" (electionstats) -> "Brandy Fluker Reid" (surname change)
    ("State Representative", "Twelfth Suffolk", "Brandy Fluker Reid"),
}

NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# 2026 is a U.S. Senate Class 2 cycle: (2026 - 1990) % 6 == 0 (see elections.R).
US_SENATE_DISTRICT = "Class 2"
US_SENATE_DISTRICT_ID = 2

PARTY_ABBR = {"Democratic": "D", "Republican": "R"}

# office name -> (office_branch, office_id)
OFFICE_META = {
    "U.S. Senate": ("Legislative", 6),
    "Governor": ("Executive", 3),
    "U.S. House": ("Legislative", 5),
    "Governor's Council": ("Executive", 529),
    "State Senate": ("Legislative", 9),
    "State Representative": ("Legislative", 8),
}

# Offices with no per-district reference lookup.
STATEWIDE = {"Governor", "U.S. Senate"}


def district_key(name):
    """&/and- and case-insensitive key for joining SEC district names to the
    canonical DB spellings (the DB mixes '&' and 'and' inconsistently)."""
    k = name.strip().lower()
    k = k.replace("&", "and")
    k = re.sub(r"\s+", " ", k)
    return k


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


def first_last(name):
    """Normalized 'first last' for within-race incumbent matching: lowercase,
    punctuation removed, middle names/initials and suffixes dropped."""
    if not isinstance(name, str):
        return ""
    toks = [t for t in re.sub(r"[.,]", " ", name.lower()).split()
            if t not in NAME_SUFFIXES]
    if not toks:
        return ""
    return f"{toks[0]} {toks[-1]}" if len(toks) >= 2 else toks[0]


def enrich_incumbency(df):
    """Add incumbent columns to the candidate dataframe (in place-ish, returns
    a new frame). Reads the general-election summaries to find the most recent
    prior winner per (office_id, district_id)."""
    summ = pd.read_csv(SUMMARIES_FILE)
    summ = summ[summ["election_date"] < ELECTION_DATE].copy()
    summ["dkey"] = summ["district_id"].fillna(-1)
    summ = summ.sort_values("election_date")
    # Most recent prior election (general or special) per office/district.
    inc = summ.groupby(["office_id", "dkey"], as_index=False).last()[
        ["office_id", "dkey", "election_date", "name_winner",
         "party_winner", "id_winner"]]
    inc = inc.rename(columns={
        "election_date": "incumbent_election_date",
        "name_winner": "incumbent_name",
        "party_winner": "incumbent_party",
        "id_winner": "incumbent_id",
    })

    df = df.copy()
    df["dkey"] = df["district_id"].fillna(-1)
    df = df.merge(inc, on=["office_id", "dkey"], how="left")

    override = {(o, d, n) for (o, d, n) in INCUMBENT_OVERRIDES}
    df["is_incumbent"] = df.apply(
        lambda r: int(
            ((r["office"], r["district"], r["name"]) in override)
            or (bool(first_last(r["name"]))
                and first_last(r["name"]) == first_last(r["incumbent_name"]))
        ),
        axis=1,
    )
    # Is the incumbent among this race's candidates (i.e., seat is defended)?
    defended = (df[df["is_incumbent"] == 1]
                .groupby(["office_id", "dkey"]).size())
    df["incumbent_running"] = df.apply(
        lambda r: int((r["office_id"], r["dkey"]) in defended.index), axis=1)

    df["incumbent_id"] = df["incumbent_id"].astype("Int64")
    df = df.drop(columns=["dkey"])
    return df


def build_reference(ref_file):
    """Return dict: office -> {district_key -> (district, district_display, district_id)}.

    Each district is registered under both its canonical name ("Eighteenth
    Essex") and its display name ("18th Essex"), so callers can join on either
    spelling. The two coincide for districts named after their counties
    ("Cape and Islands"), which is harmless -- both keys carry the same value.
    """
    ref = pd.read_csv(ref_file)
    lookup = {}
    for office, grp in ref.groupby("office"):
        by_key = {}
        for _, r in grp.iterrows():
            value = (r["district"], r["district_display"], int(r["district_id"]))
            for name in (r["district"], r["district_display"]):
                k = district_key(name)
                if by_key.get(k, value) != value:
                    sys.exit(f"reference key collision in {office!r}: {k!r}")
                by_key[k] = value
        lookup[office] = by_key
    return lookup


def main():
    rows = list(parse_raw(RAW_FILE))
    ref = build_reference(REF_FILE)

    out = []
    unmatched = []
    for r in rows:
        office = r["office"]
        if office not in OFFICE_META:
            sys.exit(f"unknown office: {office!r}")
        branch, office_id = OFFICE_META[office]

        if office == "Governor":
            district = district_display = district_id = None
        elif office == "U.S. Senate":
            district, district_display, district_id = (
                US_SENATE_DISTRICT, US_SENATE_DISTRICT, US_SENATE_DISTRICT_ID)
        else:
            key = district_key(r["district_sec"])
            match = ref.get(office, {}).get(key)
            if match is None:
                unmatched.append((r["party"], office, r["district_sec"]))
                continue
            district, district_display, district_id = match

        party = r["party"]
        abbr = PARTY_ABBR[party]
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
            "election_date": ELECTION_DATE,
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
    df = enrich_incumbency(df)
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

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_FILE, index=False, compression="gzip")

    print(f"Wrote {len(df)} candidate rows to {OUT_FILE.relative_to(REPO)}")
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


if __name__ == "__main__":
    main()
