## This script takes the raw election and candidate information
## from the data files and produces election-level and candidate-level
## summaries.

library(tidyverse)
library(lubridate)
library(DBI)

## Load candidate ID mapping to handle duplicate IDs from name variations
## This ensures the same person always has the same canonical ID and name
candidate_id_map_file <- "data/candidate-id-map.csv"
if (file.exists(candidate_id_map_file)) {
    candidate_id_map <- read_csv(candidate_id_map_file,
                                  show_col_types = FALSE) %>%
        select(id_dup, id_canonical, name_canonical)
} else {
    candidate_id_map <- tibble(id_dup = integer(), id_canonical = integer(), name_canonical = character())
}

## Apply candidate ID mapping globally
apply_candidate_id_mapping <- function(df) {
    df %>%
        left_join(candidate_id_map, by = c("candidate_id" = "id_dup")) %>%
        mutate(candidate_id = coalesce(id_canonical, candidate_id),
               name = coalesce(name_canonical, name)) %>%
        select(-id_canonical, -name_canonical)
}

## Fix some issues with the data
candidate_fixes <- function(df) {
    df %>%
        mutate(is_write_in = case_when(
                 ((election_id == 154409) & (candidate_id == 89485)) ~ TRUE,
                 TRUE ~ is_write_in),
             name = case_when(
                 ((election_id == 154409) & (candidate_id == 78007)) ~ "Susannah M. Whipps",
                 ((election_id == 154549) & (candidate_id == 88406)) ~ "Bradley H. Jones, Jr.",
                 TRUE ~ name),
             is_winner = case_when(
                 ((election_id == 96321) & (candidate_id == 71530)) ~ FALSE,
                 TRUE ~ is_winner),
             candidate_id = case_when(
                 ((election_id == 154549) & (candidate_id == 88406)) ~ 62825,
                 TRUE ~ candidate_id),
             num_elections = case_when(
                 (candidate_id == 62825) ~ 33,
                 TRUE ~ num_elections))
}

## Older version of data fixes:
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
##              is_winner = case_when(
##                  ((election_id == 96321) & (candidate_id == 71530)) ~ FALSE,
##                  TRUE ~ is_winner))
## }

## No longer required
## election_fixes <- function(df) {
##     df %>%
##         filter(election_id != 98279) %>%
##         mutate(election_date = case_when(
##                    (election_id %in% c(130117, 130120)) ~ ymd("1996-11-05"),
##                    TRUE ~ election_date))
## }

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

## Treat the Senate seat Class as its district
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

elections_in_file <- "data/ma_elections.csv.gz"
cat(str_glue("Reading elections from {elections_in_file}...\n\n"))

elections <- read_csv(elections_in_file,
                      col_types=list(party_primary = col_logical(),
                                     is_special = col_logical())) %>%
    # Treat missing TRUE/FALSE as FALSE 
    mutate(party_primary = replace_na(party_primary, FALSE),
           is_special = replace_na(is_special, FALSE)) %>%
    add_senate_seat_as_district()

cat(str_glue("Read {nrow(elections)} elections.\n\n"))

## Identify first election cycle for each office to exclude from outputs
## (these elections have no valid incumbency data)
first_cycles <- elections %>%
    group_by(office_id) %>%
    summarize(first_cycle_date = min(election_date), .groups='drop')

elections <- elections %>%
    left_join(first_cycles, by="office_id") %>%
    mutate(is_first_cycle = (election_date == first_cycle_date))

## Show which elections will be excluded
first_cycle_summary <- elections %>%
    filter(is_first_cycle) %>%
    group_by(office) %>%
    summarize(
        first_date = first(election_date),
        num_elections = n(),
        .groups='drop'
    )

cat("Excluding first election cycle per office (no incumbency data):\n")
print(first_cycle_summary)
cat("\n")

party_abbrev <- function(party) {
    case_when(
        party == "Democratic" ~ "D",
        party == "Republican" ~ "R",
        party == "Unenrolled" ~ "U",
        party == "Libertarian" ~ "L",
        party == "Independent" ~ "I",
        party == "Green-Rainbow" ~ "GR",
        party == "Natural Law" ~ "NL",
        TRUE ~ "Other"
    )
}

candidate_display <- function(name, party_abbr, city_town) {
    if_else(is.na(city_town),
            str_glue("{name} ({party_abbr})"),
            str_glue("{name} ({party_abbr}-{city_town})"))
}

candidates_in_file <- "data/ma_candidates.csv.gz"
cat(str_glue("Reading candidates from {candidates_in_file}...\n\n"))

candidates <- read_csv(candidates_in_file,
                       col_types=list(is_winner = col_logical(),
                                      is_write_in = col_logical())) %>%
    apply_candidate_id_mapping() %>%
    candidate_fixes() %>%
    mutate(party = replace_na(party, "None"),
           party_abbr = party_abbrev(party),
           city_town = str_replace(city_state, ", MA", ""),
           display = candidate_display(name, party_abbr, city_town),
           is_winner = replace_na(is_winner, FALSE),
           is_write_in = replace_na(is_write_in, FALSE),
           ## Simplify party information into three-valued "dem", "gop"
           ## and, "third_party" as `party_role` for use in column naming
           party_role = case_when(
               is_write_in ~ "write_in",
               (party == "Democratic") ~ "dem",
               (party == "Republican") ~ "gop",
               TRUE ~ "third_party"))

cat(str_glue("Read {nrow(candidates)} candidates.\n\n"))


## Determine incumbency by checking if a candidate won the most recent
## previous election (regular or special) for that office/district.
## This handles special elections, career gaps, and redistricting.
##
## First, create a table of distinct election cycles per office using only
## regular elections. This is used for first-cycle filtering, not incumbency.
## For U.S. Senate, we need to group by district_id (Class) as well.
distinct_cycles <- elections %>%
    filter(!is_special) %>%  ## Only regular elections define cycles
    group_by(office_id, district_id, election_date) %>%
    slice(1) %>%  ## One row per office-district-date combination
    ungroup() %>%
    group_by(office_id, district_id) %>%  ## Group by office AND district (for Senate Class)
    arrange(election_date) %>%
    mutate(prev_cycle_date = lag(election_date)) %>%
    ungroup() %>%
    select(office_id, district_id, election_date, prev_cycle_date)

election_cycles <- elections %>%
    left_join(distinct_cycles, by=c("office_id", "district_id", "election_date")) %>%
    select(election_id, office_id, district_id, election_date, prev_cycle_date)

## Create a table of all election dates per office/district to find previous elections
## This includes BOTH regular and special elections
all_election_dates <- elections %>%
    group_by(office_id, district_id) %>%
    arrange(election_date) %>%
    mutate(prev_election_date = lag(election_date)) %>%
    ungroup() %>%
    select(election_id, office_id, district_id, election_date, prev_election_date)

## Create a table of who won what in each election (regular or special)
all_winners <- elections %>%
    left_join(candidates %>% filter(is_winner), by="election_id") %>%
    select(office_id, election_date, district_id, candidate_id, name) %>%
    filter(!is.na(candidate_id))

## Determine incumbency by checking if candidate won the most recent previous election
## We need to handle cases where a candidate may have won multiple times
## in the same election (shouldn't happen but be safe), so deduplicate by taking
## the first district they won
candidate_is_incumbent <- elections %>%
    left_join(candidates, by="election_id") %>%
    left_join(all_election_dates, by=c("election_id", "office_id", "district_id", "election_date")) %>%
    left_join(
        all_winners %>%
            group_by(office_id, candidate_id, election_date) %>%
            slice(1) %>%  ## Take first district if multiple wins in same election
            ungroup() %>%
            mutate(won_prev_election = TRUE),  ## Add marker for successful join
        by=c("office_id", "candidate_id", "prev_election_date" = "election_date"),
        suffix=c("", "_prev")
    ) %>%
    mutate(is_incumbent = !is.na(won_prev_election)) %>%  ## Check if join matched
    select(election_id, candidate_id, is_incumbent, district_id_prev)

## Join the incumbency information back into the candidate list
## The new algorithm handles all previous edge cases automatically
##
candidates_w_inc <- candidates %>%
    left_join(candidate_is_incumbent,
              by=c("election_id", "candidate_id")) %>%
    mutate(is_incumbent = replace_na(is_incumbent, FALSE))

## Add the candidates to the elections as a nested dataframe.
##
elections_candidates <- elections %>%
    nest_join(candidates_w_inc,
              by="election_id",
              name="candidate")

## Count incumbents per election for tracking multiple incumbents
## (which can happen legitimately due to redistricting)
##
num_incumbents <- function(cands) {
    incumbents <- cands %>%
        filter(is_incumbent)
    nrow(incumbents)
}

elections_candidates <- elections_candidates %>%
    mutate(num_incumbents = map_int(candidate, num_incumbents))

## This is the primary working function of the script. It identifies
## (if present) the Democrat, Republican, third-party candidate with
## most votes, and write-in candidate with most votes, provides
## flattened information in the election row with the "dem_", "gop_",
## "third_party_", and "write_in_" prefixes. The information
## provided is `name`, `votes`, `percent`, `party`, `city_town`,
## and `id`.
##
## For incumbents, when multiple exist (due to redistricting), we prefer
## the incumbent who served in the same district, falling back to the
## most recent winner.
##
extract_summaries <- function(cands, current_district) {
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
    winner <- filter(cands, is_winner) %>%
        mutate(party_role = "winner", percent = 0)

    ## Handle multiple incumbents by preferring same-district incumbent
    incumbent <- cands %>%
        filter(is_incumbent) %>%
        arrange(
            ## Prefer incumbent from same district
            district_id_prev != current_district,
            ## Then prefer non-NA district_id_prev
            is.na(district_id_prev)
        ) %>%
        slice(1) %>%
        mutate(party_role = "incumbent", percent = 0)

    rbind((rbind(dem, gop, third_party, write_in) %>%
           mutate(percent = num_votes/sum(num_votes))),
          winner,
          incumbent) %>%
        select(party_role,
               party,
               name,
               display,
               votes=num_votes,
               percent,
               city_town,
               id=candidate_id) %>%
        pivot_wider(names_from=party_role,
                    values_from=c(name, display, votes, percent,
                                  party, city_town, id)) %>%
        ## Leave out some obvious information
        select(-any_of(c("party_dem",
                         "party_gop",
                         "votes_incumbent",
                         "percent_incumbent")))
}

cat("Generating summaries (this may take a few minutes)...\n\n")


## Only count non-write-in candidates that were on the ballot
##
num_candidates_on_ballot <-function(cands) {
    nrow(cands %>% filter(!is_write_in))
}

## Create the flatted `candidate_summary` using the `extract_summaries`. This
## takes a couple of minutes.
##
election_summaries <- elections_candidates %>%
    filter(!is_first_cycle) %>%
    mutate(num_candidates = map_int(candidate, num_candidates_on_ballot),
           candidate_summary = map2(candidate, district_id, extract_summaries)) %>%
    ## Try adding a debugging check if the the `candidate_summary`
    ## has more than one row, which would mean some faulty logic or data.
    select(-candidate) %>%
    unnest(candidate_summary) %>%
    mutate(percent_winner = votes_winner/(total_votes - (blank_votes + all_other_votes))) %>%
    ## It is a bit brittle to list all of the columns in this
    ## selection, but it is to get the desired ordering. There could
    ## be a debugging check to ensure that there are no additional columns.
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
           num_incumbents,
           id_winner,
           name_winner,
           display_winner,
           city_town_winner,
           votes_winner,
           percent_winner,
           party_winner,
           id_incumbent,
           name_incumbent,
           display_incumbent,
           city_town_incumbent,
           party_incumbent,
           id_dem,
           name_dem,
           display_dem,
           city_town_dem,
           votes_dem,
           percent_dem,
           id_gop,
           name_gop,
           display_gop,
           city_town_gop,
           votes_gop,
           percent_gop,
           id_third_party,
           name_third_party,
           display_third_party,
           city_town_third_party,
           votes_third_party,
           percent_third_party,
           party_third_party,
           id_write_in,
           name_write_in,
           display_write_in,
           city_town_write_in,
           votes_write_in,
           percent_write_in,
           party_write_in)

summary_out_file <- "data/ma_general_election_summaries.csv.gz"
cat(str_glue("Writing summaries to {summary_out_file}...\n\n"))
election_summaries %>%
    write_csv(summary_out_file)

candidate_out_file <- "data/ma_general_election_candidates.csv.gz"
cat(str_glue("Writing candidates to {candidate_out_file}...\n\n"))
elections_candidates %>%
    filter(!is_first_cycle) %>%
    unnest(candidate) %>%
    write_csv(candidate_out_file)

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
dbWriteTable(
    elec_db,
    "general_election",
    (election_summaries %>%
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
dbWriteTable(
    elec_db,
    "election_candidate",
    (elections_candidates %>%
     filter(!is_first_cycle) %>%
     unnest(candidate) %>%
     select(-is_first_cycle, -num_incumbents)),
    field.types = c(
        election_id = "INTEGER",
        candidate_id = "INTEGER",
        num_elections = "INTEGER",
        num_votes = "INTEGER"
    )
)
dbDisconnect(elec_db)

cat("Done.\n\n")

## I forget what this was for, so leaving it
## here until I show it isn't useful.
##
## election_summaries %>%
##     arrange(desc(election_date)) %>%
##     split(.$office) %>%
##     # Remove complete empty columns
##     map(~ .x %>% select_if(~ any(!is.na(.)))) %>%
##     write_xlsx(path="ma_general_elections_1990_2024.xlsx")
