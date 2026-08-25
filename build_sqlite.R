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

## --- primary_election ---
primary_election_file <- "data/ma_primary_election_summaries.csv.gz"
if (file.exists(primary_election_file)) {
    cat("Loading primary_election...\n")
    primary_election <- read_csv(
        primary_election_file,
        show_col_types = FALSE
    )
    dbWriteTable(
        elec_db,
        "primary_election",
        (primary_election %>%
         mutate(election_date = format(election_date, "%Y-%m-%d"))),
        field.types = c(
            office_id = "INTEGER",
            district_id = "INTEGER",
            election_id = "INTEGER",
            total_votes = "INTEGER",
            blank_votes = "INTEGER",
            all_other_votes = "INTEGER",
            num_candidates = "INTEGER",
            winner_id = "INTEGER",
            winner_votes = "INTEGER"
        )
    )
    dbExecute(
        elec_db,
        "CREATE UNIQUE INDEX idx_primary_election_pk
             ON primary_election (election_id)"
    )
} else {
    cat(str_glue("Skipping primary_election ({primary_election_file} not found).\n\n"))
}

## --- primary_election_candidate ---
primary_candidate_file <- "data/ma_primary_election_candidates.csv.gz"
if (file.exists(primary_candidate_file)) {
    cat("Loading primary_election_candidate...\n")
    primary_election_candidate <- read_csv(
        primary_candidate_file,
        show_col_types = FALSE
    )
    dbWriteTable(
        elec_db,
        "primary_election_candidate",
        (primary_election_candidate %>%
         mutate(election_date = format(election_date, "%Y-%m-%d"))),
        field.types = c(
            office_id = "INTEGER",
            district_id = "INTEGER",
            election_id = "INTEGER",
            total_votes = "INTEGER",
            blank_votes = "INTEGER",
            all_other_votes = "INTEGER",
            num_candidates = "INTEGER",
            candidate_id = "INTEGER",
            num_votes = "INTEGER",
            num_elections = "INTEGER",
            winner_id = "INTEGER",
            winner_votes = "INTEGER"
        )
    )
    dbExecute(
        elec_db,
        "CREATE UNIQUE INDEX idx_primary_election_candidate_pk
             ON primary_election_candidate (election_id, candidate_id)"
    )
} else {
    cat(str_glue("Skipping primary_election_candidate ({primary_candidate_file} not found).\n\n"))
}

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

## --- district_pvi ---
district_pvi_file <- "data/pvi/ma_district_pvi.csv.gz"
if (file.exists(district_pvi_file)) {
    cat("Loading district_pvi...\n")
    district_pvi <- read_csv(
        district_pvi_file,
        show_col_types = FALSE
    )
    dbWriteTable(
        elec_db,
        "district_pvi",
        district_pvi,
        field.types = c(pvi_year = "INTEGER")
    )
    dbExecute(
        elec_db,
        "CREATE UNIQUE INDEX idx_district_pvi_pk
             ON district_pvi (pvi_year, office, district)"
    )
} else {
    cat(str_glue("Skipping district_pvi ({district_pvi_file} not found).\n\n"))
}

## --- precinct_district ---
precinct_district_file <- "data/precinct/ma_precinct_district.csv.gz"
if (file.exists(precinct_district_file)) {
    cat("Loading precinct_district...\n")
    precinct_district <- read_csv(
        precinct_district_file,
        show_col_types = FALSE
    )
    dbWriteTable(
        elec_db,
        "precinct_district",
        precinct_district,
        field.types = c(redistricting_year = "INTEGER")
    )
    dbExecute(
        elec_db,
        "CREATE UNIQUE INDEX idx_precinct_district_pk
             ON precinct_district
                (redistricting_year, city_town, ward, precinct)"
    )
} else {
    cat(str_glue("Skipping precinct_district ({precinct_district_file} not found).\n\n"))
}

## --- precinct_presidential_vote ---
precinct_presidential_vote_file <- "data/precinct/ma_precinct_presidential_vote.csv.gz"
if (file.exists(precinct_presidential_vote_file)) {
    cat("Loading precinct_presidential_vote...\n")
    precinct_presidential_vote <- read_csv(
        precinct_presidential_vote_file,
        show_col_types = FALSE
    )
    dbWriteTable(
        elec_db,
        "precinct_presidential_vote",
        precinct_presidential_vote,
        field.types = c(
            election_year = "INTEGER",
            redistricting_year = "INTEGER"
        )
    )
    dbExecute(
        elec_db,
        "CREATE UNIQUE INDEX idx_precinct_presidential_vote_pk
             ON precinct_presidential_vote
                (election_year, redistricting_year, city_town, ward, precinct)"
    )
} else {
    cat(str_glue("Skipping precinct_presidential_vote ({precinct_presidential_vote_file} not found).\n\n"))
}

## --- national_presidential_baseline ---
national_baseline_file <- "data/precinct/ma_national_presidential_baseline.csv"
if (file.exists(national_baseline_file)) {
    cat("Loading national_presidential_baseline...\n")
    national_presidential_baseline <- read_csv(
        national_baseline_file,
        show_col_types = FALSE
    )
    dbWriteTable(
        elec_db,
        "national_presidential_baseline",
        national_presidential_baseline,
        field.types = c(
            election_year = "INTEGER",
            dem_votes = "INTEGER",
            gop_votes = "INTEGER"
        )
    )
} else {
    cat(str_glue("Skipping national_presidential_baseline ({national_baseline_file} not found).\n\n"))
}

## --- district_summary ---
district_summary_file <- "data/district_summaries.csv"
if (file.exists(district_summary_file)) {
    cat("Loading district_summary...\n")
    district_summary <- read_csv(
        district_summary_file,
        show_col_types = FALSE
    )
    dbWriteTable(
        elec_db,
        "district_summary",
        (district_summary %>%
         mutate(effective_date = format(effective_date, "%Y-%m-%d")))
    )
    dbExecute(
        elec_db,
        "CREATE UNIQUE INDEX idx_district_summary_pk
             ON district_summary (office, district, effective_date)"
    )
} else {
    cat(str_glue("Skipping district_summary ({district_summary_file} not found).\n\n"))
}

dbDisconnect(elec_db)

cat("Done.\n\n")
