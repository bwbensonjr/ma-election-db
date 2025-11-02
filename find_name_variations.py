"""
Comprehensive candidate duplicate detection using multiple strategies.

Finds candidates who are likely the same person with different IDs due to:
1. Name variations (middle name expanded/abbreviated)
2. Consecutive election winners with same name but different IDs
3. Multiple appearances in same district with similar names
"""

import pandas as pd
import sqlite3
import re

def normalize_name(name):
    """Normalize name for comparison by removing punctuation and extra spaces."""
    if pd.isna(name):
        return ""
    # Remove punctuation except spaces
    name = re.sub(r'[^\w\s]', '', name)
    # Collapse multiple spaces
    name = re.sub(r'\s+', ' ', name)
    return name.strip().lower()

def extract_initials(name):
    """Extract all initials from a name."""
    if pd.isna(name):
        return set()
    words = name.split()
    return {w[0].upper() for w in words if w}

def names_match_with_abbreviation(name1, name2):
    """Check if names match allowing for middle name abbreviations."""
    if pd.isna(name1) or pd.isna(name2):
        return False

    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)

    # Exact match after normalization
    if norm1 == norm2:
        return True

    # Check if one is a substring (for "Jo Comerford" vs "Joanne M. Comerford")
    words1 = set(norm1.split())
    words2 = set(norm2.split())

    # If one name is entirely contained in the other
    if words1.issubset(words2) or words2.issubset(words1):
        return True

    # Check for middle name expansion/abbreviation
    # "Daniel J. Ryan" vs "Daniel Joseph Ryan"
    initials1 = extract_initials(name1)
    initials2 = extract_initials(name2)

    # If both have same first and last word but different middle parts
    parts1 = name1.split()
    parts2 = name2.split()

    if len(parts1) >= 2 and len(parts2) >= 2:
        # First names match
        if normalize_name(parts1[0]) == normalize_name(parts2[0]):
            # Last names match
            if normalize_name(parts1[-1]) == normalize_name(parts2[-1]):
                # Check if middle parts are related
                if len(parts1) != len(parts2):
                    # One might have abbreviated middle name
                    return True
                else:
                    # Check if all initials match
                    mid_initials1 = {p[0].upper() for p in parts1[1:-1] if p}
                    mid_initials2 = {p[0].upper() for p in parts2[1:-1] if p}
                    if mid_initials1 == mid_initials2:
                        return True

    return False

def find_consecutive_winner_duplicates(db_path):
    """Find winners of consecutive elections with different IDs but similar names."""
    conn = sqlite3.connect(db_path)

    query = """
    WITH consecutive_winners AS (
      SELECT
        e1.district_id,
        e1.office,
        e1.election_date as election_1,
        e2.election_date as election_2,
        c1.candidate_id as id_1,
        c1.name as name_1,
        c1.last_name as last_name_1,
        c1.city_town as city_1,
        c2.candidate_id as id_2,
        c2.name as name_2,
        c2.last_name as last_name_2,
        c2.city_town as city_2,
        c2.is_incumbent
      FROM general_election e1
      JOIN election_candidate c1 ON e1.election_id = c1.election_id AND c1.is_winner = 1
      JOIN general_election e2 ON e1.district_id = e2.district_id
        AND e1.office_id = e2.office_id
        AND e2.election_date > e1.election_date
      JOIN election_candidate c2 ON e2.election_id = c2.election_id AND c2.is_winner = 1
      WHERE NOT EXISTS (
        SELECT 1 FROM general_election e3
        WHERE e3.district_id = e1.district_id
          AND e3.office_id = e1.office_id
          AND e3.election_date > e1.election_date
          AND e3.election_date < e2.election_date
      )
    )
    SELECT * FROM consecutive_winners
    WHERE id_1 != id_2
      AND last_name_1 = last_name_2
      AND (city_1 = city_2 OR city_1 IS NULL OR city_2 IS NULL)
      AND is_incumbent = 0
      AND election_2 >= '2016-01-01'
    ORDER BY election_2 DESC
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    # Filter to likely matches using name matching
    df['names_match'] = df.apply(
        lambda row: names_match_with_abbreviation(row['name_1'], row['name_2']),
        axis=1
    )

    return df[df['names_match']].copy()

def find_same_district_duplicates(db_path):
    """Find candidates appearing in same district with similar names."""
    conn = sqlite3.connect(db_path)

    query = """
    SELECT
      c1.candidate_id as id_1,
      c1.name as name_1,
      c1.first_name as first_1,
      c1.last_name as last_1,
      c2.candidate_id as id_2,
      c2.name as name_2,
      c2.first_name as first_2,
      c2.last_name as last_2,
      c1.office,
      c1.district,
      c1.city_town as city_1,
      c2.city_town as city_2,
      COUNT(DISTINCT c1.election_id) as elections_1,
      COUNT(DISTINCT c2.election_id) as elections_2
    FROM election_candidate c1
    JOIN election_candidate c2
      ON c1.district_id = c2.district_id
      AND c1.office_id = c2.office_id
      AND c1.last_name = c2.last_name
      AND c1.candidate_id < c2.candidate_id
      AND (c1.city_town = c2.city_town OR c1.city_town IS NULL OR c2.city_town IS NULL)
    WHERE c1.last_name != ''
      AND c1.first_name = c2.first_name
    GROUP BY c1.candidate_id, c2.candidate_id
    HAVING COUNT(DISTINCT c1.election_id) > 0 AND COUNT(DISTINCT c2.election_id) > 0
    ORDER BY elections_1 + elections_2 DESC
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    # Filter to likely matches
    df['names_match'] = df.apply(
        lambda row: names_match_with_abbreviation(row['name_1'], row['name_2']),
        axis=1
    )

    return df[df['names_match']].copy()

def combine_results(consecutive_df, same_district_df):
    """Combine and deduplicate results from different detection methods."""

    # From consecutive winners
    consecutive_results = consecutive_df[['id_1', 'name_1', 'id_2', 'name_2', 'office', 'district_id']].copy()
    consecutive_results['detection_method'] = 'consecutive_winner'
    consecutive_results['confidence'] = 'high'

    # From same district
    same_district_results = same_district_df[['id_1', 'name_1', 'id_2', 'name_2', 'office', 'district']].copy()
    same_district_results.rename(columns={'district': 'district_id'}, inplace=True)
    same_district_results['detection_method'] = 'same_district'
    same_district_results['confidence'] = 'medium'

    # Combine
    all_results = pd.concat([consecutive_results, same_district_results], ignore_index=True)

    # Deduplicate by ID pair
    all_results['id_pair'] = all_results.apply(
        lambda row: tuple(sorted([row['id_1'], row['id_2']])),
        axis=1
    )

    # Keep highest confidence for each pair
    confidence_order = {'high': 2, 'medium': 1}
    all_results['confidence_score'] = all_results['confidence'].map(confidence_order)
    all_results = all_results.sort_values('confidence_score', ascending=False)
    all_results = all_results.drop_duplicates(subset='id_pair', keep='first')

    return all_results.drop(columns=['id_pair', 'confidence_score']).sort_values(['confidence', 'id_2'], ascending=[False, False])

def main():
    db_path = "data/ma_elections.sqlite"

    print("Finding consecutive winner duplicates...")
    consecutive_df = find_consecutive_winner_duplicates(db_path)
    print(f"Found {len(consecutive_df)} consecutive winner duplicates\n")

    print("Finding same district duplicates...")
    same_district_df = find_same_district_duplicates(db_path)
    print(f"Found {len(same_district_df)} same district duplicates\n")

    print("Combining results...")
    results = combine_results(consecutive_df, same_district_df)

    print(f"\nTotal unique candidate ID pairs found: {len(results)}\n")

    # Format for candidate-id-map.csv
    output = results[['id_2', 'id_1', 'name_1']].copy()
    output.columns = ['id_dup', 'id_canonical', 'name_canonical']
    output['note'] = results['detection_method'] + ' - ' + results['confidence'] + ' confidence'

    # Save full report
    results.to_csv("data/potential-name-variation-duplicates.csv", index=False)
    print("Saved detailed report to: data/potential-name-variation-duplicates.csv")

    # Save mapping format
    output.to_csv("data/suggested-id-mappings.csv", index=False)
    print("Saved suggested mappings to: data/suggested-id-mappings.csv")
    print("\nReview the suggested mappings and add confirmed ones to data/candidate-id-map.csv")

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY OF HIGH-CONFIDENCE DUPLICATES")
    print("="*80)
    high_conf = results[results['confidence'] == 'high']
    for _, row in high_conf.head(20).iterrows():
        print(f"\n{row['office']} - {row.get('district_id', 'N/A')}")
        print(f"  ID {row['id_1']}: {row['name_1']}")
        print(f"  ID {row['id_2']}: {row['name_2']}")
        print(f"  Detection: {row['detection_method']}")

if __name__ == "__main__":
    main()
