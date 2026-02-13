# OpenParlamento API Endpoints for Data Refresh

Based on the [OpenParlamento API Explorer](https://service.opdm.openpolis.io/api-openparlamento/v1/19/?format=api), here are the necessary endpoints to refresh your data:

## Primary Endpoints (Currently Used)

### 1. **Persons** - For Person Model
- **List Endpoint**: `https://service.opdm.openpolis.io/api-openparlamento/v1/19/persons/`
  - Returns paginated list of all persons
  - Each result has a `url` field pointing to detailed person data
  - Supports pagination via `?page=N` and `next` field in response
  
- **Detail Endpoint**: Individual person URLs from the list
  - Format: `https://service.opdm.openpolis.io/api-openparlamento/v1/19/persons/{id}/`
  - Contains full person details: name, party, roles, voting history, etc.

**Current Usage**: Your system fetches:
1. List all persons (paginated)
2. For each person, fetch detailed data from their `url`

## Additional Endpoints (Potential Future Use)

### 2. **Parliamentary Assemblies** - For Session Data
- **Camera Assemblies**: `https://service.opdm.openpolis.io/api-openparlamento/v1/19/parl_assemblies/camera/`
- **Senato Assemblies**: `https://service.opdm.openpolis.io/api-openparlamento/v1/19/parl_assemblies/senato/`
- **Bicameral Assemblies**: `https://service.opdm.openpolis.io/api-openparlamento/v1/19/parl_assemblies/bichambers/`

**Potential Use**: Could supplement or replace WebTV session data

### 3. **Memberships** - For Role/Party Information
- **Endpoint**: `https://service.opdm.openpolis.io/api-openparlamento/v1/19/memberships/`
- **Use**: Track party memberships, role changes over time

### 4. **Votings** - For Voting Records
- **Endpoint**: `https://service.opdm.openpolis.io/api-openparlamento/v1/19/votings/`
- **Use**: Voting history, which could link to speeches/topics

### 5. **Groups Votes** - For Party Voting Patterns
- **Endpoint**: `https://service.opdm.openpolis.io/api-openparlamento/v1/19/groups_votes/`
- **Use**: How parties voted on different issues

## Current Data Flow

```
1. GET /api-openparlamento/v1/19/persons/?page=1
   ↓
2. For each person in results:
   GET {person.url}  (individual detail)
   ↓
3. Process and store in database
```

## Endpoints Summary Table

| Endpoint | Purpose | Used For | Priority |
|----------|---------|----------|----------|
| `persons/` | List all persons | Person model | ✅ **Required** |
| `persons/{id}/` | Person details | Person model | ✅ **Required** |
| `parl_assemblies/camera/` | Camera sessions | Session model (future) | ⚠️ Optional |
| `parl_assemblies/senato/` | Senato sessions | Session model (future) | ⚠️ Optional |
| `memberships/` | Role/party memberships | Person roles | ⚠️ Optional |
| `votings/` | Voting records | Analysis | ⚠️ Optional |
| `groups_votes/` | Party voting patterns | Analysis | ⚠️ Optional |

## Implementation Notes

### For Person Data Refresh:
1. **Start with**: `GET /api-openparlamento/v1/19/persons/?page=1`
2. **Paginate**: Follow `next` URL until `next` is `null`
3. **Fetch details**: For each person, GET their `url` field
4. **Rate limiting**: Add delays (3-5 seconds) between requests
5. **Update logic**: Check if person exists, update if changed

### API Response Format:
```json
{
  "count": 1000,
  "next": "https://...?page=2",
  "previous": null,
  "results": [
    {
      "id": 123,
      "url": "https://.../persons/123/",
      "family_name": "Rossi",
      "given_name": "Mario",
      ...
    }
  ]
}
```

## Rate Limiting Considerations

The API appears to be public but you should:
- Add delays between requests (3-5 seconds)
- Handle rate limit errors (429 status)
- Implement retry logic with exponential backoff
- Consider caching to avoid unnecessary requests

## Next Steps

To implement automatic data refresh, you would need to:

1. **Create a fetcher module** that:
   - Fetches from `persons/` endpoint with pagination
   - Fetches individual person details
   - Handles errors and rate limiting

2. **Update the processor** to:
   - Accept data from API (not just files)
   - Compare timestamps/versions to detect changes
   - Update existing records when data changes

3. **Add scheduling** (optional):
   - Run refresh daily/weekly
   - Track last update time
   - Only fetch changed records if API supports it

