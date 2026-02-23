# Data Cleaning in Politia

## Overview

Data cleaning happens at multiple stages in the pipeline to ensure data quality and consistency. Here's how it works:

## Cleaning Steps

### 1. **Name Normalization** (NameMatcher)

**Location**: `politia/pipeline/name_matcher.py`

**What it does**:
- Removes titles: "PRESIDENTE", "ON", "ONOREVOLE", "SENATORE", "DEPUTATO", "MINISTRO", "MINISTRA"
- Converts to uppercase for consistent matching
- Removes special characters (keeps only letters, numbers, spaces)
- Normalizes whitespace (removes extra spaces)
- Handles name format variations (surname first vs given name first)

**Example**:
```
Input:  "PRESIDENTE LI Silvana Andreina"
Output: "LI SILVANA ANDREINA"
```

### 2. **Empty Data Filtering** (WebTV Processor)

**Location**: `politia/pipeline/webtv_processor.py`

**What it does**:
- Skips empty topics (no title or empty interventions)
- Skips empty speeches (no text content)
- Skips invalid interventions (not a dictionary)
- Validates text is not just whitespace

**Code**:
```python
if not topic_title or not interventions:
    continue  # Skip empty topics

if not text.strip():
    continue  # Skip empty speeches
```

### 3. **Duplicate Detection**

**Location**: Both processors

**What it does**:
- **Persons**: Checks if person exists by `person_id` before creating
- **Sessions**: Checks if session exists before creating
- **Topics**: Checks if topic exists before creating
- **Speeches**: Checks if speech exists by `speech_id` before creating

**Prevents**: Duplicate records in database

### 4. **Data Type Validation**

**Location**: `politia/pipeline/webtv_processor.py`

**What it does**:
- Validates interventions are dictionaries
- Validates required fields exist
- Type conversion (string to int for session numbers)

**Code**:
```python
if not isinstance(intervention, dict):
    continue  # Skip invalid data types
```

### 5. **Error Handling & Rollback**

**Location**: Both processors

**What it does**:
- Catches exceptions during processing
- Rolls back database transactions on error
- Logs errors for review
- Continues processing other files (doesn't stop entire pipeline)

**Code**:
```python
try:
    self.process_file(json_file)
except Exception as e:
    logger.error(f"Error processing {json_file}: {e}")
    self.db.rollback()
    continue  # Process next file
```

### 6. **Data Extraction & Structuring**

**Location**: Both processors

**What it does**:
- Extracts only relevant fields from raw data
- Structures data into canonical format
- Handles missing fields gracefully (uses defaults)
- Creates proper relationships (session → topic → speech)

**Example** (OpenParlamento):
```python
# Extract only what we need
family_name = data.get('family_name', '')  # Handles missing
given_name = data.get('given_name', '')
full_name = f"{family_name} {given_name}".strip()  # Clean whitespace
```

### 7. **Name Matching & Entity Resolution**

**Location**: `politia/pipeline/name_matcher.py`

**What it does**:
- Matches speaker names to Person records
- Handles name format variations
- Creates "unknown" persons for unmatched speakers (preserves data)
- Prevents data loss from unmatched names

## Current Cleaning Capabilities

### ✅ What's Implemented

1. **Name normalization** - Removes titles, special chars, normalizes format
2. **Empty data filtering** - Skips empty/invalid records
3. **Duplicate detection** - Prevents duplicate records
4. **Type validation** - Validates data types
5. **Error handling** - Graceful error handling with rollback
6. **Data structuring** - Extracts and structures relevant fields

### ⚠️ What Could Be Enhanced

1. **Encoding normalization** - Currently assumes UTF-8, could validate
2. **Text cleaning** - Remove extra whitespace, normalize quotes
3. **Date validation** - Currently uses placeholder dates for sessions
4. **Malformed record detection** - More aggressive validation
5. **Data quality scoring** - Confidence scores for matches
6. **Deduplication** - More sophisticated duplicate detection

## Data Quality Flow

```
Raw Data (JSON/XML)
    ↓
1. Parse & Extract
    ↓
2. Validate Types
    ↓
3. Filter Empty/Invalid
    ↓
4. Normalize Names
    ↓
5. Check Duplicates
    ↓
6. Structure Data
    ↓
7. Save to Database
```

## Example: Speech Cleaning

**Raw Input** (from WebTV):
```json
{
  "speaker": "PRESIDENTE LI Silvana",
  "text": "  Some text with extra spaces  "
}
```

**After Cleaning**:
- Speaker normalized: "LI SILVANA" (title removed, uppercase)
- Text trimmed: "Some text with extra spaces"
- Empty check: Passed (has text)
- Type check: Passed (is dict)
- Duplicate check: Checked by speech_id hash

**Result**: Clean, structured SpeechSegment record

## Validation Points

### Required Fields
- Person: `person_id`, `full_name`
- Session: `session_id`, `date`, `chamber`
- Topic: `topic_id`, `session_id`, `title`
- SpeechSegment: `speech_id`, `session_id`, `text`, `date`

### Optional but Validated
- Speaker matching (creates unknown if not found)
- Party extraction (handles missing gracefully)
- Role extraction (handles missing gracefully)

## Error Recovery

The system is designed to be resilient:

1. **File-level errors**: One bad file doesn't stop the pipeline
2. **Record-level errors**: One bad record doesn't stop file processing
3. **Transaction rollback**: Errors don't leave partial data
4. **Logging**: All errors logged for review
5. **Continue processing**: Pipeline continues with remaining data

## Summary

**Current cleaning includes**:
- Name normalization
- Empty data filtering
- Duplicate detection
- Type validation
- Error handling
- Data structuring

**The system ensures**:
- No duplicate records
- No empty/invalid data stored
- Consistent name formats
- Proper error recovery
- Data preservation (unknown speakers)





