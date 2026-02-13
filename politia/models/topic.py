"""
Topic model - represents discussion topics within a session
"""
from sqlalchemy import Column, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base


class Topic(Base):
    __tablename__ = "topics"

    topic_id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.session_id"), nullable=False, index=True)
    title = Column(Text, nullable=False)
    
    # Relationships
    session = relationship("Session", back_populates="topics")
    speech_segments = relationship("SpeechSegment", back_populates="topic")

    def __repr__(self):
        return f"<Topic(topic_id={self.topic_id}, title={self.title[:50]}...)>"


