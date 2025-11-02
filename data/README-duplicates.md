# Candidate ID Duplicate Detection

## Overview

This directory contains tools for identifying and fixing candidate ID duplicates caused by name spelling variations.

## Files

### `candidate-id-map.csv`
The canonical mapping file used by `elections.R` to consolidate duplicate candidate IDs.

**Format:** `id_dup,id_canonical,name_canonical,note`

This file is automatically applied during the data pipeline to ensure consistent candidate IDs.

### Detection Scripts

#### `find_name_variations.py` (Recommended)
Comprehensive duplicate detection using multiple strategies:
- Consecutive election winners with same name but different IDs (high confidence)
- Candidates appearing in same district with similar names (medium confidence)

**Output files:**
- `potential-name-variation-duplicates.csv` - Detailed report with confidence levels
- `suggested-id-mappings.csv` - Ready-to-use mappings in correct format

**Usage:**
```bash
python3 find_name_variations.py
# Review suggested-id-mappings.csv
# Add confirmed duplicates to candidate-id-map.csv
# Rerun: Rscript elections.R
```

#### `find_dup_candidates.py` (Legacy)
Original fuzzy string matching approach. Requires `fuzzywuzzy` library.
Not part of standard pipeline - more prone to false positives.

## Detection Strategies

### High-Confidence Indicators
1. **Consecutive winners**: Same person won back-to-back elections but isn't marked as incumbent
   - Example: "Elizabeth A. Warren" (ID 74528) → "Elizabeth Ann Warren" (ID 110183)

2. **Same last name + city + district**: Multiple IDs for same person in same location
   - Example: "David Allen Robertson" (ID 78701) vs "David A. Robertson" (ID 88422)

### Common Name Variations
- Middle name expanded/abbreviated: "Carol A." → "Carol Ann"
- Middle initial added/removed: "Daniel J." → "Daniel Joseph"
- Punctuation changes: "Antonio F.D." → "Antonio d. F."

## Workflow

1. Run duplicate detection:
   ```bash
   python3 find_name_variations.py
   ```

2. Review `suggested-id-mappings.csv` for high-confidence matches

3. Add confirmed duplicates to `candidate-id-map.csv`

4. Regenerate database:
   ```bash
   Rscript elections.R
   ```

5. Verify incumbency is now correct for affected candidates

## Impact

As of the most recent detection run:
- **18 unique candidate ID pairs identified**
- **14 high-confidence duplicates** (consecutive winners)
- **15 incumbency records fixed** after applying mappings
- Notable fixes: Elizabeth Warren, Carol Doherty, Brendan Crighton, Antonio Cabral

## Notes

- The mapping file uses the **older/lower ID** as canonical when possible
- High-confidence duplicates should be added immediately
- Medium-confidence duplicates require manual verification
- Always rerun `elections.R` after updating the mapping file
