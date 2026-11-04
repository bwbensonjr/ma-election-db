"""Normalize AP and SEC spellings to ma-election-db conventions.

Offices, districts, parties and candidate names all arrive in forms that
differ from how the database records them. Everything here is a pure mapping
or lookup, shared by every event.
"""

import re
import sys

import pandas as pd

# Database office name -> (office_branch, office_id), matching general_election.
OFFICE_META = {
    "U.S. Senate": ("Legislative", 6),
    "Governor": ("Executive", 3),
    "U.S. House": ("Legislative", 5),
    "Governor's Council": ("Executive", 529),
    "State Senate": ("Legislative", 9),
    "State Representative": ("Legislative", 8),
}

# AP officeName -> database office name. AP offices absent from this map
# (District Attorney, Attorney General, Lieutenant Governor, Secretary of
# State, Treasurer, Auditor, ballot questions) are outside the schema.
AP_OFFICE = {
    "U.S. Senate": "U.S. Senate",
    "Governor": "Governor",
    "U.S. House": "U.S. House",
    "Governor's Council": "Governor's Council",
    "State Senate": "State Senate",
    "State House": "State Representative",
}

# Party name -> abbreviation, matching party_abbrev() in elections.R.
PARTY_ABBR = {
    "Democratic": "D",
    "Republican": "R",
    "Unenrolled": "U",
    "Libertarian": "L",
    "Independent": "I",
    "Green-Rainbow": "GR",
    "Natural Law": "NL",
}

# AP candidate party code -> database party name. Unknown codes map to Other.
AP_PARTY = {
    "Dem": "Democratic",
    "GOP": "Republican",
    "Unr": "Unenrolled",
    "Ind": "Independent",
    "Lib": "Libertarian",
    "Grn": "Green-Rainbow",
}

NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def party_abbr(party):
    return PARTY_ABBR.get(party, "Other")


def ap_party(code):
    """AP party code -> (party, party_abbr)."""
    party = AP_PARTY.get(code, "Other")
    return party, party_abbr(party)


def us_senate_class(election_date):
    """U.S. Senate class for a regular election year, per elections.R."""
    year = int(str(election_date)[:4])
    if (year - 1990) % 6 == 0:
        return 2
    if (year - 1994) % 6 == 0:
        return 1
    sys.exit(f"no regular U.S. Senate election in {year}")


def ordinal(n):
    """1 -> '1st', 2 -> '2nd', 3 -> '3rd', 4 -> '4th', ..."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def ap_district_name(office, seat_name):
    """Translate an AP seatName into a spelling build_reference() can key on.

    State House / State Senate seats already arrive in display form ("18th
    Essex", "5th Middlesex"). The two numbered offices arrive as "District N",
    which the reference records as an ordinal ("6th") for Governor's Council
    and as a bare number ("7") for U.S. House.
    """
    if seat_name is None:
        sys.exit(f"missing seatName for {office!r}")
    seat_name = seat_name.strip()
    if office in ("Governor's Council", "U.S. House"):
        if not seat_name.lower().startswith("district "):
            sys.exit(f"unexpected {office} seatName: {seat_name!r}")
        number = int(seat_name.split()[-1])
        return ordinal(number) if office == "Governor's Council" else str(number)
    return seat_name


def district_key(name):
    """&/and- and case-insensitive key for joining district names to the
    canonical DB spellings (the DB mixes '&' and 'and' inconsistently)."""
    k = name.strip().lower()
    k = k.replace("&", "and")
    k = re.sub(r"\s+", " ", k)
    return k


_ORDINAL_UNITS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth",
                  "Seventh", "Eighth", "Ninth"]
_ORDINAL_TEENS = ["Tenth", "Eleventh", "Twelfth", "Thirteenth", "Fourteenth",
                  "Fifteenth", "Sixteenth", "Seventeenth", "Eighteenth",
                  "Nineteenth"]
_ORDINAL_TENS = {20: ("Twentieth", "Twenty"), 30: ("Thirtieth", "Thirty"),
                 40: ("Fortieth", "Forty")}


def _ordinal_words():
    """{'first': 1, ..., 'thirty-seventh': 37, ...} up to 49."""
    words = {w.lower(): i + 1 for i, w in enumerate(_ORDINAL_UNITS)}
    words.update({w.lower(): i + 10 for i, w in enumerate(_ORDINAL_TEENS)})
    for tens, (exact, prefix) in _ORDINAL_TENS.items():
        words[exact.lower()] = tens
        for i, w in enumerate(_ORDINAL_UNITS):
            words[f"{prefix}-{w}".lower()] = tens + i + 1
    return words


ORDINAL_WORDS = _ordinal_words()


def abbreviate_ordinal(name):
    """'Third Bristol & Plymouth' -> '3rd Bristol & Plymouth'; other names
    are returned unchanged."""
    head, _, rest = name.strip().partition(" ")
    n = ORDINAL_WORDS.get(head.lower())
    return f"{ordinal(n)} {rest}" if n and rest else name


def build_reference(ref_file):
    """Return dict: office -> {district_key -> (district, district_display, district_id)}.

    Each district is registered under its canonical name ("Eighteenth
    Essex"), its display name ("18th Essex"), and the canonical name with its
    ordinal abbreviated. The last matters because the reference's display
    names are not uniform -- some districts display as "Third Bristol &
    Plymouth" while AP sends "3rd Bristol & Plymouth". The spellings coincide
    for districts named after their counties ("Cape and Islands"), which is
    harmless -- every key carries the same value.
    """
    ref = pd.read_csv(ref_file)
    lookup = {}
    for office, grp in ref.groupby("office"):
        by_key = {}
        for _, r in grp.iterrows():
            value = (r["district"], r["district_display"], int(r["district_id"]))
            for name in (r["district"], r["district_display"],
                         abbreviate_ordinal(r["district"])):
                k = district_key(name)
                if by_key.get(k, value) != value:
                    sys.exit(f"reference key collision in {office!r}: {k!r}")
                by_key[k] = value
        lookup[office] = by_key
    return lookup


def resolve_district(office, name, ref, election_date):
    """(district, district_display, district_id) for a database office.

    `name` is a district spelling the reference knows (canonical, display, or
    SEC). Governor has no district; U.S. Senate carries its Class. Returns
    None when a districted office's name does not resolve.
    """
    if office == "Governor":
        return (None, None, None)
    if office == "U.S. Senate":
        cls = us_senate_class(election_date)
        return (f"Class {cls}", f"Class {cls}", cls)
    return ref.get(office, {}).get(district_key(name))


def first_last(name):
    """Normalized 'first last' for within-race name matching: lowercase,
    punctuation removed, middle names/initials and suffixes dropped."""
    if not isinstance(name, str):
        return ""
    toks = [t for t in re.sub(r"[.,]", " ", name.lower()).split()
            if t not in NAME_SUFFIXES]
    if not toks:
        return ""
    return f"{toks[0]} {toks[-1]}" if len(toks) >= 2 else toks[0]
