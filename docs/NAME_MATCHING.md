# Name Matching in Politia

## Overview

The name matching system links speaker names from parliamentary transcripts to Person records from OpenParlamento. When a match cannot be found, the system creates an "unknown" Person record to ensure no speech data is lost.

## What Happens When No Match is Found

### Current Behavior

1. **Debug Logging**: A debug message is logged:
   ```
   No match found for speaker: MUSUMECI Nello (normalized: MUSUMECI NELLO)
   ```

2. **Unknown Person Creation**: The system automatically creates a Person record with:
   - `person_id`: `unknown_{normalized_name}` (e.g., `unknown_MUSUMECI_NELLO`)
   - `full_name`: Original speaker name from transcript
   - `family_name`: Last word of the name (assumed surname)
   - `given_name`: First word of the name (assumed given name)

3. **Speech Processing Continues**: The speech segment is still created and linked to this unknown person, so **no data is lost**.

### Example Cases

**Case 1: "LI Silvana Andreina"**
- Normalized: `LI SILVANA ANDREINA`
- If not found in OpenParlamento, creates: `unknown_LI_SILVANA_ANDREINA`
- The improved matcher now tries:
  1. Exact match: `LI SILVANA ANDREINA`
  2. Reverse: `SILVANA ANDREINA LI`
  3. Surname first: `LI SILVANA ANDREINA`
  4. Given first: `SILVANA ANDREINA LI`
  5. Surname + first given: `LI SILVANA` or `SILVANA LI`

**Case 2: "MUSUMECI Nello"**
- Normalized: `MUSUMECI NELLO`
- If not found, creates: `unknown_MUSUMECI_NELLO`
- Tries matching variations of "MUSUMECI" and "NELLO"

## Matching Strategy

The improved matcher uses a multi-step approach:

1. **Exact Match**: Normalized name matches exactly
2. **Reverse Order**: Tries name in reverse (handles "Surname Given" vs "Given Surname")
3. **Surname-First Format**: For multi-part names, tries surname + rest
4. **Given-First Format**: Tries rest + surname
5. **Surname + First Given**: More specific than surname alone
6. **Surname Only** (last resort): Only if exactly one match

## Why Matches Fail

Common reasons for failed matches:

1. **Name Format Differences**
   - Transcript: "LI Silvana Andreina" (surname first)
   - OpenParlamento: "Silvana Andreina Li" (given names first)

2. **Missing from OpenParlamento**
   - Speaker might not be a current parliamentarian
   - Historical data might not be in OpenParlamento

3. **Name Variations**
   - Nicknames vs full names
   - Different spellings
   - Accented characters

4. **Multiple People with Same Surname**
   - System avoids guessing when multiple matches exist

## Manual Review and Correction

### Viewing Unmatched Speakers

You can query the database for unknown persons:

```python
from politia.models import get_db, Person
from politia.pipeline.name_matcher import NameMatcher

db = next(get_db())
matcher = NameMatcher(db)
report = matcher.get_unmatched_speakers_report()

print(f"Total unmatched: {report['total_unmatched']}")
for speaker in report['unmatched_speakers'][:10]:
    print(f"  - {speaker['full_name']} (normalized: {speaker['normalized']})")
```

### Manual Matching

To manually link an unknown speaker to a Person:

```python
# Find the unknown person
unknown = db.query(Person).filter(Person.person_id == "unknown_MUSUMECI_NELLO").first()

# Find the correct person
correct = db.query(Person).filter(Person.full_name.like("%MUSUMECI%NELLO%")).first()

# Update all speech segments
from politia.models import SpeechSegment
speeches = db.query(SpeechSegment).filter(SpeechSegment.speaker_id == unknown.person_id).all()
for speech in speeches:
    speech.speaker_id = correct.person_id

# Delete the unknown person record
db.delete(unknown)
db.commit()
```

## Improving Match Rates

### Option 1: Add Manual Override Table

Create a CSV or JSON file with manual mappings:

```json
{
  "LI Silvana Andreina": "op_123456",
  "MUSUMECI Nello": "op_789012"
}
```

Then load these before matching.

### Option 2: Use Fuzzy Matching

Add a library like `fuzzywuzzy` or `rapidfuzz` for approximate string matching:

```python
from rapidfuzz import fuzz

# Find best match by similarity
best_match = None
best_score = 0
for person in all_persons:
    score = fuzz.ratio(normalized, person.normalized_name)
    if score > best_score and score > 80:  # 80% similarity threshold
        best_score = score
        best_match = person
```

### Option 3: Enhance Normalization

Improve the normalization to handle:
- Accented characters (è → E)
- Common abbreviations (G. → Giuseppe)
- Compound surnames (De Rossi → DEROSSI)

## Monitoring

Check match rates:

```python
from politia.models import Person

total_persons = db.query(Person).count()
unknown_persons = db.query(Person).filter(Person.person_id.like("unknown_%")).count()
match_rate = (total_persons - unknown_persons) / total_persons * 100

print(f"Match rate: {match_rate:.1f}%")
print(f"Unmatched: {unknown_persons} out of {total_persons}")
```

## Best Practices

1. **Run pipeline first** to see how many unmatched speakers you have
2. **Review unmatched speakers** periodically
3. **Create manual mappings** for common cases
4. **Monitor match rates** to track data quality
5. **Keep unknown persons** until manually reviewed (don't delete automatically)






