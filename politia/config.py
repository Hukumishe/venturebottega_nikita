"""
Configuration management for Politia system
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    DATABASE_URL: str = "sqlite:///./data/politia.db"
    
    # Data paths
    DATA_ROOT: Path = Path("data")
    RAW_DATA_PATH: Path = Path("data/raw")
    PROCESSED_DATA_PATH: Path = Path("data/processed")
    
    # API fetching
    OPENPARLAMENTO_API_BASE: str = "https://service.opdm.openpolis.io/api-openparlamento/v1/19"
    FETCH_RATE_LIMIT_DELAY: float = 3.0  # Seconds between API requests
    
    # Source data paths (relative to project root or absolute)
    OPENPARLAMENTO_DATA_PATH: Optional[str] = None
    WEBTV_DATA_PATH: Optional[str] = None
    
    # API
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    API_TITLE: str = "Politia API"
    API_VERSION: str = "v1"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

# Set default paths if not provided
if settings.OPENPARLAMENTO_DATA_PATH is None:
    # Try to find it relative to common locations
    # Get the project root (parent of politia package)
    project_root = Path(__file__).parent.parent
    possible_paths = [
        project_root.parent / "politia-main" / "notebooks" / "data" / "openparlamento",
        project_root / "data" / "raw" / "openparlamento",
    ]
    for path in possible_paths:
        if path.exists():
            settings.OPENPARLAMENTO_DATA_PATH = str(path.absolute())
            break

if settings.WEBTV_DATA_PATH is None:
    project_root = Path(__file__).parent.parent
    possible_paths = [
        project_root.parent / "politia-main" / "notebooks" / "data" / "camera",
        project_root / "data" / "raw" / "camera",
    ]
    for path in possible_paths:
        if path.exists():
            settings.WEBTV_DATA_PATH = str(path.absolute())
            break

