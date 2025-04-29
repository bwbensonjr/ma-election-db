from fuzzywuzzy import fuzz
import pandas as pd

def main():
    cand_elecs = (pd.read_csv("data/ma_general_election_candidates_1990_2025.csv.gz")
                  .sort_values(["candidate_id", "election_id"], ascending=False))
    cands = cand_elecs.drop_duplicates("candidate_id")
    cand_spelling_dups = potential_duplicates(cands)
    special_dups = special_cases(cands)
    dups = (pd.concat([cand_spelling_dups, special_dups], ignore_index=True)
            .sort_values("same_person", ascending=False))
    dups.to_csv("data/possible-candidate-dupes.csv", index=False)
    rep_dups = (dups.query("same_person == 'yes'")
                .drop(["same_person", "ratio"], axis=1)
                .pipe(transform_for_report)
                .drop_duplicates("id_dup")
                .sort_values("id_pref"))
    rep_dups.to_csv("data/reported-duplicates.csv", index=False)
        
def special_cases(df):
    keating_rows = df[df["name"].str.contains("Keating")].sort_values("candidate_id")
    pref_id = keating_rows.iloc[2]["candidate_id"]
    keating_1 = combined_row_info(keating_rows.iloc[0], keating_rows.iloc[2])
    keating_2 = combined_row_info(keating_rows.iloc[1], keating_rows.iloc[2])
    keating_df = (pd.DataFrame([keating_1, keating_2])
                  .assign(same_person = "yes",
                          pref_id = pref_id,
                          ratio = 100))
    return keating_df

def combined_row_info(row_1, row_2):
    comb_row = {
        "id_1": row_1["candidate_id"],
        "id_2": row_2["candidate_id"],
        "name_1": row_1["name"],
        "name_2": row_2["name"],
        "office_1": row_1["office"],
        "district_1": row_1["district"],
        "city_town_1": row_1["city_town"],
        "office_2": row_2["office"],
        "district_2": row_2["district"],
        "city_town_2": row_2["city_town"],
    }
    return comb_row
    
def potential_duplicates(df):
    pot_dups = []
    for i, row_1 in df.iterrows():
        for j, row_2 in df.iloc[i+1:].iterrows():  # only compare with candidates we haven"t compared yet
            if row_1["candidate_id"] == row_2["candidate_id"]:
                continue
            # Use multiple comparison methods to minimize false negatives
            ratio = fuzz.ratio(row_1["name"], row_2["name"])
            token_sort = fuzz.token_sort_ratio(row_1["name"], row_2["name"])
            token_set = fuzz.token_set_ratio(row_1["name"], row_2["name"])
            # Use a relaxed threshold to minimize false negatives (adjust as needed)
            # Consider a match if ANY of the metrics exceeds threshold
            #if ratio > 75 or token_sort > 75 or token_set > 80:
            if ratio > 90:
                comb_row = combined_row_info(row_1, row_2)
                comb_row["ratio"] = ratio
                pot_dups.append(comb_row)
    df_dups = pd.DataFrame(pot_dups)
    return df_dups
    
def transform_for_report(df):
    # Initialize the new DataFrame with the same index
    result_data = []
    for _, row in df.iterrows():
        new_row = {}
        if row['pref_id'] == row['id_1']:
            pref_suffix = '1'
            dup_suffix = '2'
        else:
            pref_suffix = '2'
            dup_suffix = '1'
        # Map columns from old to new names
        new_row['id_pref'] = row[f'id_{pref_suffix}']
        new_row['name_pref'] = row[f'name_{pref_suffix}']
        new_row['office_pref'] = row[f'office_{pref_suffix}']
        new_row['district_pref'] = row[f'district_{pref_suffix}']
        new_row['city_town_pref'] = row[f'city_town_{pref_suffix}']
        new_row['id_dup'] = row[f'id_{dup_suffix}']
        new_row['name_dup'] = row[f'name_{dup_suffix}']
        new_row['office_dup'] = row[f'office_{dup_suffix}']
        new_row['district_dup'] = row[f'district_{dup_suffix}']
        new_row['city_town_dup'] = row[f'city_town_{dup_suffix}']
        result_data.append(new_row)
    result_df = pd.DataFrame(result_data)
    return result_df
