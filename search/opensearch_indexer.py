"""Batch indexer: SQLite -> canonical OpenSearch documents -> bulk index."""

from datetime import datetime, timezone

from loguru import logger
from opensearchpy.helpers import bulk
from sqlalchemy.orm import Session

from engine.core.db import SpeechSegment, ParliamentarySession, Topic, Person
from engine.core.labels import normalize_party as _normalize_party
from engine.core.process import is_president_speech
from engine.search.opensearch_client import get_opensearch_client
from engine.search.opensearch_index import ALIAS_NAME


def _fix_utf8_title(title: str | None) -> str | None:
    if not title:
        return None
    try:
        return title.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return title


def _speech_to_doc(
    speech: SpeechSegment,
    session: ParliamentarySession | None,
    topic: Topic | None,
    speaker: Person | None,
    now_iso: str,
) -> dict:
    text = speech.text or ""
    president = is_president_speech(text)
    party = _normalize_party(speech.party)

    topic_title = None
    if topic and topic.title:
        topic_title = _fix_utf8_title(topic.title)

    session_title = None
    if session and session.title:
        session_title = _fix_utf8_title(session.title)

    return {
        "_index": ALIAS_NAME,
        "_id": speech.speech_id,
        "doc_id": speech.speech_id,
        "doc_type": "speech",
        "source": "camera",
        "body": text,
        "title": session_title,
        "speaker_id": speech.speaker_id,
        "speaker_name": speech.speaker_display_name or (speaker.full_name if speaker else None),
        "party": party,
        "date": speech.date.isoformat() if speech.date else None,
        "legislature": session.legislature if session else None,
        "chamber": session.chamber if session else None,
        "session_number": session.session_number if session else None,
        "topic_title": topic_title,
        "order_in_topic": speech.order_in_topic,
        "video_url": speech.video_url,
        "intervention_id": speech.intervention_id,
        "text_length": len(text),
        "is_president_speech": president,
        "indexed_at": now_iso,
    }


def reindex_all(db: Session) -> int:
    client = get_opensearch_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    speeches = (
        db.query(SpeechSegment)
        .join(ParliamentarySession, SpeechSegment.session_id == ParliamentarySession.session_id)
        .outerjoin(Topic, SpeechSegment.topic_id == Topic.topic_id)
        .outerjoin(Person, SpeechSegment.speaker_id == Person.person_id)
        .all()
    )

    logger.info(f"Indexing {len(speeches)} speeches...")

    actions = []
    for speech in speeches:
        session = speech.session
        topic = speech.topic
        speaker = speech.speaker
        actions.append(_speech_to_doc(speech, session, topic, speaker, now_iso))

    BATCH_SIZE = 500
    total_indexed = 0

    for i in range(0, len(actions), BATCH_SIZE):
        batch = actions[i : i + BATCH_SIZE]
        success, errors = bulk(client, batch, raise_on_error=False)
        total_indexed += success
        if errors:
            logger.warning(f"Batch {i // BATCH_SIZE + 1}: {len(errors)} errors")
        if (i // BATCH_SIZE + 1) % 10 == 0:
            logger.info(f"Indexed {total_indexed}/{len(actions)} documents")

    logger.info(f"Indexing complete: {total_indexed}/{len(actions)} documents indexed")
    return total_indexed
