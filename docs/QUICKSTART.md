# Quick Start Guide

## Prerequisites

- Python 3.8 or higher
- pip

## Installation

1. **Clone or navigate to the project directory**

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure data paths (optional)**
   
   Create a `.env` file in the project root:
   ```env
   OPENPARLAMENTO_DATA_PATH=../politia-main/notebooks/data/openparlamento
   WEBTV_DATA_PATH=../politia-main/notebooks/data/camera
   ```
   
   If you don't create a `.env` file, the system will try to auto-detect these paths.

## Running the System

### Step 1: Fetch Fresh Data (Optional)

To get the latest data from OpenParlamento API:

```bash
python scripts/fetch_openparlamento.py
```

This fetches directly from the API and saves to database + JSON files.

**Note**: This takes time (3 seconds per person). For 600+ persons, expect ~30 minutes.

### Step 2: Process Data

Run the data pipeline to load data into the database:

```bash
python scripts/run_pipeline.py
```

This will:
- Create the SQLite database at `data/politia.db`
- Process all OpenParlamento JSON files (creates Person records)
- Process all WebTV JSON files (creates Session, Topic, and SpeechSegment records)
- Link speakers to Person records using name matching

**Expected output:**
```
INFO: Initializing database...
INFO: Database initialized at sqlite:///./data/politia.db
INFO: Starting data pipeline...
INFO: Found 668 OpenParlamento JSON files
INFO: Processed 668 persons
INFO: Found 101 WebTV JSON files
INFO: Processed 101 sessions
INFO: Data pipeline completed successfully!
```

### Step 3: Start the API Server

In a new terminal:

```bash
python scripts/run_api.py
```

The API will start at `http://127.0.0.1:8000`

### Step 4: Test the API

Open your browser and visit:
- API Documentation: http://127.0.0.1:8000/docs
- Health Check: http://127.0.0.1:8000/health

Or use curl:

```bash
# Get all persons
curl "http://127.0.0.1:8000/persons?limit=5"

# Search for a person
curl "http://127.0.0.1:8000/persons?search=Meloni&limit=5"

# Get speeches
curl "http://127.0.0.1:8000/speeches?limit=5"
```

### Step 5: Use the API Client

```python
from politia.api.client import APIClient

client = APIClient()
speeches = client.search_speeches(search_text="clima", limit=10)
print(f"Found {len(speeches)} speeches about climate")
```

## Troubleshooting

### Data paths not found

If you see warnings about data paths not being found:

1. Check that your data files exist
2. Create a `.env` file with absolute paths to your data directories
3. Or copy your data to `data/raw/openparlamento` and `data/raw/camera`

### Database errors

If you encounter database errors:

1. Delete `data/politia.db` and run the pipeline again
2. Make sure you have write permissions in the `data/` directory

### API not starting

If the API fails to start:

1. Check that port 8000 is not already in use
2. Change the port in `.env`: `API_PORT=8001`
3. Make sure the database exists (run the pipeline first)

## Next Steps

- Explore the API documentation at `/docs`
- Build custom agents by extending `BaseAgent`
- Scale to PostgreSQL for production use
- Add full-text search capabilities
- Implement advanced agent workflows


