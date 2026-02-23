# OpenParlamento Fetcher Usage Guide

## Overview

The `OpenParlamentoFetcher` automatically fetches fresh data from the OpenParlamento API and can save it directly to your database or to JSON files.

## Quick Start

### Fetch and Save to Database + Files

```bash
python scripts/fetch_openparlamento.py
```

This will:
- Fetch all persons from the API
- Save to database (updates existing, creates new)
- Save to JSON files as backup
- Respect rate limiting (3 seconds between requests)

## Usage Options

### 1. Fetch to Database Only

```python
from politia.models import get_db
from politia.pipeline.openparlamento_fetcher import OpenParlamentoFetcher

db = next(get_db())
fetcher = OpenParlamentoFetcher(
    db=db,
    save_to_files=False,
    rate_limit_delay=3.0
)

count = fetcher.fetch_all_persons()
db.commit()
```

### 2. Fetch to Files Only (No Database)

```python
from politia.pipeline.openparlamento_fetcher import OpenParlamentoFetcher

fetcher = OpenParlamentoFetcher(
    db=None,  # No database
    save_to_files=True,
    output_path=Path("data/raw/openparlamento"),
    rate_limit_delay=3.0
)

count = fetcher.fetch_all_persons()
```

### 3. Fetch Single Person

```python
fetcher = OpenParlamentoFetcher()
person_data = fetcher.fetch_person_by_id(12345)
```

### 4. Custom Processing

```python
def my_processor(person_data):
    # Do something with person_data
    print(f"Processing {person_data.get('full_name')}")

fetcher = OpenParlamentoFetcher()
fetcher.fetch_all_persons(process_callback=my_processor)
```

## Configuration

### Rate Limiting

Default is 3 seconds between requests. Adjust if needed:

```python
fetcher = OpenParlamentoFetcher(rate_limit_delay=5.0)  # 5 seconds
```

### Output Path

Control where JSON files are saved:

```python
fetcher = OpenParlamentoFetcher(
    output_path=Path("custom/path/openparlamento")
)
```

## API Health Check

Before fetching, check if API is accessible:

```python
fetcher = OpenParlamentoFetcher()
if fetcher.check_api_health():
    print("API is accessible")
    fetcher.fetch_all_persons()
else:
    print("API is not accessible")
```

## Performance

- **Time**: ~3 seconds per person (due to rate limiting)
- **600 persons**: ~30 minutes
- **1000 persons**: ~50 minutes

The fetcher:
- Handles pagination automatically
- Fetches list, then details for each person
- Updates existing records in database
- Creates new records if they don't exist
- Saves to files as backup (if enabled)

## Error Handling

The fetcher handles:
- Network errors (retries not implemented, but logs errors)
- Rate limiting (respects delays)
- Missing data (skips persons without URLs)
- Database errors (rolls back on failure)

## Integration with Pipeline

After fetching, you can still run the normal pipeline:

```bash
# Fetch fresh data
python scripts/fetch_openparlamento.py

# Process WebTV data (sessions, speeches)
python scripts/run_pipeline.py
```

The pipeline will use the fresh data from the database.

## Best Practices

1. **Run during off-peak hours** - Large fetches take time
2. **Save to files** - Keep backups of fetched data
3. **Monitor logs** - Check for errors or rate limit issues
4. **Incremental updates** - Consider fetching only changed persons (future enhancement)

## Troubleshooting

### API Not Accessible
- Check internet connection
- Verify API URL is correct
- Check if API requires authentication (currently doesn't)

### Rate Limiting Issues
- Increase `rate_limit_delay` if you get 429 errors
- The API may have stricter limits than expected

### Database Errors
- Ensure database is initialized
- Check database permissions
- Verify SQLAlchemy connection

### Missing Persons
- Some persons may not have detail URLs
- Check logs for warnings about missing URLs





