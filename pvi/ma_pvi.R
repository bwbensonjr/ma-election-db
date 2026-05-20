## Assembles district-level Partisan Voting Index (PVI) data from
## upstream mapoli outputs into a single multi-year CSV under
## `data/pvi/`. Currently mapoli is the source-of-truth for PVI
## computation; this script just reshapes its outputs into the unified
## ma-election-db schema.
##
## Inputs (read from sibling mapoli checkout at ../mapoli):
##   pvi/ma_state_leg_pvi_2008_2024.csv      (State Rep + State Senate, 2008-2024)
##   pvi/ma_legislative_district_pvi_2024.csv (all 4 offices, 2024 only)
##
## Output:
##   data/pvi/ma_district_pvi.csv.gz
##     Columns: pvi_year, office, district, district_display, pvi_n, pvi

library(tidyverse)

mapoli_pvi_dir <- "../mapoli/pvi"
historical_csv <- file.path(mapoli_pvi_dir, "ma_state_leg_pvi_2008_2024.csv")
current_csv <- file.path(mapoli_pvi_dir, "ma_legislative_district_pvi_2024.csv")

for (f in c(historical_csv, current_csv)) {
    if (!file.exists(f)) {
        stop(str_glue(
            "Required mapoli input not found: {f}\n",
            "This script reads PVI outputs from a sibling mapoli checkout. ",
            "Ensure the mapoli repo is checked out at ../mapoli."
        ))
    }
}

cat(str_glue("Reading {historical_csv}...\n\n"))
historical <- read_csv(historical_csv, show_col_types = FALSE) %>%
    rename(pvi_n = PVI_N, pvi = PVI) %>%
    select(pvi_year, office, district, district_display, pvi_n, pvi)

cat(str_glue("Reading {current_csv}...\n\n"))
current_2024_supplement <- read_csv(current_csv, show_col_types = FALSE) %>%
    rename(pvi_n = PVI_N, pvi = PVI) %>%
    filter(office %in% c("Governor's Council", "U.S. House")) %>%
    mutate(pvi_year = 2024L) %>%
    select(pvi_year, office, district, district_display, pvi_n, pvi)

district_pvi <- bind_rows(historical, current_2024_supplement) %>%
    arrange(pvi_year, office, district)

output_dir <- "data/pvi"
if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
}
output_file <- file.path(output_dir, "ma_district_pvi.csv.gz")

cat(str_glue("Writing {output_file} ({nrow(district_pvi)} rows)...\n\n"))
write_csv(district_pvi, output_file)

cat("Done.\n")
