## This script takes the raw election and candidate information
## from the data files and produces election-level and candidate-level
## summaries.

library(tidyverse)
library(lubridate)
library(DBI)
library(writexl)

candidate_fixes <- function(df) {
    df %>%
        mutate(is_write_in = case_when(
                 ((election_id == 154409) & (candidate_id == 89485)) ~ TRUE,
                 TRUE ~ is_write_in),
             name = case_when(
                 ((election_id == 154409) & (candidate_id == 78007)) ~ "Susannah M. Whipps",
                 ((election_id == 154549) & (candidate_id = 88406)) ~ "Bradley H. Jones, Jr.",
                 ((election_id == 140828) & (candidate_id = 82206)) ~ "Steven G. Xiarhos",
                 TRUE ~ name),
             winner = case_when(
                 ((election_id == 96321) & (candidate_id == 71530)) ~ FALSE,
                 TRUE ~ winner),
             candidate_id = case_when(
                 ((election_id == 154549) & (candidate_id = 88406)) ~ 62825,
                 ((election_id == 154423) & (candidate_id = 88326)) ~ 82206,
                 TRUE ~ candidate_id),
             num_elections = case_when(
                 (candidate_id == 62825) ~ 33,
                 (candidate_id == 82206) ~ 4,
                 TRUE ~ num_elections))
}

## candidate_fixes <- function(df) {
##     df %>%
##         mutate(party = case_when(
##                 ((election_id == 94958) & (candidate_id == 70862)) ~ "Republican",
##                 ((election_id == 94964) & (candidate_id == 70867)) ~ "Republican",
##                 ((election_id == 95845) & (candidate_id == 71320)) ~ "Republican",
##                 ((election_id == 95959) & (candidate_id == 71358)) ~ "Republican",
##                 ((election_id == 99393) & (candidate_id == 73032)) ~ "Republican",
##                 ((election_id == 99105) & (candidate_id == 63034)) ~ "Democratic",
##                 ((election_id == 96474) & (candidate_id == 63226)) ~ "Democratic",
##                 ((election_id == 96531) & (candidate_id == 72743)) ~ "Republican",
##                 ((election_id == 95680) & (candidate_id == 68209)) ~ "Democratic",
##                 ((election_id == 95839) & (candidate_id == 63571)) ~ "Democratic",
##                 TRUE ~ party),
##              is_write_in = case_when(
##                  ((election_id == 111742) & (candidate_id == 72665)) ~ TRUE,
##                  ((election_id == 154409) & (candidate_id == 89485)) ~ TRUE,
##                  TRUE ~ is_write_in),
##              name = case_when(
##                  ((election_id == 154409) & (candidate_id == 78007)) ~ "Susannah M. Whipps",
##                  TRUE ~ name),
##              winner = case_when(
##                  ((election_id == 96321) & (candidate_id == 71530)) ~ FALSE,
##                  TRUE ~ winner))
## }

## election_fixes <- function(df) {
##     df %>%
##         filter(election_id != 98279) %>%
##         mutate(election_date = case_when(
##                    (election_id %in% c(130117, 130120)) ~ ymd("1996-11-05"),
##                    TRUE ~ election_date))
## }

senate_election_class <- function(election_date) {
    case_when(
    (election_date == "2010-01-19") ~ 1,
    (election_date == "2013-06-25") ~ 2,
    ((year(election_date) - 1994) %% 6) == 0 ~ 1,
    ((year(election_date) - 1990) %% 6) == 0 ~ 2)
}

add_senate_seat_as_district <- function(df) {
    df %>%
        mutate(district_id = if_else(office == "U.S. Senate",
                                     senate_election_class(election_date),
                                     district_id),
               district = if_else(office == "U.S. Senate",
                                  str_glue("Class {district_id}"),
                                  district),
               district_display = if_else(office == "U.S. Senate",
                                          str_glue("Class {district_id}"),
                                          district_display))
}

elections_in_file <- "data/ma_elections_1990_2024.csv.gz"
cat(str_glue("Reading elections from {elections_in_file}...\n\n"))

elections <- read_csv(elections_in_file,
                      col_types=list(party_primary = col_logical(),
                                     is_special = col_logical())) %>%
    mutate(party_primary = replace_na(party_primary, FALSE),
           is_special = replace_na(is_special, FALSE)) %>%
    add_senate_seat_as_district()

cat(str_glue("Read {nrow(elections)} elections.\n\n"))

candidates_in_file <- "data/ma_candidates_1990_2024.csv.gz"
cat(str_glue("Reading candidates from {candidates_in_file}...\n\n"))

candidates <- read_csv(candidates_in_file,
                       col_types=list(winner = col_logical(),
                                      is_write_in = col_logical())) %>%
    candidate_fixes() %>%
    mutate(party = replace_na(party, "None"),
           city_town = str_replace(city_state, ", MA", ""),
           winner = replace_na(winner, FALSE),
           is_write_in = replace_na(is_write_in, FALSE),
           party_role = case_when(
               is_write_in ~ "write_in",
               (party == "Democratic") ~ "dem",
               (party == "Republican") ~ "gop",
               TRUE ~ "third_party"))

cat(str_glue("Read {nrow(candidates)} candidates.\n\n"))


## Attempt to determine incumbency putting each
## candidates with their election and filtering
## for only winners, then grouping winners by office,
## sorting by election date and removing the first
## row.
candidate_is_incumbent <- elections %>%
    left_join(candidates, by="election_id") %>%
    group_by(office_id, candidate_id) %>%
    arrange(election_date) %>%
    mutate(is_incumbent = lag(winner)) %>%
    ungroup() %>%
    select(election_id, candidate_id, is_incumbent)

## This handles the special cases of candidates having been
## elected to a particular office, being out of office, then
## coming back. This could be handled in the general case by
## looking at the previous election for the same district, but
## this might not work because of redistricting.
incumbency_fixes <- function(candidates) {
    candidates %>%
        mutate(is_incumbent = case_when(
        ((election_id == 98267) & (candidate_id == 63651)) ~ FALSE,
        ((election_id == 98501) & (candidate_id == 62827)) ~ FALSE,
        ((election_id == 103356) & (candidate_id == 63232)) ~ FALSE,
        ((election_id == 126287) & (candidate_id == 63121)) ~ FALSE,
        ((election_id == 130480) & (candidate_id == 62994)) ~ FALSE,
        TRUE ~ is_incumbent))
}

candidates_w_inc <- candidates %>%
    left_join(candidate_is_incumbent,
              by=c("election_id", "candidate_id")) %>%
    mutate(is_incumbent = replace_na(is_incumbent, FALSE)) %>%
    incumbency_fixes()

elections_candidates <- elections %>%
    nest_join(candidates_w_inc,
              by="election_id",
              name="candidate")

## Find mistaken incumbency duplicates
## num_incumbents <- function(cands) {
##     incumbents <- cands %>%
##         filter(is_incumbent)
##     nrow(incumbents)
## }

## elecs_with_dup_incumbents <- elections_candidates %>%
##     mutate(num_incumbents = map_dbl(candidate, num_incumbents)) %>%
##     filter(num_incumbents > 1)

## ## If there are dup_incumbents, run this for more info
## elecs_with_dup_incumbents %>%
##     unnest(candidate) %>%
##     select(office,
##            district_display,
##            district_id,
##            election_id,
##            election_date,
##            candidate_id,
##            name,
##            party_role)

extract_summaries <- function(cands) {
    dem <- filter(cands, party_role == "dem")
    gop <- filter(cands, party_role == "gop")
    third_party <- cands %>%
        filter(party_role == "third_party") %>%
        arrange(desc(num_votes)) %>%
        slice(1)
    write_in <- cands %>%
        filter(party_role == "write_in") %>%
        arrange(desc(num_votes)) %>%
        slice(1)
    winner <- filter(cands, winner) %>%
        mutate(party_role = "winner", percent = 0)
    incumbent <- filter(cands, is_incumbent) %>%
        mutate(party_role = "incumbent", percent = 0)
    rbind((rbind(dem, gop, third_party, write_in) %>%
           mutate(percent = num_votes/sum(num_votes))),
          winner,
          incumbent) %>%
        select(party_role,
               party,
               name,
               votes=num_votes,
               percent,
               city_town,
               id=candidate_id) %>%
        pivot_wider(names_from=party_role,
                    values_from=c(name, votes, percent,
                                  party, city_town, id)) %>%
        select(-any_of(c("party_dem",
                         "party_gop",
                         "votes_incumbent",
                         "votes_winner",
                         "percent_incumbent",
                         "percent_winner")))
}

cat("Generating summaries...\n\n")

election_summaries <- elections_candidates %>%
    mutate(num_candidates = map_int(candidate, nrow),
           candidate_summary = map(candidate, extract_summaries)) %>%
    select(-candidate) %>%
    unnest(candidate_summary) %>%
    select(office_branch,
           office_id,
           office,
           district,
           district_display,
           district_id,
           election_id,
           election_date,
           is_special,
           total_votes,
           blank_votes,
           all_other_votes,
           num_candidates,
           id_winner,
           name_winner,
           city_town_winner,
           party_winner,
           id_incumbent,
           name_incumbent,
           city_town_incumbent,
           party_incumbent,
           id_dem,
           name_dem,
           city_town_dem,
           votes_dem,
           percent_dem,
           id_gop,
           name_gop,
           city_town_gop,
           votes_gop,
           percent_gop,
           id_third_party,
           name_third_party,
           city_town_third_party,
           votes_third_party,
           percent_third_party,
           party_third_party,
           id_write_in,
           name_write_in,
           city_town_write_in,
           votes_write_in,
           percent_write_in,
           party_write_in)

summary_out_file <- "data/ma_general_election_summaries_1990_2024.csv.gz"
cat(str_glue("Writing summaries to {summary_out_file}...\n\n"))
election_summaries %>%
    write_csv(summary_out_file)

candidate_out_file <- "data/ma_general_election_candidates_1990_2024.csv.gz"
cat(str_glue("Writing candidates to {candidate_out_file}...\n\n"))
elections_candidates %>%
    unnest(candidate) %>%
    write_csv(candidate_out_file)

sqlite_db_file <- "data/ma_elections.sqlite"
if (file.exists(sqlite_db_file)) {
    cat(str_glue("Deleting {sqlite_db_file}...\n\n"))
    file.remove("ma_elections.sqlite")
}
cat(str_glue("Writing {sqlite_db_file}...\n\n"))
elec_db <- dbConnect(RSQLite::SQLite(), "ma_elections.sqlite")
dbWriteTable(elec_db, "general_election", election_summaries)
dbWriteTable(elec_db, "election_candidate", candidates)
dbDisconnect(elec_db)

cat("Done.\n\n")

## election_summaries %>%
##     arrange(desc(election_date)) %>%
##     split(.$office) %>%
##     # Remove complete empty columns
##     map(~ .x %>% select_if(~ any(!is.na(.)))) %>%
##     write_xlsx(path="ma_general_elections_1990_2024.xlsx")
