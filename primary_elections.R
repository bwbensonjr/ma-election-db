library(tidyverse)
library(lubridate)
library(DBI)

## Load candidate ID mapping to handle duplicate IDs from name variations
## This ensures the same person always has the same canonical ID and name
candidate_id_map_file <- "data/candidate-id-map.csv"
if (file.exists(candidate_id_map_file)) {
    candidate_id_map <- read_csv(candidate_id_map_file,
                                  show_col_types = FALSE) |>
        select(id_dup, id_canonical, name_canonical)
} else {
    candidate_id_map <- tibble(id_dup = integer(), id_canonical = integer(), name_canonical = character())
}

## Apply candidate ID mapping globally
apply_candidate_id_mapping <- function(df) {
    df |>
        left_join(candidate_id_map, by = c("candidate_id" = "id_dup")) |>
        mutate(candidate_id = coalesce(id_canonical, candidate_id),
               name = coalesce(name_canonical, name)) |>
        select(-id_canonical, -name_canonical)
}

date_fixes <- function(election_date) {
    case_when(
    (election_date == "2000-11-07") ~ ymd("2000-09-19"),
    (election_date == "1996-11-05") ~ ymd("1996-03-05"),
    TRUE ~ election_date,
    )
}

standardize_party <- function(party) {
    case_when(
        party == "Green-rainbow" ~ "Green-Rainbow",
        party == "United Independent Party" ~ "United Independent",
        TRUE ~ party,
    )
}

party_abbrev <- function(party) {
    case_when(
        party == "Democratic" ~ "D",
        party == "Republican" ~ "R",
        party == "Libertarian" ~ "L",
        party == "Green-Rainbow" ~ "GR",
        party == "Green" ~ "G",
        party == "United Independent" ~ "UI",
        TRUE ~ "Other",
    )
}

## The two U.S. Senate seats can be differentiated by
## their "Class" as defined on the Wikipedia page:
## https://en.wikipedia.org/wiki/List_of_United_States_senators_from_Massachusetts
##
senate_election_class <- function(election_date) {
    case_when(
    (election_date == "2010-01-19") ~ 1,
    (election_date == "2013-06-25") ~ 2,
    ((year(election_date) - 1994) %% 6) == 0 ~ 1,
    ((year(election_date) - 1990) %% 6) == 0 ~ 2)
}

elections_in_file <- "data/ma_primary_elections.csv.gz"
cat(str_glue("Reading primary elections from {elections_in_file}...\n\n"))

elections <- read_csv(elections_in_file,
                      col_types=list(is_special = col_logical())) |>
    # Filter out a couple of specials missing dates
    filter(!is.na(election_date)) |> 
    rename(party = party_primary) |>
    mutate(party = standardize_party(party),
           is_special = replace_na(is_special, FALSE),
           election_date = date_fixes(election_date))

cat(str_glue("Read {nrow(elections)} elections.\n\n"))

candidate_display <- function(name, party_abbr, city_town) {
    if_else(is.na(city_town),
            str_glue("{name} ({party_abbr})"),
            str_glue("{name} ({party_abbr}-{city_town})"))
}

candidates_in_file <- "data/ma_primary_candidates.csv.gz"
cat(str_glue("Reading candidates from {candidates_in_file}...\n\n"))

candidates <- read_csv(candidates_in_file,
    col_types = list(
        is_winner = col_logical(),
        is_write_in = col_logical()
    )
) |>
    apply_candidate_id_mapping() |>
    select(-party) |>
    mutate(
        city_town = str_replace(city_state, ", MA", ""),
        is_winner = replace_na(is_winner, FALSE),
        is_write_in = replace_na(is_write_in, FALSE)
    ) |>
    select(-city_state)


cat(str_glue("Read {nrow(candidates)} candidates.\n\n"))

elections_candidates <- elections |>
    ## Inner join to leave out elections with no candidates
    ## and candidates with no election.
    inner_join(candidates, by = "election_id") |>
    group_by(election_id) |>
    mutate(
        party_abbr = party_abbrev(party),
        display_name = candidate_display(name, party_abbr, city_town),
        percent = num_votes / (total_votes - blank_votes),
        num_candidates = n()
    ) |>
    ungroup()

# elections_candidates |>
#     filter(election_date == "2022-09-06",
#            office == "State Representative",
#            district_display == "37th Middlesex")

num_winners <- function(cands) {
    cands |>
        filter(is_winner) |>
        nrow()
}

winner_id <- function(cands) {
    winners <- cands |> filter(is_winner)
    if (nrow(winners) == 0) return(NA_real_)
    winners$candidate_id[1]
}

winner_name <- function(cands) {
    winners <- cands |> filter(is_winner)
    if (nrow(winners) == 0) return(NA_character_)
    winners$display_name[1]
}

winner_num_votes <- function(cands) {
    winners <- cands |> filter(is_winner)
    if (nrow(winners) == 0) return(NA_integer_)
    as.integer(winners$num_votes[1])
}

winner_percent <- function(cands) {
    winners <- cands |> filter(is_winner)
    if (nrow(winners) == 0) return(NA_real_)
    winners$percent[1]
}

cat(str_glue("Summarizing elections...\n\n"))

elections_summaries <- elections_candidates |>
    nest(candidate = c(
        candidate_id,
        name,
        display_name,
        first_name,
        middle_name,
        last_name,
        num_votes,
        percent,
        is_winner,
        is_write_in,
        street_addr,
        city_town,
        num_elections
    )) |>
    mutate(
        winner_id = map_dbl(candidate, winner_id),
        winner = map_chr(candidate, winner_name),
        winner_votes = map_int(candidate, winner_num_votes),
        winner_percent = map_dbl(candidate, winner_percent)
    )

primary_election_summaries_out_file <- "data/ma_primary_election_summaries.csv.gz"
cat(str_glue("Writing primary election summaries to {primary_election_summaries_out_file}...\n\n"))

elections_summaries |>
    select(-candidate) |>
    write_csv(primary_election_summaries_out_file)

primary_election_candidates_out_file <- "data/ma_primary_election_candidates.csv.gz"
cat(str_glue("Writing primary election candidates to {primary_election_candidates_out_file}...\n\n"))

elections_summaries |>
    unnest(candidate) |>
    write_csv(primary_election_candidates_out_file)

