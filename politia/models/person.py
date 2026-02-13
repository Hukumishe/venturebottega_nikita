"""
Person model - represents politicians/parliamentarians
"""
from sqlalchemy import Column, String, Integer, JSON, Text
from sqlalchemy.orm import relationship
from .database import Base


class Person(Base):
    __tablename__ = "persons"

    person_id = Column(String, primary_key=True, index=True)
    full_name = Column(String, nullable=False, index=True)
    family_name = Column(String, index=True)
    given_name = Column(String, index=True)
    party = Column(String, index=True)
    roles = Column(JSON)  # Store roles as JSON array
    source_ids = Column(JSON)  # Store source IDs (e.g., openparlamento IDs)
    
    # Additional metadata from OpenParlamento
    birth_date = Column(String)
    birth_place = Column(String)
    image_url = Column(String)
    slug = Column(String, index=True)
    
    # Raw data for reference
    raw_data = Column(JSON)  # Store full OpenParlamento JSON for future use
    
    # Relationships
    speech_segments = relationship("SpeechSegment", back_populates="speaker")

    def __repr__(self):
        return f"<Person(person_id={self.person_id}, full_name={self.full_name})>"

