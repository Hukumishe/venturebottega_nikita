# Politia Architecture

## System Overview

Politia is a multi-layered data engineering system designed to process, store, and analyze Italian parliamentary data. The architecture follows a clean separation of concerns with five distinct layers.

## Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer                             │
│  (FastAPI REST API - Controlled Data Access)           │
│  (API Client - Programmatic Access)                    │
└────────────────────┬────────────────────────────────────┘
                    │
┌────────────────────▼────────────────────────────────────┐
│                 Storage Layer                            │
│  (SQLite/PostgreSQL - Structured Data)                  │
└────────────────────┬────────────────────────────────────┘
                    │
┌────────────────────▼────────────────────────────────────┐
│                Data Pipeline                             │
│  (Ingestion, Cleaning, Normalization, Structuring)     │
└────────────────────┬────────────────────────────────────┘
                    │
┌────────────────────▼────────────────────────────────────┐
│                 Data Sources                             │
│  (OpenParlamento API, WebTV XML/JSON)                   │
└─────────────────────────────────────────────────────────┘
```

## Components

### 1. Data Pipeline (`politia/pipeline/`)

**Responsibilities:**
- Ingestion of raw data from multiple sources
- Data cleaning and normalization
- Entity standardization (name matching)
- Structuring into canonical entities

**Key Components:**
- `OpenParlamentoProcessor`: Processes politician profiles
- `WebTVProcessor`: Processes parliamentary transcripts
- `NameMatcher`: Matches speaker names to Person records
- `DataPipeline`: Orchestrates the complete pipeline

**Data Flow:**
```
Raw JSON Files → Processors → Structured Entities → Database
```

### 2. Storage Layer (`politia/models/`)

**Database Schema:**
- **Person**: Politician profiles with party, roles, metadata
- **Session**: Parliamentary sessions with date, chamber, legislature
- **Topic**: Discussion topics within sessions
- **SpeechSegment**: Individual speech segments with text, speaker, date

**Design Decisions:**
- SQLite for MVP (easy migration to PostgreSQL)
- SQLAlchemy ORM for database abstraction
- Foreign key relationships for data integrity
- JSON fields for flexible metadata storage

### 3. API Layer (`politia/api/`)

**Endpoints:**
- `/persons` - Person search and retrieval
- `/sessions` - Session listing and filtering
- `/topics` - Topic search
- `/speeches` - Speech segment search with full-text capabilities

**Features:**
- Pagination for all list endpoints
- Filtering by multiple criteria
- Full-text search capabilities
- RESTful design
- OpenAPI/Swagger documentation

### 4. API Client (`politia/api/client.py`)

**Purpose:**
- Simple Python client for programmatic API access
- Useful for data analysis scripts and integrations
- Provides convenient methods for common queries

**Design:**
- Uses the REST API (not direct database access)
- Separation ensures system stability
- Lightweight wrapper around HTTP requests

### 5. Configuration (`politia/config.py`)

**Settings:**
- Database connection
- Data source paths
- API configuration
- Logging settings

**Environment Variables:**
- `.env` file support
- Auto-detection of data paths
- Production-ready configuration management

## Data Flow

### Pipeline Execution

1. **OpenParlamento Processing**
   - Read JSON files
   - Extract person information
   - Create/update Person records
   - Store raw data for reference

2. **WebTV Processing**
   - Read session JSON files
   - Extract sessions, topics, interventions
   - Match speakers to Person records
   - Create Session, Topic, SpeechSegment records

3. **Name Matching**
   - Normalize names (remove titles, standardize format)
   - Match using surname and given name
   - Handle ambiguous cases
   - Create unknown speaker records when needed

### API Request Flow

1. Client sends request to API endpoint
2. API validates request parameters
3. Query database using SQLAlchemy
4. Apply filters, pagination, search
5. Serialize results using Pydantic schemas
6. Return JSON response

### API Client Usage

1. Initialize APIClient with API URL
2. Call methods to query the API
3. Process returned data in your scripts
4. Use for data analysis, reporting, or integrations

## Scalability Path

### Current (MVP)
- SQLite database
- Single-threaded pipeline
- In-memory name matching
- Basic API with no caching

### Production Ready
- PostgreSQL database
- Parallel pipeline processing
- Redis caching layer
- Full-text search (PostgreSQL FTS or Elasticsearch)
- API authentication and rate limiting
- Monitoring and logging

### Advanced
- Distributed processing (Airflow/Prefect)
- Vector embeddings for semantic search
- Real-time data ingestion
- Advanced analytics and reporting
- Advanced analytics layer

## Data Quality

### Validation Steps
- Required field validation
- Duplicate detection
- Name matching confidence scoring
- Logging of failed matches
- Manual review process for conflicts

### Traceability
- Source references in all entities
- Version tracking for datasets
- Audit logs for data changes
- Reproducible research support

## Security Considerations

### Current MVP
- Local-only API (127.0.0.1)
- No authentication
- CORS enabled for development

### Production Requirements
- API authentication (JWT/OAuth)
- Rate limiting
- Input validation and sanitization
- Secure database connections
- Encrypted sensitive data

## Monitoring

### Current
- Loguru logging
- Basic error handling
- Pipeline execution logs

### Production
- Structured logging (JSON)
- Metrics collection (Prometheus)
- Error tracking (Sentry)
- Performance monitoring
- Health checks

## Future Enhancements

1. **Advanced Search**
   - Full-text search with ranking
   - Semantic search with embeddings
   - Multi-field search

2. **Advanced Querying**
   - Full-text search with ranking
   - Complex filtering and aggregation
   - Batch operations
   - Export capabilities

3. **Data Enrichment**
   - External context sources
   - News article linking
   - Social media signals
   - Trend analysis

4. **Analytics**
   - Voting pattern analysis
   - Topic modeling
   - Sentiment analysis
   - Network analysis


