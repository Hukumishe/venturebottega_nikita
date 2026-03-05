# All commands reference

Single reference for every command used in the Politia project.

---

## Setup & install

```bash
# Install dependencies
pip install -r requirements.txt

# Or use pre-built wheels only (if Rust/Cargo issues)
pip install --only-binary :all: -r requirements.txt

# Editable install (enables politia-engine CLI)
pip install -e .
```

---

## CLI: politia-engine

Main interface for refreshing data. Use after `pip install -e .`, or run as module:

```bash
python -m politia.cli <command> [options]
```

### Refresh data sources

```bash
politia-engine refresh --source <webtv|politicians> [options]
```

#### Refresh WebTV (Camera transcripts)

| Command | Description |
|--------|-------------|
| `politia-engine refresh --source webtv` | 100 most recent meetings (discovers latest, fetches latest-99..latest) |
| `politia-engine refresh --source webtv --from-meeting N` | From meeting N up to latest |
| `politia-engine refresh --source webtv --to-meeting M` | Single meeting M |
| `politia-engine refresh --source webtv --from-meeting N --to-meeting M` | Range [N, M] (inclusive) |
| `politia-engine refresh --source webtv --from-meeting N --to-meeting M --max-meetings K` | Same range, cap at K meetings (last K in range) |

**WebTV options**

| Option | Description |
|--------|-------------|
| `--from-meeting N` | Start meeting number (inclusive) |
| `--to-meeting M` | End meeting number (inclusive), or single meeting if only this is set |
| `--max-meetings K` | Cap total meetings to fetch |
| `--legislature N` | Legislature number (default: 19) |
| `--rate-limit SECS` | Seconds between requests (default: 1.5; increase if 429/blocked) |
| `--no-skip-existing` | Re-fetch and overwrite existing session files |

**WebTV examples**

```bash
# 100 most recent
politia-engine refresh --source webtv

# Range 450–600
politia-engine refresh --source webtv --from-meeting 450 --to-meeting 600

# From 450 to latest
politia-engine refresh --source webtv --from-meeting 450

# Single meeting 450
politia-engine refresh --source webtv --to-meeting 450

# At most 50 meetings from 400 to latest
politia-engine refresh --source webtv --from-meeting 400 --max-meetings 50
```

#### Refresh politicians (OpenParlamento)

Full refresh only (all persons).

Optional: `--rate-limit SECS` (default from config).

---

## Scripts

### Run pipeline (load raw data into DB)

Processes OpenParlamento and WebTV raw files into the database. Run after refreshing WebTV.

```bash
python scripts/run_pipeline.py
```

### Run API server

Starts the FastAPI server (default http://127.0.0.1:8000).

```bash
python scripts/run_api.py
```

### Legacy fetch scripts (optional)

Alternative to `politia-engine refresh`; same behavior, different interface.

**OpenParlamento (politicians)**

```bash
python scripts/fetch_openparlamento.py
```

**WebTV**

```bash
# Incremental (new sessions only)
python scripts/fetch_webtv.py

# Manual range
python scripts/fetch_webtv.py --start 347 --end 450

# Incremental with max sessions
python scripts/fetch_webtv.py --max-sessions 50

# Options: --legislature 19, --rate-limit 1.5, --no-skip-existing
python scripts/fetch_webtv.py --start 347 --end 450 --no-skip-existing
```

---

## Typical workflows

**First-time setup**

```bash
pip install -e .
politia-engine refresh --source politicians
politia-engine refresh --source webtv
python scripts/run_pipeline.py
python scripts/run_api.py
```

**Update WebTV only**

```bash
politia-engine refresh --source webtv
python scripts/run_pipeline.py
```

**Update politicians only**

```bash
politia-engine refresh --source politicians
```

**Fetch a specific meeting range**

```bash
politia-engine refresh --source webtv --from-meeting 450 --to-meeting 600
python scripts/run_pipeline.py
```
