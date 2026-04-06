"""Speeches service: filtered listings, widgets, and detail for parliamentary speeches."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Callable

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from engine.core.db import SpeechSegment, ParliamentarySession, Topic, Person, get_db
from engine.services.dagospia_monitor import TTLCache


def _opensearch_available() -> bool:
    try:
        from engine.search.opensearch_client import get_opensearch_client
        client = get_opensearch_client()
        return client.ping()
    except Exception as e:
        # OpenSearch failures are expected sometimes (service not running, network issues),
        # but we should not hide the reason completely.
        logger.warning(f"OpenSearch ping failed: {e}")
        return False


class SpeechesService:
    def __init__(self, cache_ttl_seconds: int = 120):
        self.cache = TTLCache(ttl_seconds=cache_ttl_seconds)
        self._os_available: bool | None = None

    def _use_opensearch(self) -> bool:
        if self._os_available is None:
            self._os_available = _opensearch_available()
            if self._os_available:
                logger.info("OpenSearch is available, using it for search")
            else:
                logger.info("OpenSearch not available, falling back to SQLite")
        return self._os_available

    def _get_db(self) -> Session:
        return next(get_db())

    def get_filters(self) -> dict:
        cached = self.cache.get("filters")
        if cached is not None:
            return cached

        db = self._get_db()
        try:
            rows = (
                db.query(SpeechSegment.party, func.count(SpeechSegment.speech_id))
                .filter(SpeechSegment.party.isnot(None))
                .filter(SpeechSegment.party != "")
                .filter(~SpeechSegment.text.like("PRESIDENTE.%"))
                .group_by(SpeechSegment.party)
                .order_by(func.count(SpeechSegment.speech_id).desc())
                .all()
            )

            parties = [
                {"value": party, "label": party, "count": count}
                for party, count in rows
            ]

            result = {"parties": parties}
            self.cache.set("filters", result)
            return result
        finally:
            db.close()

    def get_list(
        self,
        search: str = "",
        party: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        safe_limit = max(1, min(limit, 200))
        safe_offset = max(0, offset)

        if search and self._use_opensearch():
            return self._get_list_opensearch(
                search=search, party=party, date_from=date_from, date_to=date_to,
                limit=safe_limit, offset=safe_offset,
            )

        return self._get_list_sqlite(
            search=search, party=party, date_from=date_from, date_to=date_to,
            limit=safe_limit, offset=safe_offset,
        )

    def _get_list_opensearch(
        self,
        search: str,
        party: str | None,
        date_from: str | None,
        date_to: str | None,
        limit: int,
        offset: int,
    ) -> dict:
        from engine.search.opensearch_search import execute_search

        response = execute_search(
            q=search, party=party, date_from=date_from, date_to=date_to,
            size=limit, offset=offset,
        )

        total = response["hits"]["total"]["value"]
        page = (offset // limit) + 1
        page_count = max(1, ((total - 1) // limit) + 1) if total else 1

        items = []
        for hit in response["hits"]["hits"]:
            src = hit["_source"]
            highlight = hit.get("highlight", {})
            text_preview = ""
            if "body" in highlight:
                text_preview = highlight["body"][0]
            elif src.get("body"):
                text_preview = src["body"][:300]

            items.append({
                "speech_id": src.get("doc_id"),
                "speaker_display_name": src.get("speaker_name"),
                "speaker_id": src.get("speaker_id"),
                "party": src.get("party"),
                "date": src.get("date"),
                "session_number": src.get("session_number"),
                "topic": src.get("topic_title"),
                "text_preview": text_preview,
                "video_url": src.get("video_url"),
                "_score": hit.get("_score"),
            })

        return {
            "filters": {
                "search": search,
                "party": party,
                "date_from": date_from,
                "date_to": date_to,
            },
            "meta": {
                "total_records": total,
                "offset": offset,
                "limit": limit,
                "page": page,
                "page_count": page_count,
                "has_prev": offset > 0,
                "has_next": offset + limit < total,
                "search_engine": "opensearch",
            },
            "items": items,
        }

    def _get_list_sqlite(
        self,
        search: str,
        party: str | None,
        date_from: str | None,
        date_to: str | None,
        limit: int,
        offset: int,
    ) -> dict:
        db = self._get_db()
        try:
            query = (
                db.query(SpeechSegment)
                .join(ParliamentarySession, SpeechSegment.session_id == ParliamentarySession.session_id)
                .outerjoin(Topic, SpeechSegment.topic_id == Topic.topic_id)
                .filter(~SpeechSegment.text.like("PRESIDENTE.%"))
            )

            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    (SpeechSegment.text.ilike(search_pattern))
                    | (SpeechSegment.speaker_display_name.ilike(search_pattern))
                )

            if party:
                query = query.filter(SpeechSegment.party == party)

            if date_from:
                try:
                    d = date.fromisoformat(date_from)
                    query = query.filter(SpeechSegment.date >= d)
                except ValueError:
                    pass

            if date_to:
                try:
                    d = date.fromisoformat(date_to)
                    query = query.filter(SpeechSegment.date <= d)
                except ValueError:
                    pass

            total = query.count()

            speeches = (
                query.order_by(SpeechSegment.date.desc(), SpeechSegment.speech_id)
                .offset(offset)
                .limit(limit)
                .all()
            )

            page = (offset // limit) + 1
            page_count = max(1, ((total - 1) // limit) + 1) if total else 1

            items = []
            for s in speeches:
                topic_title = None
                if s.topic:
                    topic_title = s.topic.title

                text_preview = s.text[:300] if s.text else ""

                items.append({
                    "speech_id": s.speech_id,
                    "speaker_display_name": s.speaker_display_name,
                    "speaker_id": s.speaker_id,
                    "party": s.party,
                    "date": s.date.isoformat() if s.date else None,
                    "session_number": s.session.session_number if s.session else None,
                    "topic": topic_title,
                    "text_preview": text_preview,
                    "video_url": s.video_url,
                })

            return {
                "filters": {
                    "search": search,
                    "party": party,
                    "date_from": date_from,
                    "date_to": date_to,
                },
                "meta": {
                    "total_records": total,
                    "offset": offset,
                    "limit": limit,
                    "page": page,
                    "page_count": page_count,
                    "has_prev": offset > 0,
                    "has_next": offset + limit < total,
                    "search_engine": "sqlite",
                },
                "items": items,
            }
        finally:
            db.close()

    def get_widgets(
        self,
        search: str = "",
        party: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict:
        cached_key = f"widgets_{search}_{party}_{date_from}_{date_to}"
        cached = self.cache.get(cached_key)
        if cached is not None:
            return cached

        if self._use_opensearch():
            result = self._get_widgets_opensearch(
                search=search, party=party, date_from=date_from, date_to=date_to,
            )
        else:
            result = self._get_widgets_sqlite(
                search=search, party=party, date_from=date_from, date_to=date_to,
            )

        self.cache.set(cached_key, result)
        return result

    def _get_widgets_opensearch(
        self,
        search: str,
        party: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> dict:
        from engine.search.opensearch_search import execute_aggregations

        response = execute_aggregations(
            q=search, party=party, date_from=date_from, date_to=date_to,
        )

        total_speeches = response["hits"]["total"]["value"]
        aggs = response.get("aggregations", {})

        party_buckets = aggs.get("by_party", {}).get("buckets", [])
        speaker_buckets = aggs.get("by_speaker", {}).get("buckets", [])

        speeches_by_party = [
            {"party": b["key"], "count": b["doc_count"]}
            for b in party_buckets
        ]

        return {
            "counts": {
                "total_speeches": total_speeches,
                "unique_speakers": len(speaker_buckets),
                "unique_parties": len(party_buckets),
            },
            "speeches_by_party": speeches_by_party,
            "search_engine": "opensearch",
        }

    def _get_widgets_sqlite(
        self,
        search: str,
        party: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> dict:
        db = self._get_db()
        try:
            query = (
                db.query(SpeechSegment)
                .filter(~SpeechSegment.text.like("PRESIDENTE.%"))
            )

            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    (SpeechSegment.text.ilike(search_pattern))
                    | (SpeechSegment.speaker_display_name.ilike(search_pattern))
                )
            if party:
                query = query.filter(SpeechSegment.party == party)
            if date_from:
                try:
                    query = query.filter(SpeechSegment.date >= date.fromisoformat(date_from))
                except ValueError:
                    pass
            if date_to:
                try:
                    query = query.filter(SpeechSegment.date <= date.fromisoformat(date_to))
                except ValueError:
                    pass

            total_speeches = query.count()

            unique_speakers = (
                query.with_entities(SpeechSegment.speaker_id)
                .distinct()
                .count()
            )

            unique_parties = (
                query.with_entities(SpeechSegment.party)
                .filter(SpeechSegment.party.isnot(None))
                .distinct()
                .count()
            )

            party_counts = (
                db.query(SpeechSegment.party, func.count(SpeechSegment.speech_id))
                .filter(~SpeechSegment.text.like("PRESIDENTE.%"))
                .filter(SpeechSegment.party.isnot(None))
                .filter(SpeechSegment.party != "")
            )
            if search:
                party_counts = party_counts.filter(
                    (SpeechSegment.text.ilike(f"%{search}%"))
                    | (SpeechSegment.speaker_display_name.ilike(f"%{search}%"))
                )
            if party:
                party_counts = party_counts.filter(SpeechSegment.party == party)
            if date_from:
                try:
                    party_counts = party_counts.filter(SpeechSegment.date >= date.fromisoformat(date_from))
                except ValueError:
                    pass
            if date_to:
                try:
                    party_counts = party_counts.filter(SpeechSegment.date <= date.fromisoformat(date_to))
                except ValueError:
                    pass

            party_rows = (
                party_counts
                .group_by(SpeechSegment.party)
                .order_by(func.count(SpeechSegment.speech_id).desc())
                .all()
            )

            speeches_by_party = [
                {"party": p, "count": c} for p, c in party_rows
            ]

            return {
                "counts": {
                    "total_speeches": total_speeches,
                    "unique_speakers": unique_speakers,
                    "unique_parties": unique_parties,
                },
                "speeches_by_party": speeches_by_party,
                "search_engine": "sqlite",
            }
        finally:
            db.close()

    def get_detail(self, speech_id: str) -> dict:
        db = self._get_db()
        try:
            speech = (
                db.query(SpeechSegment)
                .filter(SpeechSegment.speech_id == speech_id)
                .first()
            )

            if not speech:
                raise KeyError(f"Speech not found: {speech_id}")

            topic_title = None
            if speech.topic:
                topic_title = speech.topic.title

            session_info = None
            if speech.session:
                session_info = {
                    "session_id": speech.session.session_id,
                    "session_number": speech.session.session_number,
                    "date": speech.session.date.isoformat() if speech.session.date else None,
                    "title": speech.session.title,
                }

            speaker_info = None
            if speech.speaker:
                speaker_info = {
                    "person_id": speech.speaker.person_id,
                    "full_name": speech.speaker.full_name,
                    "party": speech.speaker.party,
                    "image_url": speech.speaker.image_url,
                    "slug": speech.speaker.slug,
                }

            return {
                "speech_id": speech.speech_id,
                "speaker_display_name": speech.speaker_display_name,
                "party": speech.party,
                "date": speech.date.isoformat() if speech.date else None,
                "text": speech.text,
                "video_url": speech.video_url,
                "intervention_id": speech.intervention_id,
                "topic": topic_title,
                "session": session_info,
                "speaker": speaker_info,
            }
        finally:
            db.close()
