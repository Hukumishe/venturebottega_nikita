from pathlib import Path
from typing import Generator

from sqlalchemy import Column, String, Integer, JSON, Text, Date, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

from engine.core.config import settings

# --- SQLAlchemy setup ---

db_path = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
if db_path.parent != Path("."):
    db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at {settings.DATABASE_URL}")


# --- Models ---

class Person(Base):
    __tablename__ = "persons"

    person_id = Column(String, primary_key=True, index=True)
    full_name = Column(String, nullable=False, index=True)
    family_name = Column(String, index=True)
    given_name = Column(String, index=True)
    party = Column(String, index=True)
    roles = Column(JSON)
    source_ids = Column(JSON)
    birth_date = Column(String)
    birth_place = Column(String)
    image_url = Column(String)
    slug = Column(String, index=True)
    raw_data = Column(JSON)

    speech_segments = relationship("SpeechSegment", back_populates="speaker")

    def __repr__(self):
        return f"<Person(person_id={self.person_id}, full_name={self.full_name})>"


class ParliamentarySession(Base):
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    chamber = Column(String, nullable=False, index=True)
    legislature = Column(Integer, index=True)
    session_number = Column(Integer, index=True)
    source_reference = Column(String)
    webtv_event_id = Column(Integer, index=True)
    title = Column(String)

    topics = relationship("Topic", back_populates="session", cascade="all, delete-orphan")
    speech_segments = relationship("SpeechSegment", back_populates="session")

    def __repr__(self):
        return f"<ParliamentarySession(session_id={self.session_id}, date={self.date}, chamber={self.chamber})>"


class Topic(Base):
    __tablename__ = "topics"

    topic_id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.session_id"), nullable=False, index=True)
    title = Column(Text, nullable=False)

    session = relationship("ParliamentarySession", back_populates="topics")
    speech_segments = relationship("SpeechSegment", back_populates="topic")

    def __repr__(self):
        return f"<Topic(topic_id={self.topic_id}, title={self.title[:50]}...)>"


class SpeechSegment(Base):
    __tablename__ = "speech_segments"

    speech_id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.session_id"), nullable=False, index=True)
    topic_id = Column(String, ForeignKey("topics.topic_id"), nullable=True, index=True)
    speaker_id = Column(String, ForeignKey("persons.person_id"), nullable=True, index=True)
    text = Column(Text, nullable=False)
    date = Column(Date, nullable=False, index=True)
    source_reference = Column(String)
    order_in_topic = Column(Integer)
    party = Column(String, index=True)
    speaker_display_name = Column(String)
    video_url = Column(String)
    intervention_id = Column(String)

    session = relationship("ParliamentarySession", back_populates="speech_segments")
    topic = relationship("Topic", back_populates="speech_segments")
    speaker = relationship("Person", back_populates="speech_segments")

    def __repr__(self):
        return f"<SpeechSegment(speech_id={self.speech_id}, speaker_id={self.speaker_id}, text_length={len(self.text) if self.text else 0})>"
