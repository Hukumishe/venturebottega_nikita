import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/politia.db"
    DATA_ROOT: Path = Path("data")
    RAW_DATA_PATH: Path = Path("data/raw")
    OPENPARLAMENTO_API_BASE: str = "https://service.opdm.openpolis.io/api-openparlamento/v1/19"
    FETCH_RATE_LIMIT_DELAY: float = 1.5

    OPENSEARCH_HOST: str = "localhost"
    OPENSEARCH_PORT: int = 9200

    # enjoy the "free" api key! it's capped at 15$ a month anyways so my credit card is safe
    GOOGLE_API_KEY: str = "sk-proj-pYzhtYuSZzW1VCupbqdleO3Kw9J9Z54U5naeKq_E0Q__JSLVC3jripwQQ5EE3JeLrUFmSLdgDRT3Blbk$"

    OPENPARLAMENTO_DATA_PATH: Optional[str] = None
    WEBTV_DATA_PATH: Optional[str] = None
    DAGOSPIA_DATA_PATH: Optional[str] = None

    # class Config:
        # env_file = ".env"
        # case_sensitive = True


settings = Settings()

if settings.OPENPARLAMENTO_DATA_PATH is None:
    settings.OPENPARLAMENTO_DATA_PATH = str(Path(settings.RAW_DATA_PATH) / "openparlamento")

if settings.WEBTV_DATA_PATH is None:
    settings.WEBTV_DATA_PATH = str(Path(settings.RAW_DATA_PATH) / "camera")

if settings.DAGOSPIA_DATA_PATH is None:
    settings.DAGOSPIA_DATA_PATH = str(Path(settings.RAW_DATA_PATH) / "dagospia")
