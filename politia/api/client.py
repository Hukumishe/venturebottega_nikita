"""
Simple API client for querying the Politia API
Useful for scripts and data analysis workflows
"""
import requests
from typing import List, Dict, Optional
from loguru import logger

from politia.config import settings


class APIClient:
    """
    Simple client for accessing the Politia API
    Useful for data analysis, reporting, and integration with other tools
    """
    
    def __init__(self, api_base_url: Optional[str] = None):
        self.api_base_url = api_base_url or f"http://{settings.API_HOST}:{settings.API_PORT}"
    
    def search_persons(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for persons by name"""
        try:
            response = requests.get(
                f"{self.api_base_url}/persons",
                params={"search": query, "limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
        except Exception as e:
            logger.error(f"Error searching persons: {e}")
            return []
    
    def get_person(self, person_id: str) -> Optional[Dict]:
        """Get a specific person by ID"""
        try:
            response = requests.get(f"{self.api_base_url}/persons/{person_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting person: {e}")
            return None
    
    def search_speeches(self, 
                       speaker_id: Optional[str] = None,
                       session_id: Optional[str] = None,
                       topic_id: Optional[str] = None,
                       search_text: Optional[str] = None,
                       limit: int = 50) -> List[Dict]:
        """Search for speech segments"""
        params = {"limit": limit}
        if speaker_id:
            params["speaker_id"] = speaker_id
        if session_id:
            params["session_id"] = session_id
        if topic_id:
            params["topic_id"] = topic_id
        if search_text:
            params["search"] = search_text
        
        try:
            response = requests.get(
                f"{self.api_base_url}/speeches",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
        except Exception as e:
            logger.error(f"Error searching speeches: {e}")
            return []
    
    def search_topics(self, search: str, limit: int = 20) -> List[Dict]:
        """Search for topics by title"""
        try:
            response = requests.get(
                f"{self.api_base_url}/topics",
                params={"search": search, "limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
        except Exception as e:
            logger.error(f"Error searching topics: {e}")
            return []
    
    def get_topic_speeches(self, topic_id: str) -> List[Dict]:
        """Get all speeches for a specific topic"""
        return self.search_speeches(topic_id=topic_id, limit=1000)
    
    def get_person_speeches(self, person_id: str, limit: int = 100) -> List[Dict]:
        """Get all speeches by a specific person"""
        try:
            response = requests.get(
                f"{self.api_base_url}/persons/{person_id}/speeches",
                params={"limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
        except Exception as e:
            logger.error(f"Error getting person speeches: {e}")
            return []





