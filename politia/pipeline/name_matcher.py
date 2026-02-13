"""
Name matching utility for linking speakers to Person records
"""
import re
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from loguru import logger

from politia.models import Person


class NameMatcher:
    """
    Matches speaker names from transcripts to Person records.
    Handles name normalization and fuzzy matching.
    """
    
    # Common titles to remove
    TITLES = ['PRESIDENTE', 'ON', 'ONOREVOLE', 'SENATORE', 'DEPUTATO', 'MINISTRO', 'MINISTRA']
    
    def __init__(self, db: Session):
        self.db = db
        self._person_cache = {}
        self._load_person_cache()
    
    def _load_person_cache(self):
        """Load all persons into cache for faster matching"""
        persons = self.db.query(Person).all()
        for person in persons:
            # Create normalized keys for matching
            if person.family_name and person.given_name:
                key1 = self._normalize_name(f"{person.family_name} {person.given_name}")
                key2 = self._normalize_name(f"{person.given_name} {person.family_name}")
                self._person_cache[key1] = person
                self._person_cache[key2] = person
            if person.full_name:
                key = self._normalize_name(person.full_name)
                self._person_cache[key] = person
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize a name for matching:
        - Remove titles
        - Convert to uppercase
        - Remove extra spaces
        - Remove special characters
        """
        if not name:
            return ""
        
        # Remove titles
        name_upper = name.upper()
        for title in self.TITLES:
            name_upper = name_upper.replace(title, "")
        
        # Remove special characters and extra spaces
        name_upper = re.sub(r'[^\w\s]', '', name_upper)
        name_upper = ' '.join(name_upper.split())
        
        return name_upper.strip()
    
    def match_speaker(self, speaker_name: str) -> Optional[Person]:
        """
        Match a speaker name to a Person record
        
        Args:
            speaker_name: Name from transcript (e.g., "COGNOME Nome" or "LI Silvana Andreina")
            
        Returns:
            Person object if match found, None otherwise
        """
        if not speaker_name or speaker_name == "Unknown":
            return None
        
        # Normalize the input name
        normalized = self._normalize_name(speaker_name)
        
        # Try exact match first
        if normalized in self._person_cache:
            return self._person_cache[normalized]
        
        # Try reverse order (Nome COGNOME vs COGNOME Nome)
        parts = normalized.split()
        if len(parts) >= 2:
            reversed_name = ' '.join(reversed(parts))
            if reversed_name in self._person_cache:
                return self._person_cache[reversed_name]
        
        # Try matching all parts in different orders (for multi-part names)
        # e.g., "LI Silvana Andreina" should match "SILVANA ANDREINA LI"
        if len(parts) >= 2:
            # Try: last word + rest (surname first format)
            surname_first = f"{parts[-1]} {' '.join(parts[:-1])}"
            if surname_first in self._person_cache:
                return self._person_cache[surname_first]
            
            # Try: rest + last word (given names first format)
            given_first = f"{' '.join(parts[:-1])} {parts[-1]}"
            if given_first in self._person_cache:
                return self._person_cache[given_first]
        
        # Try matching by surname + first given name (more specific than surname alone)
        if len(parts) >= 2:
            surname = parts[-1]
            first_given = parts[0]
            # Look for matches where surname and first given name both appear
            candidates = []
            for key, person in self._person_cache.items():
                key_parts = key.split()
                if len(key_parts) >= 2:
                    # Check if surname matches and first given name matches
                    if (key_parts[-1] == surname and key_parts[0] == first_given) or \
                       (key_parts[0] == surname and key_parts[-1] == first_given):
                        candidates.append(person)
            
            if len(candidates) == 1:
                return candidates[0]
            elif len(candidates) > 1:
                # Multiple candidates - log warning but return first
                logger.warning(
                    f"Multiple matches for {speaker_name} (normalized: {normalized}). "
                    f"Using first match: {candidates[0].full_name}"
                )
                return candidates[0]
        
        # Last resort: Try matching by surname only (but log as less reliable)
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
                # Multiple people with same surname - don't guess
                logger.debug(
                    f"Multiple people with surname '{surname}' for speaker '{speaker_name}'. "
                    f"Candidates: {[c.full_name for c in candidates[:3]]}"
                )
                return None
        
        logger.debug(f"No match found for speaker: {speaker_name} (normalized: {normalized})")
        return None
    
    def get_or_create_unknown_speaker(self, speaker_name: str) -> Person:
        """
        Get or create a Person record for an unmatched speaker
        
        Args:
            speaker_name: Original speaker name
            
        Returns:
            Person object
        """
        # Check if unknown speaker already exists
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
            # Add to cache
            normalized = self._normalize_name(speaker_name)
            self._person_cache[normalized] = person
        
        return person
    
    def get_unmatched_speakers_report(self) -> dict:
        """
        Generate a report of unmatched speakers for manual review
        
        Returns:
            Dictionary with unmatched speaker names and their normalized forms
        """
        # Query for all "unknown" persons
        unknown_persons = self.db.query(Person).filter(
            Person.person_id.like("unknown_%")
        ).all()
        
        report = {
            "total_unmatched": len(unknown_persons),
            "unmatched_speakers": []
        }
        
        for person in unknown_persons:
            report["unmatched_speakers"].append({
                "person_id": person.person_id,
                "full_name": person.full_name,
                "normalized": self._normalize_name(person.full_name),
                "family_name": person.family_name,
                "given_name": person.given_name,
            })
        
        return report

