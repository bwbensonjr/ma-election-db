## Verify that the precinct tables in ma_elections.sqlite can reproduce
## the 2024 district PVI values from
## ../mapoli/pvi/ma_legislative_district_pvi_2024.csv (the gold standard).
##
## This is a one-shot sanity script, not part of the build pipeline.

suppressMessages(library(tidyverse))
library(DBI)

con <- dbConnect(RSQLite::SQLite(), "data/ma_elections.sqlite")

ppv <- dbGetQuery(con, "
    SELECT election_year, city_town, ward, precinct, dem_votes, gop_votes
    FROM precinct_presidential_vote
    WHERE redistricting_year = 2021
      AND election_year IN (2020, 2024)
") %>% as_tibble()

pd <- dbGetQuery(con, "
    SELECT city_town, ward, precinct, state_rep, state_senate,
           us_house, gov_council
    FROM precinct_district
    WHERE redistricting_year = 2021
") %>% as_tibble()

baseline <- dbGetQuery(con, "
    SELECT election_year, dem_votes, gop_votes
    FROM national_presidential_baseline
    WHERE election_year IN (2020, 2024)
") %>% as_tibble()

dbDisconnect(con)

cat("loaded:\n")
cat("  precinct_presidential_vote rows (post-2021, 2020+2024):", nrow(ppv), "\n")
cat("  precinct_district rows (post-2021):", nrow(pd), "\n")
cat("  national_presidential_baseline rows:", nrow(baseline), "\n\n")

## --- Pivot vote rows back to wide for the calc ---
votes_wide <- ppv %>%
    pivot_wider(
        names_from = election_year,
        values_from = c(dem_votes, gop_votes),
        names_glue = "{.value}_{election_year}"
    ) %>%
    mutate(across(starts_with("dem_votes_"), ~replace_na(., 0)),
           across(starts_with("gop_votes_"), ~replace_na(., 0)))

joined <- votes_wide %>%
    left_join(pd, by = c("city_town", "ward", "precinct"))

## --- National baseline (2-cycle Dem%) ---
us_dem <- sum(baseline$dem_votes)
us_gop <- sum(baseline$gop_votes)
us_pvi <- us_dem / (us_dem + us_gop)
cat(sprintf("US 2-cycle Dem%%: %.6f\n", us_pvi))

calc_pvi <- function(df, group_col) {
    df %>%
        group_by(.data[[group_col]]) %>%
        summarize(dem = sum(dem_votes_2024 + dem_votes_2020),
                  gop = sum(gop_votes_2024 + gop_votes_2020),
                  .groups = "drop") %>%
        mutate(local_dem_pct = dem / (dem + gop),
               pvi_n = (local_dem_pct - us_pvi) * 100) %>%
        rename(district_raw = !!group_col)
}

state_rep <- calc_pvi(joined, "state_rep")
state_senate <- calc_pvi(joined, "state_senate")
gov_council <- calc_pvi(joined, "gov_council")
us_house <- calc_pvi(joined, "us_house")

computed <- bind_rows(
    state_rep %>% mutate(office = "State Representative"),
    state_senate %>% mutate(office = "State Senate"),
    gov_council %>% mutate(office = "Governor's Council"),
    us_house %>% mutate(office = "U.S. House")
) %>% select(office, district_raw, computed_pvi_n = pvi_n)

## --- Compare against gold standard ---
gold <- read_csv("../mapoli/pvi/ma_legislative_district_pvi_2024.csv",
                 show_col_types = FALSE) %>%
    select(office, district, district_display, gold_pvi_n = PVI_N)

## Match by district name. The gold CSV uses "and" instead of "&"
## and word ordinals (First, Second). The DB has whatever the source
## CSVs had ("&", word ordinals for state leg, integer for US House
## and Gov Council). Normalize both to "and" + lowercase for comparison.
norm <- function(x) x %>% str_replace_all("&", "and") %>% str_to_lower()

computed_n <- computed %>% mutate(key = norm(district_raw))
gold_n <- gold %>% mutate(key = norm(district))

joined_check <- inner_join(computed_n, gold_n, by = c("office", "key"))
unmatched_computed <- anti_join(computed_n, gold_n, by = c("office", "key"))
unmatched_gold <- anti_join(gold_n, computed_n, by = c("office", "key"))

cat(sprintf("\nmatched %d/%d districts\n",
            nrow(joined_check), nrow(gold_n)))
cat(sprintf("unmatched computed: %d  unmatched gold: %d\n",
            nrow(unmatched_computed), nrow(unmatched_gold)))

if (nrow(unmatched_computed) > 0) {
    cat("\ncomputed-but-not-in-gold:\n")
    print(unmatched_computed %>% select(office, district_raw))
}
if (nrow(unmatched_gold) > 0) {
    cat("\ngold-but-not-in-computed:\n")
    print(unmatched_gold %>% select(office, district))
}

joined_check <- joined_check %>%
    mutate(diff = computed_pvi_n - gold_pvi_n,
           abs_diff = abs(diff))

cat(sprintf("\nmax abs diff:    %.6f\n", max(joined_check$abs_diff)))
cat(sprintf("median abs diff: %.6f\n", median(joined_check$abs_diff)))
cat(sprintf("districts with abs_diff > 0.5: %d\n",
            sum(joined_check$abs_diff > 0.5)))

big <- joined_check %>% filter(abs_diff > 0.5) %>%
    arrange(desc(abs_diff)) %>%
    select(office, district_raw, computed_pvi_n, gold_pvi_n, diff)
if (nrow(big) > 0) {
    cat("\nlargest differences:\n")
    print(big, n = 20)
}
