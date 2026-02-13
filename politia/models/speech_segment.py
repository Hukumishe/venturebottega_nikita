"""
SpeechSegment model - represents individual speech segments/interventions
"""
from sqlalchemy import Column, String, ForeignKey, Text, Date, Integer
from sqlalchemy.orm import relationship
from .database import Base


class SpeechSegment(Base):
    __tablename__ = "speech_segments"

    speech_id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.session_id"), nullable=False, index=True)
    topic_id = Column(String, ForeignKey("topics.topic_id"), nullable=True, index=True)
    speaker_id = Column(String, ForeignKey("persons.person_id"), nullable=True, index=True)
    
    text = Column(Text, nullable=False)
    date = Column(Date, nullable=False, index=True)
    
    # Source reference for traceability
    source_reference = Column(String)
    
    # Ordering within topic/session
    order_in_topic = Column(Integer)
    
    # Relationships
    session = relationship("Session", back_populates="speech_segments")
    topic = relationship("Topic", back_populates="speech_segments")
    speaker = relationship("Person", back_populates="speech_segments")

    def __repr__(self):
        return f"<SpeechSegment(speech_id={self.speech_id}, speaker_id={self.speaker_id}, text_length={len(self.text) if self.text else 0})>"


