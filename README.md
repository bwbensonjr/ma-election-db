# Massachusetts Election Database

Tools for querying MA election results and producing a database of
elections and candidates

* [`election_stats.py`](election_stats.py) - Query election data from
  [electionstats.state.ma.us](https://electionstats.state.ma.us),
  flattening, renaming, and writing to output files.

* [`elections.R`](elections.R) - Transform the queried data into
  summarized election results into a format suitable for
  analysis. This outputs to summary files and a SQLite database with
  tables corresponding to the output files.
  * [`data/ma_general_election_candidates_1990_2024.csv.gz`](data/ma_general_election_candidates_1990_2024.csv.gz)
  * [`data/ma_general_election_summaries_1990_2024.csv.gz`](data/ma_general_election_summaries_1990_2024.csv.gz)
  * [`data/ma_elections.sqlite`](data/ma_elections.sqlite)

## Running the tools

```
$ python election_stats.py
$ Rscript elections.R
```

## Database browser

Make queries to the database using the [`sqlime`](https://sqlime.org) SQLite playground.

* [MA Election DB playground](https://sqlime.org/#https://bwbensonjr.github.io/ma-election-db/data/ma_elections.sqlite)

## Incumbency

The notion of incumbency is not represented directly in the election
data provided by
[electionstats.state.ma.us](https://electionstats.state.ma.us). Our
initial model of incumbency only handled the most common case where
the person who is currently representing the seat of a particular
office and district is a candidate for that same office and district
in which they would be considered the incumbent.

The simple office-district model of incumbency is complicated by
redistricting where the number and composition of districts for a
paricular office can change based on the decennial census and
redistricting process. Redistricting can result in a situation where
an office holder is running for a district with a different name, in
which case they should be considered an incumbent.

An even more complicated case is one where two current office holders
for the same office are running against each other for a new district
in which they both reside. This multi-incumbent election would take
place in the primary if the two office holders are in the same
party or in the general if they did not share a party designation.

## TODO

- [ ] Complete primary election and candidate data refinement
- [ ] Add primary elections to SQLite database
- [ ] Addprecinct-level results
- [x] Specify `INTEGER` data types in SQLite where appropriate
- [ ] Refine notion of incumbency to handle multiple incumbents in single election
