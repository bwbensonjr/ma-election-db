library(tidyverse)
library(lubridate)
library(DBI)

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
                      col_types=list(is_special = col_logical())) %>%
    # Filter out a couple of specials missing dates
    filter(!is.na(election_date)) %>% 
    rename(party = party_primary) %>%
    mutate(party = standardize_party(party),
           is_special = replace_na(is_special, FALSE),
           election_date = date_fixes(election_date))

cat(str_glue("Read {nrow(elections)} elections.\n\n"))

candidate_display <- function(name, party_abbr, city_town) {
    if_else(is.na(city_town),
            str_glue("{name} ({party_abbr})"),
            str_glue("{name} ({party_abbr}-{city_town})"))
}

candidates_in_file <- "data/ma_primary_candidates_1996_2024.csv.gz"
cat(str_glue("Reading candidates from {candidates_in_file}...\n\n"))

candidates <- read_csv(candidates_in_file,
                       col_types=list(winner = col_logical(),
                                      is_write_in = col_logical())) %>%
    select(-party) %>%
    mutate(city_town = str_replace(city_state, ", MA", ""),
           winner = replace_na(winner, FALSE),
           is_write_in = replace_na(is_write_in, FALSE))

cat(str_glue("Read {nrow(candidates)} candidates.\n\n"))

elections_candidates <- elections %>%
    nest_join(candidates,
              by="election_id",
              name="candidate") %>%
    mutate(num_candidates = map_int(candidate, nrow)) %>%
    filter(num_candidates > 0)

elections_candidates %>%
    filter(election_date == "2022-09-06",
           office == "State Representative",
           district_display == "37th Middlesex")

district_elections <- elections_candidates %>%
    select(office_branch,
           office_id,
           office,
           district,
           district_display,
           district_id,
           election_date,
           is_special,
           party,
           num_candidates) %>%
    nest(election = c(party, num_candidates)) %>%
    mutate(contested = map_lgl(election, ~(max(.x$num_candidates) > 1)))

district_elections %>%
    filter(election_date == "2022-09-06",
           office == "State Representative",
           district_display == "37th Middlesex")

district_elections %>%
    filter(election_date == "2022-09-06",
           office == "State Representative",
           contested)

incumbents <- read_csv("data/ma_general_election_candidates.csv.gz")  %>%
    filter(is_incumbent)
