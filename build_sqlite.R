## Assembles data/ma_elections.sqlite from the CSVs produced by each
## domain pipeline. This is the single writer for the SQLite database;
## domain scripts (elections.R, ma_census.R, ...) only write CSVs.
##
## Adding a new domain: add a read_csv + dbWriteTable block here, and
## optionally a CREATE UNIQUE INDEX for the logical primary key.

library(tidyverse)
library(DBI)

sqlite_db_file <- "data/ma_elections.sqlite"
if (file.exists(sqlite_db_file)) {
    cat(str_glue("Deleting {sqlite_db_file}...\n\n"))
    file.remove(sqlite_db_file)
}
cat(str_glue("Writing {sqlite_db_file}...\n\n"))
elec_db <- dbConnect(
    drv=RSQLite::SQLite(),
    sqlite_db_file,
    extended_types=TRUE
)

## --- general_election ---
cat("Loading general_election...\n")
general_election <- read_csv(
    "data/ma_general_election_summaries.csv.gz",
    show_col_types = FALSE
)
dbWriteTable(
    elec_db,
    "general_election",
    (general_election %>%
     mutate(election_date = format(election_date, "%Y-%m-%d"))),
    field.types = c(
        office_id = "INTEGER",
        district_id = "INTEGER",
        election_id = "INTEGER",
        total_votes = "INTEGER",
        blank_votes = "INTEGER",
        all_other_votes = "INTEGER",
        num_candidates = "INTEGER",
        num_incumbents = "INTEGER",
        id_winner = "INTEGER",
        votes_winner = "INTEGER",
        id_incumbent = "INTEGER",
        id_dem = "INTEGER",
        votes_dem = "INTEGER",
        id_gop = "INTEGER",
        votes_gop = "INTEGER",
        id_third_party = "INTEGER",
        votes_third_party = "INTEGER",
        id_write_in = "INTEGER",
        votes_write_in = "INTEGER"
    )
)

## --- election_candidate ---
cat("Loading election_candidate...\n")
election_candidate <- read_csv(
    "data/ma_general_election_candidates.csv.gz",
    show_col_types = FALSE
)
dbWriteTable(
    elec_db,
    "election_candidate",
    (election_candidate %>%
     select(-any_of(c("is_first_cycle", "num_incumbents")))),
    field.types = c(
        election_id = "INTEGER",
        candidate_id = "INTEGER",
        num_elections = "INTEGER",
        num_votes = "INTEGER"
    )
)

## --- district_demographics ---
district_demographics_file <- "data/demographics/ma_district_demographics.csv.gz"
if (file.exists(district_demographics_file)) {
    cat("Loading district_demographics...\n")
    district_demographics <- read_csv(
        district_demographics_file,
        show_col_types = FALSE
    )
    dbWriteTable(
        elec_db,
        "district_demographics",
        district_demographics,
        field.types = c(census_year = "INTEGER")
    )
    dbExecute(
        elec_db,
        "CREATE UNIQUE INDEX idx_district_demographics_pk
             ON district_demographics (census_year, office, district)"
    )
} else {
    cat(str_glue("Skipping district_demographics ({district_demographics_file} not found).\n\n"))
}

## --- precinct_demographics ---
precinct_demographics_file <- "data/demographics/ma_precinct_demographics.csv.gz"
if (file.exists(precinct_demographics_file)) {
    cat("Loading precinct_demographics...\n")
    precinct_demographics <- read_csv(
        precinct_demographics_file,
        show_col_types = FALSE
    )
    dbWriteTable(
        elec_db,
        "precinct_demographics",
        precinct_demographics,
        field.types = c(census_year = "INTEGER")
    )
    dbExecute(
        elec_db,
        "CREATE UNIQUE INDEX idx_precinct_demographics_pk
             ON precinct_demographics (census_year, city_town, ward, precinct)"
    )
} else {
    cat(str_glue("Skipping precinct_demographics ({precinct_demographics_file} not found).\n\n"))
}

dbDisconnect(elec_db)

cat("Done.\n\n")
