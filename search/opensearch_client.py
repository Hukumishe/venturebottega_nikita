"""OpenSearch connection wrapper."""

from opensearchpy import OpenSearch

from engine.core.config import settings


def get_opensearch_client() -> OpenSearch:
    return OpenSearch(
        hosts=[{"host": settings.OPENSEARCH_HOST, "port": settings.OPENSEARCH_PORT}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=30,
    )
