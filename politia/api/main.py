"""
FastAPI application for Politia API
"""
from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import date

from politia.config import settings
from politia.models import get_db, Person, Session as SessionModel, Topic, SpeechSegment
from politia.api.schemas import (
    PersonResponse,
    SessionResponse,
    TopicResponse,
    SpeechSegmentResponse,
    PaginatedResponse,
)

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="API for accessing structured parliamentary data",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


# Person endpoints
@app.get("/persons", response_model=PaginatedResponse[PersonResponse])
async def get_persons(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    party: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get list of persons with pagination"""
    query = db.query(Person)
    
    if party:
        query = query.filter(Person.party == party)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Person.full_name.ilike(search_term)) |
            (Person.family_name.ilike(search_term)) |
            (Person.given_name.ilike(search_term))
        )
    
    total = query.count()
    persons = query.offset(skip).limit(limit).all()
    
    return PaginatedResponse(
        items=[PersonResponse.model_validate(p) for p in persons],
        total=total,
        skip=skip,
        limit=limit,
    )


@app.get("/persons/{person_id}", response_model=PersonResponse)
async def get_person(person_id: str, db: Session = Depends(get_db)):
    """Get a specific person by ID"""
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return PersonResponse.model_validate(person)


@app.get("/persons/{person_id}/speeches", response_model=PaginatedResponse[SpeechSegmentResponse])
async def get_person_speeches(
    person_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get all speeches by a specific person"""
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    query = db.query(SpeechSegment).filter(SpeechSegment.speaker_id == person_id)
    total = query.count()
    speeches = query.order_by(SpeechSegment.date.desc()).offset(skip).limit(limit).all()
    
    return PaginatedResponse(
        items=[SpeechSegmentResponse.model_validate(s) for s in speeches],
        total=total,
        skip=skip,
        limit=limit,
    )


# Session endpoints
@app.get("/sessions", response_model=PaginatedResponse[SessionResponse])
async def get_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    chamber: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Get list of sessions with pagination"""
    query = db.query(SessionModel)
    
    if chamber:
        query = query.filter(SessionModel.chamber == chamber)
    
    if date_from:
        query = query.filter(SessionModel.date >= date_from)
    
    if date_to:
        query = query.filter(SessionModel.date <= date_to)
    
    total = query.count()
    sessions = query.order_by(SessionModel.date.desc()).offset(skip).limit(limit).all()
    
    return PaginatedResponse(
        items=[SessionResponse.model_validate(s) for s in sessions],
        total=total,
        skip=skip,
        limit=limit,
    )


@app.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: Session = Depends(get_db)):
    """Get a specific session by ID"""
    session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse.model_validate(session)


# Topic endpoints
@app.get("/topics", response_model=PaginatedResponse[TopicResponse])
async def get_topics(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    session_id: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get list of topics with pagination"""
    query = db.query(Topic)
    
    if session_id:
        query = query.filter(Topic.session_id == session_id)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(Topic.title.ilike(search_term))
    
    total = query.count()
    topics = query.offset(skip).limit(limit).all()
    
    return PaginatedResponse(
        items=[TopicResponse.model_validate(t) for t in topics],
        total=total,
        skip=skip,
        limit=limit,
    )


@app.get("/topics/{topic_id}", response_model=TopicResponse)
async def get_topic(topic_id: str, db: Session = Depends(get_db)):
    """Get a specific topic by ID"""
    topic = db.query(Topic).filter(Topic.topic_id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return TopicResponse.model_validate(topic)


# Speech segment endpoints
@app.get("/speeches", response_model=PaginatedResponse[SpeechSegmentResponse])
async def get_speeches(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    speaker_id: Optional[str] = None,
    session_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get list of speech segments with pagination and filtering"""
    query = db.query(SpeechSegment)
    
    if speaker_id:
        query = query.filter(SpeechSegment.speaker_id == speaker_id)
    
    if session_id:
        query = query.filter(SpeechSegment.session_id == session_id)
    
    if topic_id:
        query = query.filter(SpeechSegment.topic_id == topic_id)
    
    if date_from:
        query = query.filter(SpeechSegment.date >= date_from)
    
    if date_to:
        query = query.filter(SpeechSegment.date <= date_to)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(SpeechSegment.text.ilike(search_term))
    
    total = query.count()
    speeches = query.order_by(SpeechSegment.date.desc(), SpeechSegment.order_in_topic).offset(skip).limit(limit).all()
    
    return PaginatedResponse(
        items=[SpeechSegmentResponse.model_validate(s) for s in speeches],
        total=total,
        skip=skip,
        limit=limit,
    )


@app.get("/speeches/{speech_id}", response_model=SpeechSegmentResponse)
async def get_speech(speech_id: str, db: Session = Depends(get_db)):
    """Get a specific speech segment by ID"""
    speech = db.query(SpeechSegment).filter(SpeechSegment.speech_id == speech_id).first()
    if not speech:
        raise HTTPException(status_code=404, detail="Speech segment not found")
    return SpeechSegmentResponse.model_validate(speech)

