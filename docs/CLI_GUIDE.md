# Politia Engine CLI

The main way to refresh data sources is the **politia-engine** CLI.

## Commands

```bash
politia-engine refresh --source <webtv|politicians> [options]
```

After installing the package (`pip install -e .`), the `politia-engine` command is available. You can also run:

```bash
python -m politia.cli refresh --source webtv
```

---

## Refresh source: `webtv`

Fetches parliamentary transcript data from Camera dei Deputati (WebTV).

### Options

| Option | Description |
|--------|-------------|
| `--from-meeting N` | Start meeting number (inclusive). |
| `--to-meeting M` | End meeting number (inclusive). |
| `--max-meetings K` | Cap total meetings to fetch in this run. |
| `--legislature` | Legislature number (default: 19). |
| `--rate-limit` | Seconds between requests (default: 1.5). |
| `--no-skip-existing` | Re-fetch and overwrite existing session files. |

### Edge cases and behavior

1. **Neither `--from-meeting` nor `--to-meeting`**  
   Fetches the **100 most recent** meetings: the CLI discovers the latest meeting number on the server (by probing), then fetches from `(latest - 99)` to `latest`. If the server has fewer than 100 meetings, it fetches from meeting 1 to the latest.

2. **Only `--from-meeting N`**  
   Fetches from meeting **N up to the latest available**. The CLI probes the server from N upward to find the highest existing meeting, then fetches the range `[N, latest]`.

3. **Only `--to-meeting M`**  
   Fetches **the single meeting M** (useful for backfilling or re-fetching one session).

4. **Both `--from-meeting N` and `--to-meeting M`**  
   Fetches the **range [N, M]** (inclusive). Order does not matter: the smaller value is used as start, the larger as end.

5. **Single meeting**  
   Use `--from-meeting 450 --to-meeting 450` to fetch only meeting 450.

6. **`--max-meetings K`**  
   In any of the above modes, if the computed range would fetch more than K meetings, the range is capped: only the **last K** meetings in that range are fetched (so you get the most recent K within the range).  
   Example: range 1–500 with `--max-meetings 100` fetches meetings 401–500.

7. **First run (no local data)**  
   For “100 most recent”, the CLI must discover the latest meeting by probing the server starting from meeting 1. If the server returns nothing in the probe range, the command fails and suggests using `--from-meeting N` to set a starting point.

### Examples

```bash
# 100 most recent meetings (default)
politia-engine refresh --source webtv

# Range 450–600
politia-engine refresh --source webtv --from-meeting 450 --to-meeting 600

# From 450 up to latest
politia-engine refresh --source webtv --from-meeting 450

# Single meeting 450
politia-engine refresh --source webtv --to-meeting 450
# or
politia-engine refresh --source webtv --from-meeting 450 --to-meeting 450

# At most 50 meetings from 400 to latest
politia-engine refresh --source webtv --from-meeting 400 --max-meetings 50

# Fill a gap (e.g. you have 355–356 and 457+ but missing 357–456)
politia-engine refresh --source webtv --from-meeting 357 --to-meeting 456
```

---

## Refresh source: `politicians`

Fetches person data from the OpenParlamento API. Only **full refresh** is supported: all persons are fetched and upserted into the database (and optionally saved to JSON files).

### Options

| Option | Description |
|--------|-------------|
| `--rate-limit` | Seconds between API requests (default from config: 1.5). |

### Example

```bash
politia-engine refresh --source politicians
```

---

## After refreshing

- **WebTV**: Raw JSON is written under `data/raw/camera/`. To load it into the database, run the pipeline:
  ```bash
  python scripts/run_pipeline.py
  ```
- **Politicians**: Data is written directly to the database (and optionally to JSON under `data/raw/openparlamento/`).
