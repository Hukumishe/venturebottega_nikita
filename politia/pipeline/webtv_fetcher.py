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
    
    def fetch_session_range(self, start: int, end: int) -> int:
        """
        Fetch multiple sessions in a range
        
        Args:
            start: Starting session number
            end: Ending session number (inclusive)
            
        Returns:
            Number of sessions successfully fetched
        """
        logger.info(f"Fetching sessions {start} to {end}...")
        
        count = 0
        for session_num in range(start, end + 1):
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
        
        logger.info(f"Fetched {count} sessions out of {end - start + 1} attempted")
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

