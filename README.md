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

## TODO

- [ ] Complete primary election and candidate data refinement
- [ ] Add primary elections to SQLite database
- [ ] Addprecinct-level results
- [x] Specify `INTEGER` data types in SQLite where appropriate
