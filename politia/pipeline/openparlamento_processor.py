"""
Processor for OpenParlamento data
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
from sqlalchemy.orm import Session

from politia.models import Person
from politia.config import settings


class OpenParlamentoProcessor:
    """Processes OpenParlamento JSON files and loads them into the database"""
    
    def __init__(self, db: Session):
        self.db = db
        self.data_path = Path(settings.OPENPARLAMENTO_DATA_PATH) if settings.OPENPARLAMENTO_DATA_PATH else None
        
    def process_all(self) -> int:
        """
        Process all OpenParlamento JSON files
        
        Returns:
            Number of persons processed
        """
        if not self.data_path or not self.data_path.exists():
            logger.warning(f"OpenParlamento data path not found: {self.data_path}")
            return 0
        
        count = 0
        json_files = list(self.data_path.glob("*.json"))
        logger.info(f"Found {len(json_files)} OpenParlamento JSON files")
        
        for json_file in json_files:
            try:
                self.process_file(json_file)
                count += 1
                if count % 50 == 0:
                    logger.info(f"Processed {count}/{len(json_files)} files")
                    self.db.commit()
            except Exception as e:
                logger.error(f"Error processing {json_file}: {e}")
                self.db.rollback()
                continue
        
        self.db.commit()
        logger.info(f"Successfully processed {count} OpenParlamento files")
        return count
    
    def process_file(self, file_path: Path):
        """
        Process a single OpenParlamento JSON file
        
        Args:
            file_path: Path to the JSON file
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract person information
        person_id = f"op_{data.get('id', 'unknown')}"
        
        # Check if person already exists
        existing = self.db.query(Person).filter(Person.person_id == person_id).first()
        if existing:
            # Update existing record
            self._update_person(existing, data)
        else:
            # Create new record
            person = self._create_person(person_id, data)
            self.db.add(person)
    
    def _create_person(self, person_id: str, data: Dict) -> Person:
        """Create a Person object from OpenParlamento data"""
        family_name = data.get('family_name', '')
        given_name = data.get('given_name', '')
        full_name = f"{family_name} {given_name}".strip()
        
        # Extract party from current_roles
        party = None
        roles = []
        if 'current_roles' in data and data['current_roles']:
            parl_role = data['current_roles'].get('parl', {})
            if parl_role:
                latest_group = parl_role.get('latest_group', {})
                party = latest_group.get('acronym') or latest_group.get('name')
                roles.append({
                    'role': parl_role.get('role'),
                    'start_date': parl_role.get('start_date'),
                    'end_date': parl_role.get('end_date'),
                    'party': party,
                })
        
        # Extract source IDs
        source_ids = {
            'openparlamento': f"p{data.get('id', '')}",
            'slug': data.get('slug'),
        }
        
        return Person(
            person_id=person_id,
            full_name=full_name,
            family_name=family_name,
            given_name=given_name,
            party=party,
            roles=roles,
            source_ids=source_ids,
            birth_date=data.get('birth_date'),
            birth_place=data.get('birth_place'),
            image_url=data.get('image'),
            slug=data.get('slug'),
            raw_data=data,  # Store full data for future use
        )
    
    def _update_person(self, person: Person, data: Dict):
        """Update an existing Person with new data"""
        # Update basic fields if missing
        if not person.family_name:
            person.family_name = data.get('family_name', '')
        if not person.given_name:
            person.given_name = data.get('given_name', '')
        if not person.full_name:
            person.full_name = f"{person.family_name} {person.given_name}".strip()
        
        # Update party if available
        if 'current_roles' in data and data['current_roles']:
            parl_role = data['current_roles'].get('parl', {})
            if parl_role:
                latest_group = parl_role.get('latest_group', {})
                party = latest_group.get('acronym') or latest_group.get('name')
                if party:
                    person.party = party
        
        # Update source IDs
        if person.source_ids:
            person.source_ids['openparlamento'] = f"p{data.get('id', '')}"
        else:
            person.source_ids = {
                'openparlamento': f"p{data.get('id', '')}",
                'slug': data.get('slug'),
            }
        
        # Update raw data
        person.raw_data = data


