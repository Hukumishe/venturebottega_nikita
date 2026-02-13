# Politia Data Engineering System - MVP

A data engineering foundation for processing, storing, and analyzing Italian parliamentary data.

## Overview

Politia is a system for processing, storing, and analyzing Italian parliamentary data. It provides:

- **Data Pipeline**: Processes raw parliamentary data from OpenParlamento and WebTV sources
- **Structured Storage**: SQLite database (easily scalable to PostgreSQL)
- **REST API**: FastAPI-based API for accessing structured data
- **API Client**: Simple Python client for programmatic access

## Architecture

The system follows a layered architecture:

```
Data Sources (OpenParlamento, WebTV)
    ↓
Data Pipeline (Ingestion, Cleaning, Structuring)
    ↓
Storage Layer (SQLite/PostgreSQL)
    ↓
API Layer (FastAPI REST API)
    ↓
API Client (Programmatic Access)
```

## Project Structure

```
politia/
├── models/          # SQLAlchemy data models
├── pipeline/        # Data processing pipeline
├── api/            # FastAPI application and client
└── config.py        # Configuration management

scripts/
├── run_pipeline.py  # Run data pipeline
└── run_api.py      # Run API server

data/               # Data directory (created automatically)
└── politia.db      # SQLite database
```

## Setup

### 1. Install Dependencies

**If you encounter Rust/Cargo errors**, see [INSTALL.md](INSTALL.md) for troubleshooting.

```bash
# Standard install
pip install -r requirements.txt

# OR use pre-built wheels only (recommended if Rust is not installed)
pip install --only-binary :all: -r requirements.txt
```

### 2. Configure Data Paths

Create a `.env` file in the project root (optional):

```env
# Database
DATABASE_URL=sqlite:///./data/politia.db

# Data paths (absolute or relative to project root)
OPENPARLAMENTO_DATA_PATH=../politia-main/notebooks/data/openparlamento
WEBTV_DATA_PATH=../politia-main/notebooks/data/camera

# API
API_HOST=127.0.0.1
API_PORT=8000
```

If you don't create a `.env` file, the system will try to auto-detect data paths.

### 3. Fetch Fresh Data (Optional)

To fetch fresh data from OpenParlamento API:

```bash
python scripts/fetch_openparlamento.py
```

This will:
- Fetch all persons from the OpenParlamento API
- Save to database
- Optionally save to JSON files as backup
- Respects rate limiting (3 seconds between requests)

### 4. Initialize Database and Run Pipeline

```bash
python scripts/run_pipeline.py
```

This will:
- Create the SQLite database
- Process all OpenParlamento JSON files (or use data from API fetch)
- Process all WebTV JSON files
- Link speakers to Person records

### 5. Start the API Server

```bash
python scripts/run_api.py
```

The API will be available at `http://127.0.0.1:8000`

## API Usage

### Endpoints

#### Persons
- `GET /persons` - List all persons (with pagination, search, party filter)
- `GET /persons/{person_id}` - Get specific person
- `GET /persons/{person_id}/speeches` - Get all speeches by a person

#### Sessions
- `GET /sessions` - List all sessions (with pagination, filters)
- `GET /sessions/{session_id}` - Get specific session

#### Topics
- `GET /topics` - List all topics (with pagination, search)
- `GET /topics/{topic_id}` - Get specific topic

#### Speeches
- `GET /speeches` - List speech segments (with filters: speaker, session, topic, date, search)
- `GET /speeches/{speech_id}` - Get specific speech segment

### Example Queries

```bash
# Search for persons
curl "http://127.0.0.1:8000/persons?search=Meloni&limit=10"

# Get speeches by a person
curl "http://127.0.0.1:8000/persons/op_12345/speeches?limit=50"

# Search speeches by text
curl "http://127.0.0.1:8000/speeches?search=clima&limit=20"

# Get topics in a session
curl "http://127.0.0.1:8000/topics?session_id=session_19_347"
```

### API Documentation

Once the API is running, visit:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Data Models

### Person
- `person_id`: Unique identifier
- `full_name`, `family_name`, `given_name`: Name fields
- `party`: Political party
- `roles`: JSON array of roles
- `source_ids`: Source identifiers (OpenParlamento, etc.)

### Session
- `session_id`: Unique identifier
- `date`: Session date
- `chamber`: "C" (Camera) or "S" (Senato)
- `legislature`, `session_number`: Session identifiers

### Topic
- `topic_id`: Unique identifier
- `session_id`: Parent session
- `title`: Topic title

### SpeechSegment
- `speech_id`: Unique identifier
- `session_id`, `topic_id`: Parent references
- `speaker_id`: Reference to Person
- `text`: Speech text
- `date`: Speech date

## API Client

For programmatic access to the API from Python scripts:

```python
from politia.api.client import APIClient

# Initialize client
client = APIClient()

# Search for persons
persons = client.search_persons("Meloni", limit=10)

# Search speeches
speeches = client.search_speeches(search_text="clima", limit=50)

# Get person's speeches
person_speeches = client.get_person_speeches("op_12345", limit=100)
```

## Scaling Considerations

The MVP uses SQLite for simplicity. To scale to production:

1. **Database**: Switch to PostgreSQL**
   - Change `DATABASE_URL` in `.env` to PostgreSQL connection string
   - Install `psycopg2-binary` package

2. **Caching**: Add Redis for API response caching

3. **Search**: Integrate full-text search (PostgreSQL FTS, Elasticsearch, or similar)

4. **API**: Add authentication, rate limiting, and monitoring

5. **Pipeline**: Add scheduling (Airflow, Prefect) and parallel processing

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black politia/
```

## GitHub Setup

To set up GitHub repository and push code:

```bash
# Install GitHub CLI (if not installed)
# Windows: winget install GitHub.cli
# macOS: brew install gh
# Linux: sudo apt install gh

# Authenticate
gh auth login

# Create repository and push
gh repo create venturebottega --public --source=. --remote=origin --push
```

See [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md) for detailed GitHub CLI usage.

## License

[Your License Here]

## Contributing

[Contributing Guidelines]

