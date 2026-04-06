"""OpenSearch query builder and executor for speech search and aggregations."""

from __future__ import annotations

from loguru import logger

from engine.core.labels import resolve_party_for_search
from engine.search.opensearch_client import get_opensearch_client
from engine.search.opensearch_index import ALIAS_NAME


def _resolve_party(party: str | None) -> str | None:
    return resolve_party_for_search(party)


def build_search_query(
    q: str = "",
    party: str | None = None,
    speaker: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    exclude_president: bool = True,
    size: int = 20,
    offset: int = 0,
) -> dict:
    must = []
    filters = []
    must_not = []

    if q:
        must.append({
            "multi_match": {
                "query": q,
                "fields": ["body^1", "title^0.5", "topic_title^0.8", "speaker_name^0.3"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        })

    resolved_party = _resolve_party(party)
    if resolved_party:
        filters.append({"term": {"party": resolved_party}})

    if speaker:
        must.append({"match": {"speaker_name": speaker}})

    if date_from or date_to:
        date_range: dict = {}
        if date_from:
            date_range["gte"] = date_from
        if date_to:
            date_range["lte"] = date_to
        filters.append({"range": {"date": date_range}})

    if exclude_president:
        must_not.append({"term": {"is_president_speech": True}})

    body: dict = {
        "query": {
            "bool": {
                "must": must if must else [{"match_all": {}}],
                "filter": filters,
                "must_not": must_not,
            }
        },
        "sort": [
            {"_score": {"order": "desc"}},
            {"date": {"order": "desc"}},
            {"doc_id": {"order": "asc"}},
        ],
        "size": size,
        "from": offset,
        "_source": [
            "doc_id", "speaker_name", "speaker_id", "party", "date",
            "session_number", "topic_title", "body", "video_url",
            "text_length", "is_president_speech",
        ],
        "highlight": {
            "fields": {
                "body": {"fragment_size": 300, "number_of_fragments": 1},
            },
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
        },
    }

    return body


def execute_search(
    q: str = "",
    party: str | None = None,
    speaker: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    exclude_president: bool = True,
    size: int = 20,
    offset: int = 0,
) -> dict:
    client = get_opensearch_client()
    query = build_search_query(
        q=q,
        party=party,
        speaker=speaker,
        date_from=date_from,
        date_to=date_to,
        exclude_president=exclude_president,
        size=size,
        offset=offset,
    )

    response = client.search(index=ALIAS_NAME, body=query)
    return response


def build_aggregation_query(
    q: str = "",
    party: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    exclude_president: bool = True,
) -> dict:
    must = []
    filters = []
    must_not = []

    if q:
        must.append({
            "multi_match": {
                "query": q,
                "fields": ["body^1", "title^0.5", "topic_title^0.8"],
                "type": "best_fields",
            }
        })

    resolved_party = _resolve_party(party)
    if resolved_party:
        filters.append({"term": {"party": resolved_party}})

    if date_from or date_to:
        date_range: dict = {}
        if date_from:
            date_range["gte"] = date_from
        if date_to:
            date_range["lte"] = date_to
        filters.append({"range": {"date": date_range}})

    if exclude_president:
        must_not.append({"term": {"is_president_speech": True}})

    return {
        "query": {
            "bool": {
                "must": must if must else [{"match_all": {}}],
                "filter": filters,
                "must_not": must_not,
            }
        },
        "size": 0,
        "aggs": {
            "by_party": {
                "terms": {"field": "party", "size": 30},
            },
            "by_speaker": {
                "terms": {"field": "speaker_name.raw", "size": 30},
            },
            "by_topic": {
                "terms": {"field": "topic_title.raw", "size": 30},
            },
            "over_time": {
                "date_histogram": {
                    "field": "date",
                    "calendar_interval": "week",
                    "min_doc_count": 1,
                },
            },
        },
    }


def execute_aggregations(
    q: str = "",
    party: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    exclude_president: bool = True,
) -> dict:
    client = get_opensearch_client()
    query = build_aggregation_query(
        q=q,
        party=party,
        date_from=date_from,
        date_to=date_to,
        exclude_president=exclude_president,
    )

    response = client.search(index=ALIAS_NAME, body=query)
    return response
