# Massachusetts Election Database

Tools for querying MA election results and producing a database of
elections and candidates

* [`election_stats.py`](election_stats.py) - Query election data from
  [electionstats.state.ma.us](https://electionstats.state.ma.us),
  flattening, renaming, and writing to output files.

* [`elections.R`](elections.R) - Transform the queried data into
  summarized election results suitable for analysis. Writes gzipped
  CSVs to `data/`.
  * [`data/ma_general_election_candidates.csv.gz`](data/ma_general_election_candidates.csv.gz)
  * [`data/ma_general_election_summaries.csv.gz`](data/ma_general_election_summaries.csv.gz)

* [`demographics/ma_census.R`](demographics/ma_census.R) - Build
  district- and precinct-level demographics from the U.S. Census ACS
  5-year data. Requires a `CENSUS_API_KEY` - see
  [`demographics/README.md`](demographics/README.md).
  * [`data/demographics/ma_district_demographics.csv.gz`](data/demographics/ma_district_demographics.csv.gz)
  * [`data/demographics/ma_precinct_demographics.csv.gz`](data/demographics/ma_precinct_demographics.csv.gz)
  * [`data/demographics/ma_city_town_demographics.csv.gz`](data/demographics/ma_city_town_demographics.csv.gz)

* [`pvi/ma_pvi.R`](pvi/ma_pvi.R) - Reshape multi-year district-level
  Partisan Voting Index (PVI) data from a sibling
  [mapoli](https://github.com/bwbensonjr/mapoli) checkout into a single
  unified CSV - see [`pvi/README.md`](pvi/README.md).
  * [`data/pvi/ma_district_pvi.csv.gz`](data/pvi/ma_district_pvi.csv.gz)

* [`build_sqlite.R`](build_sqlite.R) - Read the CSVs produced above
  and assemble [`data/ma_elections.sqlite`](data/ma_elections.sqlite).
  This is the single writer for the SQLite database.

## Running the tools

Full rebuild:

```
$ make all
```

Individual stages:

```
$ python election_stats.py            # refetch raw election data
$ Rscript elections.R                 # produce election summary CSVs
$ Rscript demographics/ma_census.R    # produce demographics CSVs
$ Rscript pvi/ma_pvi.R                # produce district PVI CSV
$ Rscript build_sqlite.R              # assemble SQLite database
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
