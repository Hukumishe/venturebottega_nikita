"""Dagospia monitor data access and lightweight analytics."""

from __future__ import annotations

import json
import math
import re
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Protocol, Sequence
from urllib.parse import urlparse

from engine.core.config import settings

ITALIAN_MONTHS = {
    "gen": 1,
    "gennaio": 1,
    "feb": 2,
    "febbraio": 2,
    "mar": 3,
    "marzo": 3,
    "apr": 4,
    "aprile": 4,
    "mag": 5,
    "maggio": 5,
    "giu": 6,
    "giugno": 6,
    "lug": 7,
    "luglio": 7,
    "ago": 8,
    "agosto": 8,
    "set": 9,
    "settembre": 9,
    "ott": 10,
    "ottobre": 10,
    "nov": 11,
    "novembre": 11,
    "dic": 12,
    "dicembre": 12,
}

TIMESTAMP_PATTERN = re.compile(r"^\s*(\d{1,2})\s+([a-zA-Z.]+)\s+(\d{1,2}):(\d{2})\s*$")
KEYWORD_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9À-ÖØ-öø-ÿ]+")


@dataclass(frozen=True)
class DagospiaRecord:
    excerpt: str
    timestmp_raw: str
    parsed_at: datetime | None
    keywords: tuple[str, ...]
    detail: str
    source_category: str
    is_flash: bool


class DagospiaRepository(Protocol):
    def load_records(self) -> list[DagospiaRecord]:
        """Load raw records and return normalized entries."""


def parse_dagospia_timestamp(raw_timestamp: str, reference_year: int | None = None) -> datetime | None:
    timestamp = (raw_timestamp or "").strip().lower()
    if not timestamp or timestamp == "n/a":
        return None

    match = TIMESTAMP_PATTERN.match(timestamp)
    if not match:
        return None

    day = int(match.group(1))
    month_key = match.group(2).replace(".", "")
    hour = int(match.group(3))
    minute = int(match.group(4))
    month = ITALIAN_MONTHS.get(month_key)
    if month is None:
        return None

    year = reference_year or datetime.now().year
    try:
        return datetime(year=year, month=month, day=day, hour=hour, minute=minute)
    except ValueError:
        return None


def extract_keywords(raw_keywords: str) -> tuple[str, ...]:
    cleaned = (raw_keywords or "").strip().lower()
    if not cleaned or cleaned == "n/a":
        return tuple()
    tokens = KEYWORD_TOKEN_PATTERN.findall(cleaned)
    unique_tokens = []
    seen: set[str] = set()
    for token in tokens:
        normalized = token.strip().lower()
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_tokens.append(normalized)
    return tuple(unique_tokens)


def derive_source_category(detail_url: str) -> str:
    detail = (detail_url or "").strip()
    if not detail:
        return "unknown"
    path = urlparse(detail).path
    segments = [segment for segment in path.split("/") if segment]
    return segments[0].lower() if segments else "unknown"


def detect_flash(excerpt: str) -> bool:
    text = (excerpt or "").strip().upper()
    return text.startswith("FLASH") or text.startswith("ULTIM")


class FileDagospiaRepository:
    """Read Dagospia JSON files from the raw data folder."""

    COMPACTED_FILENAME = "dagospia_compacted.json"
    LATEST_FILENAME = "dagospia_latest.json"

    def __init__(self, data_file: Path | None = None, reference_year: int | None = None):
        self.data_file = data_file or self._default_data_file()
        self.reference_year = reference_year

    def _default_data_file(self) -> Path:
        root = Path(settings.DAGOSPIA_DATA_PATH)
        compacted = root / self.COMPACTED_FILENAME
        if compacted.exists():
            return compacted
        latest = root / self.LATEST_FILENAME
        if latest.exists():
            return latest
        return compacted

    def load_records(self) -> list[DagospiaRecord]:
        if not self.data_file.exists():
            raise FileNotFoundError(f"Dagospia data file not found: {self.data_file}")

        raw_data = json.loads(self.data_file.read_text(encoding="utf-8"))
        if not isinstance(raw_data, list):
            raise ValueError("Dagospia JSON must contain a list of records.")

        records: list[DagospiaRecord] = []
        for row in raw_data:
            if not isinstance(row, dict):
                continue
            excerpt = str(row.get("excerpt") or "").strip()
            timestmp_raw = str(row.get("timestmp") or "").strip()
            detail = str(row.get("detail") or "").strip()
            keywords = extract_keywords(str(row.get("keywords") or ""))
            parsed_at = parse_dagospia_timestamp(timestmp_raw, self.reference_year)
            records.append(
                DagospiaRecord(
                    excerpt=excerpt,
                    timestmp_raw=timestmp_raw,
                    parsed_at=parsed_at,
                    keywords=keywords,
                    detail=detail,
                    source_category=derive_source_category(detail),
                    is_flash=detect_flash(excerpt),
                )
            )
        return records


class TTLCache:
    def __init__(self, ttl_seconds: int = 60):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> object | None:
        cached = self._store.get(key)
        if cached is None:
            return None
        expires_at, value = cached
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: object) -> None:
        self._store[key] = (time.monotonic() + self.ttl_seconds, value)

    def clear(self) -> None:
        self._store.clear()


class DagospiaService:
    def __init__(
        self,
        repository: DagospiaRepository | None = None,
        cache_ttl_seconds: int = 60,
        now_provider: Callable[[], datetime] | None = None,
    ):
        self.repository = repository or FileDagospiaRepository()
        self.cache = TTLCache(ttl_seconds=cache_ttl_seconds)
        self.now_provider = now_provider or datetime.now

    def _load_records_cached(self) -> list[DagospiaRecord]:
        cache_key = "records"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        records = self.repository.load_records()
        self.cache.set(cache_key, records)
        return records

    def _normalize_keywords(self, selected_keywords: Sequence[str] | None) -> list[str]:
        if not selected_keywords:
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for keyword in selected_keywords:
            for token in extract_keywords(keyword):
                if token in seen:
                    continue
                seen.add(token)
                normalized.append(token)
        return normalized

    def _latest_reference_time(self, records: Sequence[DagospiaRecord]) -> datetime:
        parseable = [record.parsed_at for record in records if record.parsed_at is not None]
        return max(parseable) if parseable else self.now_provider()

    def _keyword_mentions(self, record: DagospiaRecord) -> set[str]:
        return set(record.keywords)

    def _build_category_distribution(self, records: Sequence[DagospiaRecord]) -> list[dict[str, object]]:
        counts = Counter(record.source_category or "unknown" for record in records)
        return [
            {"category": category, "count": count}
            for category, count in counts.most_common()
        ]

    def get_keywords(self, limit: int = 100) -> dict[str, object]:
        records = self._load_records_cached()
        counter: Counter[str] = Counter()
        for record in records:
            counter.update(self._keyword_mentions(record))
        return {
            "items": [{"keyword": keyword, "count": count} for keyword, count in counter.most_common(limit)],
            "total_distinct": len(counter),
        }

    def get_overview(self) -> dict[str, object]:
        records = self._load_records_cached()
        parseable_count = sum(1 for record in records if record.parsed_at is not None)
        flash_count = sum(1 for record in records if record.is_flash)
        latest_time = self._latest_reference_time(records) if records else None
        return {
            "total_records": len(records),
            "parseable_records": parseable_count,
            "flash_records": flash_count,
            "latest_timestamp": latest_time.isoformat() if latest_time else None,
            "source_distribution": self._build_category_distribution(records),
        }

    def _build_pulse(
        self,
        records: Sequence[DagospiaRecord],
        now: datetime,
        selected_keywords: Sequence[str],
        window_hours: int,
    ) -> list[dict[str, object]]:
        safe_window = max(1, min(window_hours, 72))
        window_start = now - timedelta(hours=safe_window)
        current_start = now - timedelta(hours=6)
        previous_start = now - timedelta(hours=12)
        oldest_needed = now - timedelta(hours=max(safe_window, 12))

        window_counts: Counter[str] = Counter()
        current_counts: Counter[str] = Counter()
        previous_counts: Counter[str] = Counter()

        bins = 8
        bin_size_hours = safe_window / bins
        sparkline_by_keyword: dict[str, list[int]] = defaultdict(lambda: [0 for _ in range(bins)])

        for record in records:
            if record.parsed_at is None:
                continue
            if record.parsed_at < oldest_needed:
                continue
            mentions = self._keyword_mentions(record)
            if not mentions:
                continue

            if record.parsed_at >= window_start:
                for mention in mentions:
                    window_counts[mention] += 1
                elapsed_hours = (record.parsed_at - window_start).total_seconds() / 3600
                index = int(elapsed_hours / bin_size_hours) if bin_size_hours else 0
                index = max(0, min(bins - 1, index))
                for mention in mentions:
                    sparkline_by_keyword[mention][index] += 1

            if record.parsed_at >= current_start:
                for mention in mentions:
                    current_counts[mention] += 1
            elif record.parsed_at >= previous_start:
                for mention in mentions:
                    previous_counts[mention] += 1

        if selected_keywords:
            candidates = list(selected_keywords)
        else:
            candidates = [keyword for keyword, _ in window_counts.most_common(20)]

        items: list[dict[str, object]] = []
        for keyword in candidates:
            current = current_counts.get(keyword, 0)
            previous = previous_counts.get(keyword, 0)
            mentions_window = window_counts.get(keyword, 0)
            if not selected_keywords and mentions_window == 0 and current == 0 and previous == 0:
                continue

            if previous == 0:
                pct_change = 100.0 if current > 0 else 0.0
                is_new = current > 0
            else:
                pct_change = ((current - previous) / previous) * 100
                is_new = False

            items.append(
                {
                    "keyword": keyword,
                    "mentions_window": mentions_window,
                    "current_6h": current,
                    "previous_6h": previous,
                    "pct_change": round(pct_change, 2),
                    "is_new": is_new,
                    "sparkline": sparkline_by_keyword.get(keyword, [0 for _ in range(bins)]),
                }
            )

        if selected_keywords:
            return items

        return sorted(
            items,
            key=lambda item: (
                int(item["current_6h"]),
                float(item["pct_change"]),
                int(item["mentions_window"]),
            ),
            reverse=True,
        )[:12]

    def _build_bursts(
        self,
        records: Sequence[DagospiaRecord],
        now: datetime,
        selected_keywords: Sequence[str],
    ) -> list[dict[str, object]]:
        lookback_hours = 7 * 24
        end_hour = now.replace(minute=0, second=0, microsecond=0)
        start_hour = end_hour - timedelta(hours=lookback_hours - 1)
        total_counts: Counter[str] = Counter()
        counts_by_keyword: dict[str, list[int]] = defaultdict(lambda: [0 for _ in range(lookback_hours)])

        for record in records:
            if record.parsed_at is None:
                continue
            record_hour = record.parsed_at.replace(minute=0, second=0, microsecond=0)
            if record_hour < start_hour or record_hour > end_hour:
                continue
            index = int((record_hour - start_hour).total_seconds() // 3600)
            mentions = self._keyword_mentions(record)
            for mention in mentions:
                counts_by_keyword[mention][index] += 1
                total_counts[mention] += 1

        if selected_keywords:
            candidates = list(selected_keywords)
        else:
            candidates = [keyword for keyword, _ in total_counts.most_common(50)]

        alerts: list[dict[str, object]] = []
        for keyword in candidates:
            series = counts_by_keyword.get(keyword)
            if not series or len(series) < 2:
                continue

            current_count = series[-1]
            baseline = series[:-1]
            baseline_mean = statistics.fmean(baseline) if baseline else 0.0
            baseline_std = statistics.pstdev(baseline) if len(baseline) > 1 else 0.0
            if baseline_std == 0:
                z_score = float(current_count - baseline_mean) if current_count > baseline_mean else 0.0
            else:
                z_score = (current_count - baseline_mean) / baseline_std

            is_burst = z_score >= 3.0 and current_count >= max(2, int(math.ceil(baseline_mean)))
            if not is_burst:
                continue

            if z_score >= 5:
                severity = "critical"
            elif z_score >= 4:
                severity = "high"
            else:
                severity = "medium"

            alerts.append(
                {
                    "keyword": keyword,
                    "current_count": current_count,
                    "baseline_mean": round(baseline_mean, 2),
                    "baseline_std": round(baseline_std, 2),
                    "z_score": round(z_score, 2),
                    "severity": severity,
                    "explanation": (
                        f"{current_count} mentions in the last hour vs baseline "
                        f"{baseline_mean:.2f} ({severity} burst)"
                    ),
                }
            )

        return sorted(
            alerts,
            key=lambda item: (float(item["z_score"]), int(item["current_count"])),
            reverse=True,
        )[:10]

    def _filter_records(self, records: Sequence[DagospiaRecord], selected_keywords: Sequence[str]) -> list[DagospiaRecord]:
        if not selected_keywords:
            return list(records)
        selected_set = set(selected_keywords)
        return [record for record in records if selected_set.intersection(record.keywords)]

    def _serialize_recent_item(self, record: DagospiaRecord, selected_set: set[str]) -> dict[str, object]:
        matched = sorted(selected_set.intersection(record.keywords)) if selected_set else []
        return {
            "excerpt": record.excerpt,
            "detail": record.detail,
            "timestmp_raw": record.timestmp_raw,
            "parsed_at": record.parsed_at.isoformat() if record.parsed_at else None,
            "keywords": list(record.keywords),
            "matched_keywords": matched,
            "source_category": record.source_category,
            "is_flash": record.is_flash,
        }

    def get_widgets(
        self,
        selected_keywords: Sequence[str] | None = None,
        window_hours: int = 24,
        recent_limit: int = 20,
    ) -> dict[str, object]:
        records = self._load_records_cached()
        normalized_keywords = self._normalize_keywords(selected_keywords)
        now = self._latest_reference_time(records)
        parseable_records = [record for record in records if record.parsed_at is not None]
        filtered_records = self._filter_records(records, normalized_keywords)

        sorted_recent_records = sorted(
            filtered_records,
            key=lambda record: record.parsed_at or datetime.min,
            reverse=True,
        )

        selected_set = set(normalized_keywords)
        return {
            "selected_keywords": normalized_keywords,
            "window_hours": max(1, min(window_hours, 72)),
            "generated_at": now.isoformat(),
            "counts": {
                "total_records": len(records),
                "filtered_records": len(filtered_records),
            },
            "pulse": self._build_pulse(
                records=parseable_records,
                now=now,
                selected_keywords=normalized_keywords,
                window_hours=window_hours,
            ),
            "bursts": self._build_bursts(
                records=parseable_records,
                now=now,
                selected_keywords=normalized_keywords,
            ),
            "source_stream": {
                "global_distribution": self._build_category_distribution(records),
                "filtered_distribution": self._build_category_distribution(filtered_records),
            },
            "recent_items": [
                self._serialize_recent_item(record, selected_set)
                for record in sorted_recent_records[: max(1, min(recent_limit, 100))]
            ],
        }
