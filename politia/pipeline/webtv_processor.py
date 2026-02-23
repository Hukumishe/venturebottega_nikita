"""
Processor for WebTV (parliamentary transcript) data
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger
from sqlalchemy.orm import Session
import hashlib

from politia.models import Session as SessionModel, Topic, SpeechSegment
from politia.pipeline.name_matcher import NameMatcher
from politia.config import settings


class WebTVProcessor:
    """Processes WebTV JSON files and loads them into the database"""
    
    def __init__(self, db: Session, name_matcher: NameMatcher):
        self.db = db
        self.name_matcher = name_matcher
        self.data_path = Path(settings.WEBTV_DATA_PATH) if settings.WEBTV_DATA_PATH else None
    
    def process_all(self) -> int:
        """
        Process all WebTV JSON files
        
        Returns:
            Number of sessions processed
        """
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
        """
        Process a single WebTV JSON file
        
        Args:
            file_path: Path to the JSON file (e.g., "19__347.json")
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract session ID from filename (e.g., "19__347.json" -> "19__347")
        session_key = file_path.stem
        legislature, session_number = session_key.split('__')
        
        # Create or get session
        session_id = f"session_{legislature}_{session_number}"
        session = self.db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
        
        if not session:
            # Parse date from session (we'll use a default if not available)
            # In real implementation, you might extract this from the XML
            session_date = datetime.now().date()  # Placeholder
            
            session = SessionModel(
                session_id=session_id,
                date=session_date,
                chamber="C",  # Camera
                legislature=int(legislature),
                session_number=int(session_number),
                source_reference=str(file_path),
            )
            self.db.add(session)
            self.db.flush()
        
        # Process topics (dibattiti)
        contents = data.get('contents', {})
        for topic_title, interventions in contents.items():
            if not topic_title or not interventions:
                continue
            
            # Create or get topic
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
            
            # Process interventions (speech segments)
            for idx, intervention in enumerate(interventions):
                if not isinstance(intervention, dict):
                    continue
                
                speaker_name = intervention.get('speaker', 'Unknown')
                text = intervention.get('text', '')
                
                if not text.strip():
                    continue
                
                # Match speaker to Person
                speaker = self.name_matcher.match_speaker(speaker_name)
                if not speaker:
                    # Create unknown speaker record
                    speaker = self.name_matcher.get_or_create_unknown_speaker(speaker_name)
                
                # Create speech segment
                speech_id = self._generate_speech_id(topic_id, idx, text)
                
                # Check if already exists
                existing = self.db.query(SpeechSegment).filter(SpeechSegment.speech_id == speech_id).first()
                if existing:
                    continue
                
                speech_segment = SpeechSegment(
                    speech_id=speech_id,
                    session_id=session_id,
                    topic_id=topic_id,
                    speaker_id=speaker.person_id,
                    text=text,
                    date=session.date,
                    source_reference=str(file_path),
                    order_in_topic=idx,
                )
                self.db.add(speech_segment)
    
    def _generate_topic_id(self, session_id: str, title: str) -> str:
        """Generate a unique topic ID"""
        # Use hash of title for uniqueness
        title_hash = hashlib.md5(title.encode('utf-8')).hexdigest()[:8]
        return f"{session_id}_topic_{title_hash}"
    
    def _generate_speech_id(self, topic_id: str, index: int, text: str) -> str:
        """Generate a unique speech segment ID"""
        # Use hash of text + index for uniqueness
        text_hash = hashlib.md5(f"{topic_id}_{index}_{text[:100]}".encode('utf-8')).hexdigest()[:12]
        return f"{topic_id}_speech_{text_hash}"






