"""
Fetcher for WebTV (parliamentary transcript) data from Camera dei Deputati
Fetches XML transcripts and converts to JSON format
"""
import requests
import json
from pathlib import Path
from time import sleep
from typing import List, Dict, Optional, Tuple
from loguru import logger
from bs4 import BeautifulSoup
from datetime import datetime

from politia.config import settings


class WebTVFetcher:
    """
    Fetches parliamentary transcripts from Camera dei Deputati website
    """
    
    BASE_URL = "https://documenti.camera.it/apps/commonServices/getDocumento.ashx"
    
    def __init__(
        self,
        legislature: int = 19,
        save_to_files: bool = True,
        output_path: Optional[Path] = None,
        rate_limit_delay: float = 5.0,
    ):
        """
        Initialize WebTV fetcher
        
        Args:
            legislature: Legislature number (default: 19)
            save_to_files: Whether to save fetched data to JSON files
            output_path: Path to save JSON files
            rate_limit_delay: Seconds to wait between requests
        """
        self.legislature = legislature
        self.save_to_files = save_to_files
        self.output_path = output_path or Path(settings.RAW_DATA_PATH) / "camera"
        self.rate_limit_delay = rate_limit_delay
        
        if self.save_to_files:
            self.output_path.mkdir(parents=True, exist_ok=True)
    
    def fetch_session(self, session_number: int) -> Optional[Dict]:
        """
        Fetch a single session by session number
        
        Args:
            session_number: Session number (e.g., 347)
            
        Returns:
            Parsed session data dictionary or None if error
        """
        url = self._build_session_url(session_number)
        
        try:
            logger.info(f"Fetching session {session_number}...")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse XML
            soup = BeautifulSoup(response.content, "xml")
            
            # Extract session info
            seduta = soup.find('seduta')
            if not seduta:
                logger.warning(f"No <seduta> tag found in session {session_number}")
                return None
            
            numero_legislatura = seduta.get('legislatura', str(self.legislature))
            numero_seduta = seduta.get('numero', str(session_number))
            
            # Extract date if available
            date_str = seduta.get('data') or seduta.get('dataSeduta')
            session_date = None
            if date_str:
                try:
                    # Try to parse date (format may vary)
                    session_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except:
                    pass
            
            # Parse debates (topics)
            contents = {}
            dibattiti = soup.find_all('dibattito')
            
            for dibattito in dibattiti:
                titolo_tag = dibattito.find('titolo')
                if not titolo_tag or not titolo_tag.text.strip():
                    continue
                
                titolo = titolo_tag.text.strip()
                interventions = []
                
                # Collect interventions
                self._gather_interventions(dibattito, interventions)
                
                if interventions:
                    contents[titolo] = interventions
            
            if not contents:
                logger.warning(f"No debates found in session {session_number}")
                return None
            
            result = {
                'legislature': numero_legislatura,
                'session_number': numero_seduta,
                'date': session_date.isoformat() if session_date else None,
                'contents': contents,
            }
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching session {session_number}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing session {session_number}: {e}")
            return None
    
    def fetch_session_range(self, start: int, end: int, skip_existing: bool = True) -> int:
        """
        Fetch multiple sessions in a range
        
        Args:
            start: Starting session number
            end: Ending session number (inclusive)
            skip_existing: If True, skip sessions that already have files
            
        Returns:
            Number of sessions successfully fetched
        """
        logger.info(f"Fetching sessions {start} to {end}...")
        
        # Get existing sessions if we should skip them
        existing_sessions = set()
        if skip_existing:
            existing_sessions = set(self.get_existing_sessions())
            skipped = [s for s in range(start, end + 1) if s in existing_sessions]
            if skipped:
                logger.info(f"Skipping {len(skipped)} existing sessions: {skipped[:10]}{'...' if len(skipped) > 10 else ''}")
        
        count = 0
        skipped_count = 0
        for session_num in range(start, end + 1):
            # Skip if already exists
            if skip_existing and session_num in existing_sessions:
                skipped_count += 1
                continue
            
            session_data = self.fetch_session(session_num)
            
            if session_data:
                # Save to file
                if self.save_to_files:
                    filename = f"{session_data['legislature']}__{session_data['session_number']}.json"
                    file_path = self.output_path / filename
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(session_data, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"Saved session {session_num} to {file_path}")
                
                count += 1
            else:
                logger.debug(f"Session {session_num} not found or empty")
            
            # Rate limiting
            if session_num < end:
                sleep(self.rate_limit_delay)
        
        total_attempted = end - start + 1
        logger.info(f"Fetched {count} new sessions, skipped {skipped_count} existing, out of {total_attempted} attempted")
        return count
    
    def _build_session_url(self, session_number: int) -> str:
        """Build URL for a session"""
        return (
            f"{self.BASE_URL}?"
            f"sezione=assemblea&"
            f"tipoDoc=formato_xml&"
            f"tipologia=stenografico&"
            f"idNumero={session_number:04d}&"
            f"idLegislatura={self.legislature}"
        )
    
    def _gather_interventions(self, parent_tag, conversation_list: List[Dict]):
        """
        Recursively gather interventions from XML
        """
        for child in parent_tag.children:
            if child.name == 'intervento':
                intervention = self._parse_intervention(child)
                if intervention:
                    conversation_list.append(intervention)
            elif child.name == 'fase':
                self._gather_interventions(child, conversation_list)
    
    def _parse_intervention(self, intervento_tag) -> Optional[Dict]:
        """
        Parse a single intervention (speech) from XML
        """
        try:
            # Extract speaker name
            nom_tag = intervento_tag.find("nominativo")
            speaker = nom_tag.get("cognomeNome") if nom_tag else "Unknown"
            
            # Collect text blocks
            text_blocks = []
            
            # Main text from <testoXHTML>
            testo_tag = intervento_tag.find("testoXHTML")
            if testo_tag:
                text_blocks.append(testo_tag.get_text(strip=True))
            
            # Additional text from <interventoVirtuale>
            iv_tags = intervento_tag.find_all("interventoVirtuale")
            for iv in iv_tags:
                text_blocks.append(iv.get_text(strip=False))
            
            full_text = "\n".join(text_blocks).strip()
            
            if not full_text:
                return None
            
            return {
                "speaker": speaker,
                "text": full_text
            }
        except Exception as e:
            logger.debug(f"Error parsing intervention: {e}")
            return None
    
    def check_session_exists(self, session_number: int) -> bool:
        """
        Check if a session exists without fetching full data
        
        Args:
            session_number: Session number to check
            
        Returns:
            True if session exists, False otherwise
        """
        url = self._build_session_url(session_number)
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            return response.status_code == 200
        except:
            return False
    
    def get_existing_sessions(self) -> List[int]:
        """
        Get list of session numbers that already have files
        
        Returns:
            List of session numbers that exist as files
        """
        if not self.output_path.exists():
            return []
        
        existing = []
        for file_path in self.output_path.glob(f"{self.legislature}__*.json"):
            try:
                # Extract session number from filename (e.g., "19__347.json" -> 347)
                parts = file_path.stem.split('__')
                if len(parts) == 2 and parts[0] == str(self.legislature):
                    session_num = int(parts[1])
                    existing.append(session_num)
            except (ValueError, IndexError):
                continue
        
        return sorted(existing)
    
    def get_last_session_number(self) -> Optional[int]:
        """
        Get the highest session number that has been fetched
        
        Returns:
            Highest session number, or None if no sessions exist
        """
        existing = self.get_existing_sessions()
        return max(existing) if existing else None
    
    def fetch_incremental(self, max_sessions: Optional[int] = None, max_attempts: int = 100) -> int:
        """
        Fetch only new sessions incrementally (starting from last fetched session)
        
        Args:
            max_sessions: Maximum number of new sessions to fetch (None = unlimited)
            max_attempts: Maximum number of consecutive missing sessions before stopping
            
        Returns:
            Number of sessions successfully fetched
        """
        # Get last fetched session number
        last_session = self.get_last_session_number()
        
        if last_session is None:
            logger.warning("No existing sessions found. Use fetch_session_range() for initial fetch.")
            return 0
        
        start_session = last_session + 1
        logger.info(f"Last fetched session: {last_session}")
        logger.info(f"Starting incremental fetch from session {start_session}...")
        
        # Try to find the end by checking consecutive sessions
        # Stop after max_attempts consecutive missing sessions
        end_session = start_session
        consecutive_missing = 0
        
        for session_num in range(start_session, start_session + max_attempts):
            if self.check_session_exists(session_num):
                end_session = session_num
                consecutive_missing = 0
            else:
                consecutive_missing += 1
                if consecutive_missing >= 5:  # Stop after 5 consecutive missing
                    break
        
        if end_session < start_session:
            logger.info("No new sessions found")
            return 0
        
        # Limit by max_sessions if specified
        if max_sessions:
            end_session = min(end_session, start_session + max_sessions - 1)
        
        logger.info(f"Fetching sessions {start_session} to {end_session}...")
        return self.fetch_session_range(start_session, end_session)
    
    def fetch_session_range_smart(self, start: Optional[int] = None, end: Optional[int] = None, 
                                   incremental: bool = True, max_sessions: Optional[int] = None) -> int:
        """
        Smart fetch that can work incrementally or with manual range
        
        Args:
            start: Starting session number (if None, uses incremental mode)
            end: Ending session number (if None and incremental=False, uses max_attempts)
            incremental: If True and start=None, fetches only new sessions
            max_sessions: Maximum sessions to fetch in incremental mode
            
        Returns:
            Number of sessions successfully fetched
        """
        if incremental and start is None:
            # Incremental mode: fetch only new sessions
            return self.fetch_incremental(max_sessions=max_sessions)
        elif start is not None:
            # Manual range mode
            if end is None:
                # If end not specified, try to find it automatically
                end = start + 100  # Default to checking next 100 sessions
                logger.info(f"End session not specified, checking up to {end}")
            return self.fetch_session_range(start, end)
        else:
            logger.error("Either specify start session or use incremental=True")
            return 0



