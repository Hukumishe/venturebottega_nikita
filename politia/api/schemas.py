"""
Pydantic schemas for API responses
"""
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Generic, TypeVar
from datetime import date

T = TypeVar('T')


class PersonResponse(BaseModel):
    """Person response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    person_id: str
    full_name: str
    family_name: Optional[str] = None
    given_name: Optional[str] = None
    party: Optional[str] = None
    roles: Optional[List[dict]] = None
    source_ids: Optional[dict] = None
    birth_date: Optional[str] = None
    birth_place: Optional[str] = None
    image_url: Optional[str] = None
    slug: Optional[str] = None


class SessionResponse(BaseModel):
    """Session response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    session_id: str
    date: date
    chamber: str
    legislature: Optional[int] = None
    session_number: Optional[int] = None
    source_reference: Optional[str] = None


class TopicResponse(BaseModel):
    """Topic response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    topic_id: str
    session_id: str
    title: str


class SpeechSegmentResponse(BaseModel):
    """Speech segment response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    speech_id: str
    session_id: str
    topic_id: Optional[str] = None
    speaker_id: Optional[str] = None
    text: str
    date: date
    source_reference: Optional[str] = None
    order_in_topic: Optional[int] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper"""
    items: List[T]
    total: int
    skip: int
    limit: int

