"""Incumbency for interim results.

The incumbent for a race is the winner of the most recent prior general OR
special election for the same (office_id, district_id), matching the
ma-election-db incumbency definition. Neither the SEC listings nor the AP
feed carry electionstats candidate IDs, so a candidate is flagged as the
incumbent by matching first+last name to that winner within the race.
Overrides catch what name matching cannot (nicknames, surname changes) -- the
same manual-mapping approach as data/candidate-id-map.csv.
"""

import sys

import pandas as pd

from . import SUMMARIES_FILE, rel
from .normalize import first_last


def prior_winners(election_date, summaries_file=SUMMARIES_FILE):
    """Most recent winner per (office_id, dkey) before election_date, where
    dkey is district_id with -1 for statewide offices."""
    if not summaries_file.exists():
        sys.exit(f"missing {rel(summaries_file)} -- run elections.R first")
    summ = pd.read_csv(summaries_file)
    summ = summ[summ["election_date"] < election_date].copy()
    summ["dkey"] = summ["district_id"].fillna(-1)
    summ = summ.sort_values("election_date")
    inc = summ.groupby(["office_id", "dkey"], as_index=False).last()[
        ["office_id", "dkey", "election_date", "name_winner",
         "party_winner", "id_winner"]]
    return inc.rename(columns={
        "election_date": "incumbent_election_date",
        "name_winner": "incumbent_name",
        "party_winner": "incumbent_party",
        "id_winner": "incumbent_id",
    })


def enrich(df, election_date, overrides, name_col="name"):
    """Add incumbent_* columns, is_incumbent and incumbent_running.

    `overrides` is a set of (office, district, name) tuples, where name is the
    candidate's name as it appears in `name_col`.
    """
    inc = prior_winners(election_date)

    df = df.copy()
    df["dkey"] = df["district_id"].fillna(-1)
    df = df.merge(inc, on=["office_id", "dkey"], how="left")

    df["is_incumbent"] = df.apply(
        lambda r: int(
            ((r["office"], r["district"], r[name_col]) in overrides)
            or (bool(first_last(r[name_col]))
                and first_last(r[name_col]) == first_last(r["incumbent_name"]))
        ),
        axis=1,
    )
    # Is the incumbent among this race's candidates (i.e., seat is defended)?
    defended = (df[df["is_incumbent"] == 1]
                .groupby(["office_id", "dkey"]).size())
    df["incumbent_running"] = df.apply(
        lambda r: int((r["office_id"], r["dkey"]) in defended.index), axis=1)

    df["incumbent_id"] = df["incumbent_id"].astype("Int64")
    return df.drop(columns=["dkey"])
