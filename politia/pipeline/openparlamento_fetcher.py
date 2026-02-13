"""
Fetcher for OpenParlamento API data
Fetches fresh data directly from the API
"""
import requests
import json
from pathlib import Path
from time import sleep
from typing import List, Dict, Optional, Callable
from loguru import logger
from sqlalchemy.orm import Session

from politia.models import Person
from politia.config import settings


class OpenParlamentoFetcher:
    """
    Fetches data from OpenParlamento API
    Can fetch directly to database or save to JSON files
    """
    
    BASE_URL = "https://service.opdm.openpolis.io/api-openparlamento/v1/19"
    PERSONS_LIST_URL = f"{BASE_URL}/persons/"
    
    def __init__(
        self,
        db: Optional[Session] = None,
        save_to_files: bool = False,
        output_path: Optional[Path] = None,
        rate_limit_delay: float = 3.0,
    ):
        """
        Initialize fetcher
        
        Args:
            db: Database session (if None, only fetches, doesn't save to DB)
            save_to_files: Whether to save fetched data to JSON files
            output_path: Path to save JSON files (if save_to_files=True)
            rate_limit_delay: Seconds to wait between requests
        """
        self.db = db
        self.save_to_files = save_to_files
        self.output_path = output_path or Path(settings.RAW_DATA_PATH) / "openparlamento"
        self.rate_limit_delay = rate_limit_delay
        
        if self.save_to_files:
            self.output_path.mkdir(parents=True, exist_ok=True)
    
    def fetch_all_persons(self, process_callback: Optional[Callable] = None) -> int:
        """
        Fetch all persons from the API
        
        Args:
            process_callback: Optional callback function(person_data) to process each person
            
        Returns:
            Number of persons fetched
        """
        logger.info("Starting to fetch persons from OpenParlamento API...")
        
        all_persons = []
        page_url = f"{self.PERSONS_LIST_URL}?page=1"
        page_num = 1
        
        while page_url:
            try:
                logger.info(f"Fetching page {page_num}...")
                response = requests.get(page_url, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                results = data.get("results", [])
                all_persons.extend(results)
                logger.info(f"Page {page_num}: Found {len(results)} persons (total: {len(all_persons)})")
                
                # Get next page URL
                page_url = data.get("next")
                page_num += 1
                
                # Rate limiting
                if page_url:
                    sleep(self.rate_limit_delay)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching page {page_url}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break
        
        logger.info(f"Fetched {len(all_persons)} persons from list endpoint")
        
        # Now fetch detailed data for each person
        total_fetched = 0
        for idx, person_summary in enumerate(all_persons, 1):
            try:
                person_url = person_summary.get("url")
                if not person_url:
                    logger.warning(f"Person {idx} has no URL, skipping")
                    continue
                
                person_data = self._fetch_person_details(person_url)
                if person_data:
                    # Process the person data
                    if process_callback:
                        process_callback(person_data)
                    elif self.db:
                        self._save_to_database(person_data)
                    
                    if self.save_to_files:
                        self._save_to_file(person_data)
                    
                    total_fetched += 1
                    
                    if idx % 50 == 0:
                        logger.info(f"Processed {idx}/{len(all_persons)} persons")
                    
                    # Rate limiting
                    sleep(self.rate_limit_delay)
                    
            except Exception as e:
                logger.error(f"Error processing person {idx}: {e}")
                continue
        
        logger.info(f"Successfully fetched {total_fetched} person details")
        return total_fetched
    
    def _fetch_person_details(self, person_url: str) -> Optional[Dict]:
        """
        Fetch detailed data for a single person
        
        Args:
            person_url: URL to person detail endpoint
            
        Returns:
            Person data dictionary or None if error
        """
        try:
            response = requests.get(person_url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching person details from {person_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching person: {e}")
            return None
    
    def _save_to_database(self, person_data: Dict):
        """
        Save person data directly to database
        
        Args:
            person_data: Person data dictionary
        """
        if not self.db:
            return
        
        try:
            from politia.pipeline.openparlamento_processor import OpenParlamentoProcessor
            processor = OpenParlamentoProcessor(self.db)
            
            # Extract person ID
            person_id = f"op_{person_data.get('id', 'unknown')}"
            
            # Check if exists
            existing = self.db.query(Person).filter(Person.person_id == person_id).first()
            if existing:
                processor._update_person(existing, person_data)
            else:
                person = processor._create_person(person_id, person_data)
                self.db.add(person)
            
            # Commit periodically
            if not hasattr(self, '_save_count'):
                self._save_count = 0
            self._save_count += 1
            
            if self._save_count % 50 == 0:
                self.db.commit()
                logger.debug(f"Committed {self._save_count} persons to database")
        except Exception as e:
            logger.error(f"Error saving person to database: {e}")
            self.db.rollback()
    
    def _save_to_file(self, person_data: Dict):
        """
        Save person data to JSON file
        
        Args:
            person_data: Person data dictionary
        """
        if not self.save_to_files:
            return
        
        try:
            family_name = person_data.get('family_name', 'Unknown')
            given_name = person_data.get('given_name', 'Unknown')
            filename = f"{family_name}__{given_name}_openparlamento.json"
            
            # Sanitize filename
            filename = filename.replace('/', '_').replace('\\', '_')
            
            file_path = self.output_path / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(person_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved to {file_path}")
        except Exception as e:
            logger.error(f"Error saving person to file: {e}")
    
    def fetch_person_by_id(self, person_id: int) -> Optional[Dict]:
        """
        Fetch a single person by their OpenParlamento ID
        
        Args:
            person_id: OpenParlamento person ID
            
        Returns:
            Person data dictionary or None if error
        """
        person_url = f"{self.PERSONS_LIST_URL}{person_id}/"
        return self._fetch_person_details(person_url)
    
    def check_api_health(self) -> bool:
        """
        Check if the API is accessible
        
        Returns:
            True if API is accessible, False otherwise
        """
        try:
            response = requests.get(self.PERSONS_LIST_URL, params={"page": 1}, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False

