import re
import json
import hashlib
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from engine.core.config import settings
from engine.core.db import Person, ParliamentarySession, Topic, SpeechSegment

PARTY_FROM_TEXT_RE = re.compile(r'^[A-Z][A-Z .]+\(([A-Z0-9-]+)\)\.')
PRESIDENTE_RE = re.compile(r'^PRESIDENTE\b', re.IGNORECASE)


def extract_party_from_text(text: str) -> Optional[str]:
    match = PARTY_FROM_TEXT_RE.match(text)
    return match.group(1) if match else None


def extract_display_name(text: str) -> Optional[str]:
    match = re.match(r'^([A-Z][A-Z .]+?)[\(,.]', text)
    if match:
        return match.group(1).strip().title()
    return None


def is_president_speech(text: str) -> bool:
    return bool(PRESIDENTE_RE.match(text))


class NameMatcher:
    TITLES = ['PRESIDENTE', 'ON', 'ONOREVOLE', 'SENATORE', 'DEPUTATO', 'MINISTRO', 'MINISTRA']

    def __init__(self, db: Session):
        self.db = db
        self._person_cache = {}
        self._load_person_cache()

    def _load_person_cache(self):
        persons = self.db.query(Person).all()
        for person in persons:
            if person.family_name and person.given_name:
                key1 = self._normalize_name(f"{person.family_name} {person.given_name}")
                key2 = self._normalize_name(f"{person.given_name} {person.family_name}")
                self._person_cache[key1] = person
                self._person_cache[key2] = person
            if person.full_name:
                key = self._normalize_name(person.full_name)
                self._person_cache[key] = person

    def _normalize_name(self, name: str) -> str:
        if not name:
            return ""

        # NFD decompose then strip combining marks (accents)
        name = unicodedata.normalize('NFD', name)
        name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')

        name_upper = name.upper()
        for title in self.TITLES:
            name_upper = name_upper.replace(title, "")

        name_upper = re.sub(r'[^\w\s]', '', name_upper)
        name_upper = ' '.join(name_upper.split())

        return name_upper.strip()

    def match_speaker(self, speaker_name: str) -> Optional[Person]:
        if not speaker_name or speaker_name == "Unknown":
            return None

        normalized = self._normalize_name(speaker_name)

        if normalized in self._person_cache:
            return self._person_cache[normalized]

        parts = normalized.split()
        if len(parts) >= 2:
            reversed_name = ' '.join(reversed(parts))
            if reversed_name in self._person_cache:
                return self._person_cache[reversed_name]

        if len(parts) >= 2:
            surname_first = f"{parts[-1]} {' '.join(parts[:-1])}"
            if surname_first in self._person_cache:
                return self._person_cache[surname_first]

            given_first = f"{' '.join(parts[:-1])} {parts[-1]}"
            if given_first in self._person_cache:
                return self._person_cache[given_first]

        if len(parts) >= 2:
            surname = parts[-1]
            first_given = parts[0]
            candidates = []
            for key, person in self._person_cache.items():
                key_parts = key.split()
                if len(key_parts) >= 2:
                    if (key_parts[-1] == surname and key_parts[0] == first_given) or \
                       (key_parts[0] == surname and key_parts[-1] == first_given):
                        candidates.append(person)

            if len(candidates) == 1:
                return candidates[0]
            elif len(candidates) > 1:
                logger.warning(
                    f"Multiple matches for {speaker_name} (normalized: {normalized}). "
                    f"Using first match: {candidates[0].full_name}"
                )
                return candidates[0]

        if len(parts) >= 1:
            surname = parts[-1]
            candidates = []
            for key, person in self._person_cache.items():
                key_parts = key.split()
                if key_parts and key_parts[-1] == surname:
                    candidates.append(person)

            if len(candidates) == 1:
                logger.debug(
                    f"Matched {speaker_name} by surname only: {candidates[0].full_name}"
                )
                return candidates[0]
            elif len(candidates) > 1:
                logger.debug(
                    f"Multiple people with surname '{surname}' for speaker '{speaker_name}'. "
                    f"Candidates: {[c.full_name for c in candidates[:3]]}"
                )
                return None

        logger.debug(f"No match found for speaker: {speaker_name} (normalized: {normalized})")
        return None

    def get_or_create_unknown_speaker(self, speaker_name: str) -> Person:
        person_id = f"unknown_{self._normalize_name(speaker_name).replace(' ', '_')}"
        person = self.db.query(Person).filter(Person.person_id == person_id).first()

        if not person:
            person = Person(
                person_id=person_id,
                full_name=speaker_name,
                family_name=speaker_name.split()[-1] if speaker_name.split() else speaker_name,
                given_name=speaker_name.split()[0] if len(speaker_name.split()) > 1 else "",
            )
            self.db.add(person)
            self.db.flush()
            normalized = self._normalize_name(speaker_name)
            self._person_cache[normalized] = person

        return person


class WebTVProcessor:
    def __init__(self, db: Session, name_matcher: NameMatcher):
        self.db = db
        self.name_matcher = name_matcher
        self.data_path = Path(settings.WEBTV_DATA_PATH) if settings.WEBTV_DATA_PATH else None

    def process_all(self) -> int:
        if not self.data_path or not self.data_path.exists():
            logger.warning(f"WebTV data path not found: {self.data_path}")
            return 0

        count = 0
        json_files = list(self.data_path.glob("*.json"))
        logger.info(f"Found {len(json_files)} WebTV JSON files")

        for json_file in json_files:
            try:
                self.process_file(json_file)
                count += 1
                if count % 10 == 0:
                    logger.info(f"Processed {count}/{len(json_files)} files")
                    self.db.commit()
            except Exception as e:
                logger.error(f"Error processing {json_file}: {e}")
                self.db.rollback()
                continue

        self.db.commit()
        logger.info(f"Successfully processed {count} WebTV files")
        return count

    def process_file(self, file_path: Path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        session_key = file_path.stem
        legislature, session_number = session_key.split('__')

        session_id = f"session_{legislature}_{session_number}"
        session = self.db.query(ParliamentarySession).filter(
            ParliamentarySession.session_id == session_id
        ).first()

        if not session:
            session_date_str = data.get('date')
            if session_date_str:
                try:
                    session_date = datetime.strptime(session_date_str, "%Y-%m-%d").date()
                except Exception:
                    session_date = datetime.now().date()
            else:
                session_date = datetime.now().date()

            session = ParliamentarySession(
                session_id=session_id,
                date=session_date,
                chamber="C",
                legislature=int(legislature),
                session_number=int(session_number),
                source_reference=str(file_path),
            )
            self.db.add(session)
            self.db.flush()

        contents = data.get('contents', {})
        for topic_title, interventions in contents.items():
            if not topic_title or not interventions:
                continue

            topic_id = self._generate_topic_id(session_id, topic_title)
            topic = self.db.query(Topic).filter(Topic.topic_id == topic_id).first()

            if not topic:
                topic = Topic(
                    topic_id=topic_id,
                    session_id=session_id,
                    title=topic_title,
                )
                self.db.add(topic)
                self.db.flush()

            for idx, intervention in enumerate(interventions):
                if not isinstance(intervention, dict):
                    continue

                speaker_name = intervention.get('speaker', 'Unknown')
                text = intervention.get('text', '')

                if not text.strip():
                    continue

                speaker = self.name_matcher.match_speaker(speaker_name)
                if not speaker:
                    speaker = self.name_matcher.get_or_create_unknown_speaker(speaker_name)

                speech_id = self._generate_speech_id(topic_id, idx, text)

                existing = self.db.query(SpeechSegment).filter(SpeechSegment.speech_id == speech_id).first()
                if existing:
                    continue

                party = extract_party_from_text(text)
                if not party and speaker and speaker.party:
                    party = speaker.party

                display_name = extract_display_name(text)
                if not display_name and speaker:
                    display_name = speaker.full_name

                speech_segment = SpeechSegment(
                    speech_id=speech_id,
                    session_id=session_id,
                    topic_id=topic_id,
                    speaker_id=speaker.person_id,
                    text=text,
                    date=session.date,
                    source_reference=str(file_path),
                    order_in_topic=idx,
                    party=party,
                    speaker_display_name=display_name,
                )
                self.db.add(speech_segment)

    def _generate_topic_id(self, session_id: str, title: str) -> str:
        title_hash = hashlib.md5(title.encode('utf-8')).hexdigest()[:8]
        return f"{session_id}_topic_{title_hash}"

    def _generate_speech_id(self, topic_id: str, index: int, text: str) -> str:
        text_hash = hashlib.md5(f"{topic_id}_{index}_{text[:100]}".encode('utf-8')).hexdigest()[:12]
        return f"{topic_id}_speech_{text_hash}"

    def enrich_from_archive(self):
        """Load webtv_archive.json and set session title/event_id."""
        archive_path = Path(settings.RAW_DATA_PATH) / "webtv_archive" / "webtv_archive.json"
        if not archive_path.exists():
            logger.warning(f"Archive not found at {archive_path}")
            return

        with open(archive_path, "r", encoding="utf-8") as f:
            archive = json.load(f)

        session_map = {}
        for item in archive:
            sn = item.get("session_number")
            if sn is not None:
                session_map[int(sn)] = item

        sessions = self.db.query(ParliamentarySession).all()
        updated = 0
        for session in sessions:
            if session.session_number and session.session_number in session_map:
                entry = session_map[session.session_number]
                if not session.webtv_event_id:
                    session.webtv_event_id = entry.get("event_id")
                if not session.title:
                    session.title = entry.get("title")
                updated += 1

        self.db.commit()
        logger.info(f"Enriched {updated} sessions with archive metadata")

    def enrich_video_urls(self):
        """Match interventions from event JSON files to speech segments by speaker name."""
        archive_dir = Path(settings.RAW_DATA_PATH) / "webtv_archive"
        if not archive_dir.exists():
            return

        sessions = (
            self.db.query(ParliamentarySession)
            .filter(ParliamentarySession.webtv_event_id.isnot(None))
            .all()
        )

        updated = 0
        for session in sessions:
            event_file = archive_dir / f"event_{session.webtv_event_id}.json"
            if not event_file.exists():
                continue

            with open(event_file, "r", encoding="utf-8") as f:
                interventions = json.load(f)

            speaker_map = {}
            for interv in interventions:
                speaker = interv.get("speaker", "").upper().strip()
                if speaker not in speaker_map:
                    speaker_map[speaker] = []
                speaker_map[speaker].append(interv)

            speeches = (
                self.db.query(SpeechSegment)
                .filter(SpeechSegment.session_id == session.session_id)
                .filter(SpeechSegment.video_url.is_(None))
                .order_by(SpeechSegment.order_in_topic)
                .all()
            )

            speaker_counters = {}
            for speech in speeches:
                if not speech.speaker_display_name:
                    continue

                name_upper = speech.speaker_display_name.upper().strip()

                matched_key = None
                for key in speaker_map:
                    if name_upper in key or key in name_upper:
                        matched_key = key
                        break

                if not matched_key:
                    name_parts = name_upper.split()
                    if len(name_parts) >= 1:
                        surname = name_parts[-1] if len(name_parts) > 1 else name_parts[0]
                        for key in speaker_map:
                            if surname in key:
                                matched_key = key
                                break

                if matched_key and speaker_map[matched_key]:
                    idx = speaker_counters.get(matched_key, 0)
                    if idx < len(speaker_map[matched_key]):
                        interv = speaker_map[matched_key][idx]
                        speech.video_url = interv.get("embedded_url")
                        speech.intervention_id = str(interv.get("intervention_id", ""))
                        speaker_counters[matched_key] = idx + 1
                        updated += 1

        self.db.commit()
        logger.info(f"Enriched {updated} speeches with video URLs")
