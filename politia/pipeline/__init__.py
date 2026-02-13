"""
Data pipeline for processing parliamentary data
"""
from .openparlamento_processor import OpenParlamentoProcessor
from .openparlamento_fetcher import OpenParlamentoFetcher
from .webtv_processor import WebTVProcessor
from .name_matcher import NameMatcher
from .pipeline import DataPipeline

__all__ = [
    "OpenParlamentoProcessor",
    "OpenParlamentoFetcher",
    "WebTVProcessor",
    "NameMatcher",
    "DataPipeline",
]


