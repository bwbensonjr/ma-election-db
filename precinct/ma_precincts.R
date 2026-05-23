## Assembles precinct-level data from upstream mapoli outputs into the
## unified ma-election-db schema. Reads four wide-format precinct files
## from a sibling mapoli checkout and produces three normalized CSVs.
##
## Inputs (read from ../mapoli/pvi/):
##   ma_precincts_districts_12_16_pres.csv  (pre-2021 districts; 2012, 2016)
##   ma_precincts_districts_16_20_pres.csv  (pre-2021 districts; 2016, 2020)
##   ma_precincts_districts_pres_2022.csv   (post-2021 districts; 2016, 2020)
##   ma_precincts_districts_pres_2024.csv   (post-2021 districts; 2016, 2020, 2024)
##
## Outputs:
##   data/precinct/ma_precinct_district.csv.gz
##     Columns: redistricting_year, city_town, ward, precinct,
##              state_rep, state_senate, us_house, gov_council
##   data/precinct/ma_precinct_presidential_vote.csv.gz
##     Columns: election_year, redistricting_year, city_town, ward,
##              precinct, dem_votes, gop_votes
##   data/precinct/ma_national_presidential_baseline.csv
##     Columns: election_year, dem_votes, gop_votes
##
## Within a redistricting cycle, where the same (precinct) or
## (election_year, precinct) appears in multiple files, the most recent
## file wins.

library(tidyverse)

mapoli_pvi_dir <- "../mapoli/pvi"

## --- File metadata: path, redistricting cycle, the elections it carries ---
## Order matters: later files within a cycle override earlier ones for
## both district assignments and vote totals.
input_specs <- tribble(
    ~path,                                    ~redistricting_year, ~rank,
    "ma_precincts_districts_12_16_pres.csv",  2011L,               1L,
    "ma_precincts_districts_16_20_pres.csv",  2011L,               2L,
    "ma_precincts_districts_pres_2022.csv",   2021L,               1L,
    "ma_precincts_districts_pres_2024.csv",   2021L,               2L
) %>% mutate(path = file.path(mapoli_pvi_dir, path))

for (f in input_specs$path) {
    if (!file.exists(f)) {
        stop(str_glue(
            "Required mapoli input not found: {f}\n",
            "Ensure the mapoli repo is checked out at ../mapoli."
        ))
    }
}

## --- Header normalization ---
## Pre-2021 files use "City/Town", "Ward", "Pct", "State Rep" etc.
## Post-2021 files use "city_town", "ward", "precinct", "State_Rep" etc.
## Normalize everything to snake_case.
normalize_headers <- function(df) {
    df %>% rename_with(~ .x %>%
        str_replace_all("/", "_") %>%
        str_replace_all(" ", "_") %>%
        str_to_lower()) %>%
        rename(precinct = any_of(c("pct"))) %>%
        rename(any_of(c(
            state_rep    = "state_rep",
            state_senate = "state_senate",
            us_house     = "us_house",
            gov_council  = "gov_council"
        )))
}

## Vote columns are named like Biden_20, Trump_24, Obama_12, Romney_12,
## Clinton_16, Trump_16. Map each to (election_year, party).
vote_col_meta <- tribble(
    ~vote_col,    ~election_year, ~party,
    "obama_12",   2012L,          "dem",
    "romney_12",  2012L,          "gop",
    "clinton_16", 2016L,          "dem",
    "trump_16",   2016L,          "gop",
    "biden_20",   2020L,          "dem",
    "trump_20",   2020L,          "gop",
    "harris_24",  2024L,          "dem",
    "trump_24",   2024L,          "gop"
)

read_one <- function(spec) {
    cat(str_glue("Reading {spec$path}...\n\n"))
    df <- read_csv(spec$path, show_col_types = FALSE) %>%
        normalize_headers() %>%
        mutate(
            redistricting_year = spec$redistricting_year,
            file_rank = spec$rank,
            ward = as.character(ward),
            precinct = as.character(precinct),
            across(any_of(c("state_rep", "state_senate",
                            "us_house", "gov_council")),
                   as.character)
        )
    df
}

raw <- input_specs %>%
    rowwise() %>%
    group_split() %>%
    map(read_one)

## --- Build precinct_district output ---
## One row per (redistricting_year, city_town, ward, precinct), keeping
## district assignments from the most recent file in each cycle.
district_keys <- c("redistricting_year", "city_town", "ward", "precinct")
district_cols <- c("state_rep", "state_senate", "us_house", "gov_council")

precinct_district <- raw %>%
    map(~ .x %>% select(all_of(c(district_keys, district_cols, "file_rank")))) %>%
    bind_rows() %>%
    arrange(redistricting_year, city_town, ward, precinct, desc(file_rank)) %>%
    distinct(across(all_of(district_keys)), .keep_all = TRUE) %>%
    select(-file_rank) %>%
    arrange(redistricting_year, city_town, ward, precinct)

## --- Build precinct_presidential_vote output ---
## Pivot vote columns to long. Within a cycle, prefer the most recent
## file per (election_year, precinct).
pivot_one <- function(df) {
    vote_cols_present <- intersect(vote_col_meta$vote_col, names(df))
    df %>%
        select(all_of(c(district_keys, "file_rank", vote_cols_present))) %>%
        pivot_longer(
            cols = all_of(vote_cols_present),
            names_to = "vote_col",
            values_to = "votes"
        ) %>%
        left_join(vote_col_meta, by = "vote_col") %>%
        select(-vote_col) %>%
        pivot_wider(names_from = party, values_from = votes,
                    names_glue = "{party}_votes")
}

precinct_presidential_vote <- raw %>%
    map(pivot_one) %>%
    bind_rows() %>%
    arrange(election_year, redistricting_year, city_town, ward, precinct,
            desc(file_rank)) %>%
    distinct(election_year, redistricting_year, city_town, ward, precinct,
             .keep_all = TRUE) %>%
    select(election_year, redistricting_year, city_town, ward, precinct,
           dem_votes, gop_votes) %>%
    arrange(election_year, redistricting_year, city_town, ward, precinct)

## --- National presidential baseline ---
## US totals for each presidential election that appears in the precinct
## files. Used by PVI calculation.
##   2024, 2020, 2016: from mapoli/R/pvi_utils.R (lines 6-12)
##   2012: official certified totals (Obama 65,915,795; Romney 60,933,504)
national_presidential_baseline <- tribble(
    ~election_year, ~dem_votes, ~gop_votes,
    2012L,          65915795L,  60933504L,
    2016L,          65853514L,  62984828L,
    2020L,          81281502L,  74222593L,
    2024L,          75017626L,  77301997L
)

## --- Write outputs ---
output_dir <- "data/precinct"
if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
}

pd_file <- file.path(output_dir, "ma_precinct_district.csv.gz")
cat(str_glue("Writing {pd_file} ({nrow(precinct_district)} rows)...\n\n"))
write_csv(precinct_district, pd_file)

ppv_file <- file.path(output_dir, "ma_precinct_presidential_vote.csv.gz")
cat(str_glue("Writing {ppv_file} ({nrow(precinct_presidential_vote)} rows)...\n\n"))
write_csv(precinct_presidential_vote, ppv_file)

npb_file <- file.path(output_dir, "ma_national_presidential_baseline.csv")
cat(str_glue("Writing {npb_file} ({nrow(national_presidential_baseline)} rows)...\n\n"))
write_csv(national_presidential_baseline, npb_file)

cat("Done.\n")
