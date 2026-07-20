## First Suffolk Senate district demographic time series.
##
## Pulls ACS 5-year data for the Massachusetts State Senate (upper chamber)
## district named "First Suffolk", directly from the Census SLDU geography for
## each vintage. Because the Census updates SLDU boundaries to match the current
## legislative plan, each year's row reflects the district *as it existed* in
## that era -- no interpolation. The boundary vintage is recorded in the
## `boundary_tag` column (parsed from the Census NAME), and the redistricting
## cycle is labeled in `redistricting_cycle`.
##
## Variables: race/ethnicity (B03002, Hispanic origin by race) and median
## household income (B19013), both available across the full ACS 5-year range.
library(tidyverse)
library(tidycensus)

if (Sys.getenv("CENSUS_API_KEY") == "") {
    stop("CENSUS_API_KEY not set. See demographics/README.md.")
}

## ACS 5-year endpoint years to pull. 2009 (2005-2009) is the earliest the
## ACS 5-year series exists; 2024 (2020-2024) is the latest.
acs_years <- 2009:2024

## B03002 = Hispanic or Latino Origin by Race. Components are mutually
## exclusive and sum to the total population (B03002_001).
race_vars <- c(
    total_pop      = "B03002_001",
    white          = "B03002_003",  # White alone, non-Hispanic
    black          = "B03002_004",  # Black alone, non-Hispanic
    native         = "B03002_005",  # American Indian/Alaska Native, NH
    asian          = "B03002_006",  # Asian alone, non-Hispanic
    hawaiian       = "B03002_007",  # Native Hawaiian/Pacific Islander, NH
    other_race     = "B03002_008",  # Some other race alone, non-Hispanic
    multiracial    = "B03002_009",  # Two or more races, non-Hispanic
    hispanic       = "B03002_012",  # Hispanic or Latino (any race)
    med_hh_income  = "B19013_001"
)

fetch_year <- function(year) {
    message("Fetching ACS 5-year ", year, " ...")
    raw <- tryCatch(
        get_acs(
            geography = "state legislative district (upper chamber)",
            variables = race_vars,
            year      = year,
            state     = "MA",
            output    = "wide"
        ),
        error = function(e) {
            message("  ERROR for ", year, ": ", conditionMessage(e))
            NULL
        }
    )
    if (is.null(raw)) return(NULL)

    fs <- raw %>%
        filter(str_detect(NAME, "First Suffolk District"))

    if (nrow(fs) != 1) {
        message("  WARNING: ", nrow(fs), " First Suffolk matches for ", year,
                " -- skipping.")
        return(NULL)
    }

    fs %>%
        transmute(
            acs_endpoint_year = year,
            acs_window        = str_glue("{year - 4}-{year}"),
            geoid             = GEOID,
            census_name       = NAME,
            # Boundary vintage tag the Census stamps in the NAME, e.g. (2016).
            boundary_tag      = as.integer(str_extract(NAME, "(?<=\\()\\d{4}(?=\\))")),
            total_population  = total_popE,
            median_hh_income  = med_hh_incomeE,
            median_hh_income_moe = med_hh_incomeM,
            white_pct       = 100 * whiteE       / total_popE,
            black_pct       = 100 * blackE       / total_popE,
            hispanic_pct    = 100 * hispanicE    / total_popE,
            asian_pct       = 100 * asianE       / total_popE,
            multiracial_pct = 100 * multiracialE / total_popE,
            # Native American, Hawaiian/PI, and "some other race" are each tiny
            # district-wide; combine into a single "other" share.
            other_pct       = 100 * (nativeE + hawaiianE + other_raceE) / total_popE
        )
}

ts <- map(acs_years, fetch_year) %>%
    compact() %>%
    bind_rows() %>%
    arrange(acs_endpoint_year) %>%
    mutate(
        redistricting_cycle = case_when(
            boundary_tag <= 2011 ~ "2001 plan (elections 2002-2010)",
            boundary_tag <= 2021 ~ "2011 plan (elections 2012-2020)",
            TRUE                 ~ "2021 plan (elections 2022-)"
        )
    ) %>%
    relocate(redistricting_cycle, .after = boundary_tag)

out_file <- "/Users/bwb/src/github.com/massnumbers/blog/posts/2026-06-08-first-suffolk/first_suffolk_demographics_timeseries.csv"
write_csv(ts, out_file)
message("Wrote ", out_file)

## Print a readable summary.
ts %>%
    select(acs_window, boundary_tag, redistricting_cycle, total_population,
           median_hh_income, white_pct, black_pct, hispanic_pct, asian_pct,
           multiracial_pct) %>%
    mutate(across(ends_with("_pct"), ~round(., 1))) %>%
    print(n = 100, width = Inf)
