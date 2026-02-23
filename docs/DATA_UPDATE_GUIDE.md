# Data Update Guide

This guide explains how to update data in the Politia system, including both OpenParlamento (politicians) and WebTV (parliamentary transcripts) data sources.

## Overview

The Politia system supports two main data sources:

1. **OpenParlamento**: Politician profiles, roles, and metadata
2. **WebTV**: Parliamentary session transcripts, topics, and speeches

Both sources support incremental updates, meaning you can fetch only new data without re-downloading everything.

---

## OpenParlamento Data Updates

### What Gets Updated

- **Person profiles**: Names, parties, roles, birth information
- **Metadata**: Images, slugs, source IDs
- **Raw data**: Full JSON from API (always updated)

### Update Behavior

- **Existing records**: Partially updated (party, raw_data, source_ids)
- **New records**: Created automatically
- **Names**: Only updated if previously empty

### How to Update

```bash
python scripts/fetch_openparlamento.py
```

This script will:
1. Connect to OpenParlamento API
2. Fetch all persons (paginated)
3. Update existing records or create new ones
4. Save to database and optionally to JSON files
5. Commit changes every 50 records

### Configuration

The fetcher uses these settings from `politia/config.py`:
- `OPENPARLAMENTO_API_BASE`: API base URL
- `FETCH_RATE_LIMIT_DELAY`: Delay between requests (default: 3.0 seconds)

### Example Output

```
[INFO] Initializing database...
[INFO] Checking API health...
[INFO] API is accessible. Starting fetch...
[INFO] Fetching page 1 of persons...
[INFO] Fetched person: Mario Rossi
[INFO] Fetch completed successfully! Fetched 945 persons.
```

---

## WebTV Data Updates

### What Gets Updated

- **Sessions**: Parliamentary session metadata
- **Topics**: Discussion topics within sessions
- **Speeches**: Individual speech segments/interventions

### Update Behavior

- **Existing sessions**: Skipped by default (not updated)
- **New sessions**: Fetched and saved
- **Incremental mode**: Only fetches sessions after the last one

### Update Methods

#### 1. Incremental Update (Recommended for Monthly Updates)

Fetches only new sessions automatically:

```bash
python scripts/fetch_webtv.py
```

This will:
1. Check existing session files
2. Find the last fetched session number
3. Fetch only new sessions starting from last + 1
4. Stop after 5 consecutive missing sessions

**Example:**
- Last session: 450
- New sessions available: 451, 452, 453
- Will fetch: 451, 452, 453
- Will skip: 454, 455 (if they don't exist)

#### 2. Incremental with Limit

Limit the number of new sessions to fetch:

```bash
python scripts/fetch_webtv.py --max-sessions 50
```

#### 3. Manual Range

Specify exact session range:

```bash
python scripts/fetch_webtv.py --start 347 --end 450
```

#### 4. Re-fetch Existing Sessions

Force re-download of existing sessions:

```bash
python scripts/fetch_webtv.py --start 347 --end 450 --no-skip-existing
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--legislature` | Legislature number | 19 |
| `--start` | Starting session number | None (incremental) |
| `--end` | Ending session number | None |
| `--incremental` | Use incremental mode | True |
| `--no-incremental` | Disable incremental mode | False |
| `--max-sessions` | Max new sessions to fetch | None (unlimited) |
| `--rate-limit` | Seconds between requests | 5.0 |
| `--skip-existing` | Skip existing files | True |
| `--no-skip-existing` | Re-fetch existing files | False |

### Processing Downloaded Data

After fetching WebTV data, you need to process it into the database:

```bash
python scripts/run_pipeline.py
```

This will:
1. Process all JSON files in `data/raw/camera/`
2. Create/update Session, Topic, and SpeechSegment records
3. Match speakers to Person records
4. Handle unknown speakers

### Example Workflow

```bash
# 1. Fetch new sessions (incremental)
python scripts/fetch_webtv.py

# 2. Process into database
python scripts/run_pipeline.py

# 3. Verify in API
curl http://127.0.0.1:8000/sessions?limit=5
```

---

## Monthly Update Workflow

For monthly updates, follow this recommended workflow:

### Step 1: Update OpenParlamento Data

```bash
python scripts/fetch_openparlamento.py
```

**Time**: ~30-60 minutes (depends on API rate limits)
**Frequency**: Monthly or when politician data changes

### Step 2: Update WebTV Data (Incremental)

```bash
python scripts/fetch_webtv.py
```

**Time**: ~5-10 minutes per new session
**Frequency**: Monthly (fetches only new sessions)

### Step 3: Process WebTV Data

```bash
python scripts/run_pipeline.py
```

**Time**: ~1-2 minutes per session file
**Frequency**: After fetching new WebTV data

### Step 4: Verify Updates

```bash
# Check API health
curl http://127.0.0.1:8000/health

# Check latest sessions
curl http://127.0.0.1:8000/sessions?limit=5

# Check person count
curl http://127.0.0.1:8000/persons?limit=1
```

---

## Understanding Update Behavior

### OpenParlamento Updates

**What gets updated:**
- ✅ Party affiliation (if changed)
- ✅ Source IDs
- ✅ Raw data (full JSON)
- ⚠️ Names (only if previously empty)
- ❌ Roles (not updated, only set on creation)

**Why partial updates?**
- Names are considered stable identifiers
- Roles require careful handling to avoid data loss
- Raw data always updated for full traceability

### WebTV Updates

**What gets updated:**
- ❌ Existing sessions (skipped by default)
- ❌ Existing topics (skipped)
- ❌ Existing speeches (skipped)
- ✅ New sessions (always fetched)
- ✅ New topics (always created)
- ✅ New speeches (always created)

**Why no updates?**
- Transcripts are considered immutable once published
- Updates would require content comparison (not implemented)
- Prevents accidental overwrites

**To update existing WebTV data:**
1. Delete the JSON file
2. Re-run `fetch_webtv.py` with `--no-skip-existing`
3. Re-run `run_pipeline.py`

---

## Troubleshooting

### Issue: "No existing sessions found"

**Solution**: Run with manual range for initial fetch:
```bash
python scripts/fetch_webtv.py --start 347 --end 450
```

### Issue: API rate limiting

**Solution**: Increase rate limit delay:
```bash
python scripts/fetch_webtv.py --rate-limit 10.0
```

### Issue: Missing sessions in range

**Solution**: This is normal - some session numbers may not exist. The fetcher will skip them automatically.

### Issue: Database not updating

**Solution**: 
1. Check if files were fetched: `ls data/raw/camera/`
2. Run pipeline: `python scripts/run_pipeline.py`
3. Check logs for errors

### Issue: Speaker names not matching

**Solution**: 
1. Check unmatched speakers: See `docs/NAME_MATCHING.md`
2. Review logs for matching attempts
3. Manually review and update Person records if needed

---

## Best Practices

1. **Regular Updates**: Update monthly to keep data current
2. **Incremental First**: Always use incremental mode for WebTV unless you need specific range
3. **Backup Before Updates**: Backup database before major updates
4. **Monitor Logs**: Check logs for warnings and errors
5. **Verify After Updates**: Always verify data in API after updates
6. **Rate Limiting**: Respect API rate limits to avoid being blocked

---

## File Locations

- **OpenParlamento JSON files**: `data/raw/openparlamento/`
- **WebTV JSON files**: `data/raw/camera/`
- **Database**: `data/politia.db` (SQLite)
- **Logs**: Console output (or configured log file)

---

## API Endpoints for Verification

After updating data, verify using these endpoints:

```bash
# Health check
GET /health

# Latest sessions
GET /sessions?limit=5

# Person count
GET /persons?limit=1  # Check total in response

# Recent speeches
GET /speeches?limit=10

# Search for specific person
GET /persons?search=Rossi
```

---

## Automation (Future)

For production, consider automating monthly updates:

1. **Cron job** (Linux/Mac):
   ```bash
   0 2 1 * * cd /path/to/politia && python scripts/fetch_openparlamento.py
   0 3 1 * * cd /path/to/politia && python scripts/fetch_webtv.py
   0 4 1 * * cd /path/to/politia && python scripts/run_pipeline.py
   ```

2. **Task Scheduler** (Windows):
   - Create scheduled tasks for each script
   - Run on first day of each month

3. **GitHub Actions**:
   - Create workflow for monthly updates
   - Commit updated data files

---

## Support

For issues or questions:
1. Check logs for error messages
2. Review this guide
3. See `docs/` directory for additional documentation
4. Check `README.md` for general information



