"""
Session model - represents parliamentary sessions
"""
from sqlalchemy import Column, String, Date, Integer
from sqlalchemy.orm import relationship
from .database import Base


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    chamber = Column(String, nullable=False, index=True)  # "C" for Camera, "S" for Senato
    legislature = Column(Integer, index=True)
    session_number = Column(Integer, index=True)
    
    # Source reference
    source_reference = Column(String)  # Original file path or URL
    
    # Relationships
    topics = relationship("Topic", back_populates="session", cascade="all, delete-orphan")
    speech_segments = relationship("SpeechSegment", back_populates="session")

    def __repr__(self):
        return f"<Session(session_id={self.session_id}, date={self.date}, chamber={self.chamber})>"






