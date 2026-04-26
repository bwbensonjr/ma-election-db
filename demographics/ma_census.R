library(tidyverse)
library(tidycensus)
library(sf)
library(tigris)
library(glue)
library(here)

options(tigris_use_cache = TRUE)

if (Sys.getenv("CENSUS_API_KEY") == "") {
    stop("CENSUS_API_KEY environment variable is not set. See demographics/README.md for setup.")
}

## ACS 5-year endpoint year (e.g., 2024 = 2020-2024 ACS)
census_year <- 2024
acs_year <- census_year

## Read the table of variables we want to capture or use
message("Reading census variables to collect...")
census_vars <- read_csv(here("demographics", "census_vars.csv"))

## The set of variables that are only used for calculations but
## aren't kept around after use.
temp_var_names <- census_vars %>%
    filter(!keep) %>%
    pull(var_name)

census_query <- function(geography, vars, state=NULL) {
    get_acs(geography=geography,
            variables=vars$variable,
            year=acs_year,
            state=state) %>%
        left_join(vars, by="variable") %>%
        pivot_wider(id_cols=c("GEOID", "NAME"),
                    names_from="var_name",
                    values_from="estimate")
}

add_calculated_factors <- function(df) {
    df %>%
        mutate(ed_college_degree = (ed_bachelors +
                                    ed_masters +
                                    ed_professional +
                                    ed_doctorate),
               ed_some_college = (ed_college_lt_1 +
                                  ed_college_gt_1 +
                                  ed_associates +
                                  ed_college_degree),
               race_minority = (race_black +
                                race_native_american +
                                race_asian +
                                race_hawaiian +
                                race_other +
                                race_multiracial +
                                race_hispanic),
               vote_male_eligible = (vote_male_native_18_plus +
                                     vote_male_naturalized_18_plus),
               vote_female_eligible = (vote_female_native_18_plus +
                                       vote_female_naturalized_18_plus),
               vote_eligible = (vote_male_eligible +
                                vote_female_eligible))
}

add_percentage_factors <- function(df) {
    df %>%
        mutate(gender_female_pct = gender_female / total_population,
               below_poverty_pct = below_poverty_level / poverty_total,
               ed_college_degree_pct = ed_college_degree / total_population,
               ed_some_college_pct = ed_some_college / total_population,
               race_minority_pct = race_minority / total_population,
               race_white_pct = race_white / total_population,
               race_black_pct = race_black / total_population,
               race_asian_pct = race_asian / total_population,
               race_hispanic_pct = race_hispanic / total_population,
               race_native_pct = race_native_american / total_population,
               poverty_pct = below_poverty_level / poverty_total,
               vote_female_pct = vote_female_eligible / vote_eligible,
               wwc_pct = (white_nh_male_lt_high_school +
                          white_nh_male_high_school_grad +
                          white_nh_male_some_college +
                          white_nh_female_lt_high_school +
                          white_nh_female_high_school_grad +
                          white_nh_female_some_college) / total_population,
               white_college_pct = ((white_nh_male_bachelors_or_gt +
                                     white_nh_female_bachelors_or_gt) /
                                    total_population),
               ancestry_french_candadian_pct = ancestry_french_canadian/total_population,
               ancestry_portuguese_pct = ancestry_portuguese/total_population)
}

city_town_name <- function(comp_name) {
    first_part <- str_split_fixed(comp_name, ", ", 3)[,1]
    str_replace_all(first_part, c(" Town city" = "",
                                  " town" = "",
                                  " city" = ""))
}

city_town_county <- function(comp_name) {
    first_part <- str_split_fixed(comp_name, ", ", 3)[,2]
    str_replace(first_part, " County", "")
}

## Urbanicity
##
## We classify each census tract as "very low density",
## "low density", "medium density", or "high density".
##
## When we look at larger geographies we will compute
## the percentage of tracts of each type within the parent
## geometry.
ma_tract_hh <- get_acs(geography="tract",
                       variables=c("NAME", "DP02_0001E"),
                       year=acs_year,
                       state=25) %>%
    rename(total_households = estimate) %>%
    select(-c(variable, moe))

ma_tract_geom <- tracts(25, class="sf") |>
    st_transform(6491) |>
    mutate(area = ((ALAND + AWATER)/2.59e+6)) |>
    select(GEOID, area, ALAND, AWATER)

ma_tract_density <- ma_tract_geom |>
    left_join(ma_tract_hh, by="GEOID") %>%
    mutate(hh_per_sq_mi = as.double(total_households / area),
           density_type = case_when(hh_per_sq_mi < 102 ~ "very low density",
                                    hh_per_sq_mi < 800 ~ "low density",
                                    hh_per_sq_mi < 2123 ~ "medium density",
                                    TRUE ~ "high density"))

density_order <- c("very low", "low", "medium", "high")

district_density <- function(dist_geom) {
    ma_tract_density |>
        st_join(
            dist_geom |> select(district) |> st_transform(6491)
        ) |>
        filter(!is.na(district)) |>
        group_by(district) |>
        summarize(
            very_low_density_pct = sum(density_type == "very low density")/n(),
            low_density_pct = sum(density_type == "low density")/n(),
            medium_density_pct = sum(density_type == "medium density")/n(),
            high_density_pct = sum(density_type == "high density")/n()
        ) |>
        st_drop_geometry() |>
        rowwise() |>
        mutate(
            density_type = {
                v <- c(
                    `very low` = very_low_density_pct,
                    low      = low_density_pct,
                    medium   = medium_density_pct,
                    high     = high_density_pct
                )
                ord <- order(v, decreasing = TRUE)
                n1 <- names(v)[ord[1]]
                n2 <- names(v)[ord[2]]

                if (v[n1] > 0.5) {
                    n1
                } else if (v[n1] + v[n2] > 0.5) {
                    top2 <- c(n1, n2)
                    top2_sorted <- top2[order(match(top2, density_order))]
                    paste(top2_sorted, collapse = "/")
                } else {
                    "mixed"
                }
            }
        ) |>
        ungroup()
}

city_town_vars <- census_query("county subdivision",
                               census_vars,
                               state=25) |>
    filter(!str_detect(NAME, "not defined")) |>
    mutate(city_town = city_town_name(NAME),
           county = city_town_county(NAME)) |>
    rename(city_town_fips = GEOID) |>
    select(-NAME) |>
    add_calculated_factors() |>
    add_percentage_factors() |>
    select(-all_of(temp_var_names)) |>
    mutate(census_year = census_year) |>
    relocate(census_year, city_town_fips, city_town, county)

city_town_file <- here("data", "demographics", "ma_city_town_demographics.csv.gz")
message(str_glue("Writing City/Town variables to file {city_town_file}..."))
city_town_vars |>
    write_csv(city_town_file)

## The new MA State Rep and State Senate districts
## are different from the ones known by the census so
## the variable values need to be interpolated.
##
## It looks like we need to do the interpolation
## in three different cases:
## - block groups, extensive=TRUE (counts of things)
## - block groups, extensive=FALSE (e.g., central/median values)
## - tracts, extensive=TRUE
## - tracts, extensive=FALSE (we don't have this case)
##
block_group_count_vars <- census_vars %>%
    filter(geography == "block group", count)
block_group_median_vars <- census_vars %>%
    filter(geography == "block group", !count)
tract_count_vars <- census_vars %>%
    filter(geography == "tract")

message("Reading block geometry...")
block_geom <- blocks(state=25, year=acs_year) %>%
    st_transform(6491)

message("Reading block group geometry...")
block_group_geom <- block_groups(state=25,
                                 cb=TRUE,
                                 year=acs_year) %>%
    st_transform(6491) %>%
    select(GEOID)

message("Reading tract geometry...")
tract_geom <- tracts(state=25,
                     cb=TRUE,
                     year=acs_year) %>%
    st_transform(6491) %>%
    select(GEOID)

message("Reading block group counts and medians...")
block_group_counts <- block_group_geom %>%
    left_join(census_query("block group",
                           block_group_count_vars,
                           state=25),
              by="GEOID")

block_group_medians <- block_group_geom %>%
    left_join(census_query("block group",
                           block_group_median_vars,
                           state=25),
              by="GEOID")

message("Reading tract counts...")
tracts <- tract_geom %>%
    left_join(census_query("tract",
                           tract_count_vars,
                           state=25),
              by="GEOID")

add_geometry_area <- function(target_vars, target_geom, target_id) {
    target_vars |>
        left_join((target_geom |>
                   st_drop_geometry() |>
                   select(all_of(target_id), shape_area)),
                  by=target_id) |>
        rename(area_m2 = shape_area)
}

interpolate_geom <- function(target_geom, target_id, target_crs) {
    target_block_group_counts <- interpolate_pw(block_group_counts,
                                                target_geom,
                                                weights=block_geom,
                                                to_id=target_id,
                                                extensive=TRUE,
                                                crs=target_crs) %>%
        as_tibble() %>%
        select(-geometry)
    target_block_group_medians <- interpolate_pw(block_group_medians,
                                                 target_geom,
                                                 weights=block_geom,
                                                 to_id=target_id,
                                                 extensive=FALSE,
                                                 crs=target_crs) %>%
        as_tibble() %>%
        select(-geometry)
    target_tract_counts <- interpolate_pw(tracts,
                                          target_geom,
                                          weights=block_geom,
                                          to_id=target_id,
                                          extensive=TRUE,
                                          crs=target_crs) %>%
        as_tibble() %>%
        select(-geometry)
    target_block_group_counts %>%
        left_join(target_block_group_medians, by=target_id) %>%
        left_join(target_tract_counts, by=target_id) %>%
        add_calculated_factors() %>%
        add_percentage_factors() %>%
        select(-all_of(temp_var_names)) %>%
        add_geometry_area(target_geom, target_id)
}

## Returns a tibble of district-level demographics with office and
## census_year columns prepended. Called once per office; results are
## bind_rows'd to produce a single consolidated CSV.
district_demographics_for_office <- function(office, geom_file) {
    message(str_glue("Interpolating {office} values..."))
    dist_geom <- read_sf(geom_file)
    dist_density <- district_density(dist_geom)
    interpolate_geom(dist_geom, "district", 6491) |>
        left_join(dist_density, by="district") |>
        mutate(office = office, census_year = census_year) |>
        relocate(census_year, office, district)
}

district_demographics <- bind_rows(
    district_demographics_for_office(
        "State Representative",
        here("data", "geometry", "2021", "house2021.geojson")
    ),
    district_demographics_for_office(
        "State Senate",
        here("data", "geometry", "2021", "senate2021.geojson")
    ),
    district_demographics_for_office(
        "Governor's Council",
        here("data", "geometry", "2021", "govcouncil2021.geojson")
    ),
    district_demographics_for_office(
        "U.S. House",
        here("data", "geometry", "2021", "congressma118.geojson")
    )
)

district_file <- here("data", "demographics", "ma_district_demographics.csv.gz")
message(str_glue("Writing district-level variables to file {district_file}..."))
district_demographics |> write_csv(district_file)

message("Interpolating precinct-level values...")
precinct_geom <-
    read_sf(here("data", "geometry", "2021", "wards_pcts_subs_2022.geojson")) |>
    rename(
        precinct_name = name,
        ward = Ward,
        precinct = Pct
    ) |>
    mutate(shape_area = st_area(geometry))
precinct_ids <- precinct_geom |>
    as_tibble() |>
    select(precinct_name, city_town, ward, precinct)
precinct_vars <- interpolate_geom(precinct_geom, "precinct_name", 6491) |>
    left_join(precinct_ids, by="precinct_name") |>
    relocate(name=precinct_name, city_town, ward, precinct) |>
    mutate(census_year = census_year) |>
    relocate(census_year, name, city_town, ward, precinct)

precinct_file <- here("data", "demographics", "ma_precinct_demographics.csv.gz")
message(glue("Writing precinct-level variables to file {precinct_file}..."))
precinct_vars |> write_csv(precinct_file)

message("Done.")
