"""OpenSearch index management: create, delete, and alias handling for politia-docs."""

from loguru import logger

from engine.search.opensearch_client import get_opensearch_client

INDEX_NAME = "politia-docs-v1"
ALIAS_NAME = "politia-docs"

INDEX_SETTINGS = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "filter": {
                "italian_stop": {"type": "stop", "stopwords": "_italian_"},
                "italian_stemmer": {"type": "stemmer", "language": "light_italian"},
                "italian_elision": {
                    "type": "elision",
                    "articles": [
                        "c", "l", "all", "dall", "dell", "nell", "sull",
                        "coll", "pell", "gl", "agl", "dagl", "degl",
                        "negl", "sugl", "un", "m", "t", "s", "v", "d",
                    ],
                    "articles_case": True,
                },
            },
            "analyzer": {
                "italian_custom": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "italian_elision",
                        "lowercase",
                        "italian_stop",
                        "italian_stemmer",
                    ],
                },
            },
        },
    },
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "doc_type": {"type": "keyword"},
            "source": {"type": "keyword"},
            "body": {"type": "text", "analyzer": "italian_custom"},
            "title": {
                "type": "text",
                "analyzer": "italian_custom",
                "fields": {"raw": {"type": "keyword"}},
            },
            "speaker_id": {"type": "keyword"},
            "speaker_name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {"raw": {"type": "keyword"}},
            },
            "party": {"type": "keyword"},
            "date": {"type": "date", "format": "yyyy-MM-dd"},
            "legislature": {"type": "integer"},
            "chamber": {"type": "keyword"},
            "session_number": {"type": "integer"},
            "topic_title": {
                "type": "text",
                "analyzer": "italian_custom",
                "fields": {"raw": {"type": "keyword"}},
            },
            "order_in_topic": {"type": "integer"},
            "video_url": {"type": "keyword", "index": False},
            "intervention_id": {"type": "keyword"},
            "text_length": {"type": "integer"},
            "is_president_speech": {"type": "boolean"},
            "indexed_at": {"type": "date"},
        }
    },
}


def create_index() -> None:
    client = get_opensearch_client()

    if client.indices.exists(index=INDEX_NAME):
        logger.info(f"Index {INDEX_NAME} already exists, skipping creation")
        return

    client.indices.create(index=INDEX_NAME, body=INDEX_SETTINGS)
    logger.info(f"Created index {INDEX_NAME}")

    if not client.indices.exists_alias(name=ALIAS_NAME):
        client.indices.put_alias(index=INDEX_NAME, name=ALIAS_NAME)
        logger.info(f"Created alias {ALIAS_NAME} -> {INDEX_NAME}")


def delete_index() -> None:
    client = get_opensearch_client()

    if client.indices.exists_alias(name=ALIAS_NAME):
        client.indices.delete_alias(index="_all", name=ALIAS_NAME)
        logger.info(f"Deleted alias {ALIAS_NAME}")

    if client.indices.exists(index=INDEX_NAME):
        client.indices.delete(index=INDEX_NAME)
        logger.info(f"Deleted index {INDEX_NAME}")
    else:
        logger.info(f"Index {INDEX_NAME} does not exist")
