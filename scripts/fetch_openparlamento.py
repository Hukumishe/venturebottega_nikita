#!/usr/bin/env python3
"""
Script to fetch fresh data from OpenParlamento API
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from politia.models import init_db, get_db
from politia.pipeline.openparlamento_fetcher import OpenParlamentoFetcher
from loguru import logger


def main():
    """Fetch data from OpenParlamento API"""
    logger.info("Initializing database...")
    init_db()
    
    db = next(get_db())
    
    try:
        # Check API health first
        fetcher = OpenParlamentoFetcher(
            db=db,
            save_to_files=True,  # Also save to JSON files as backup
            rate_limit_delay=3.0,  # 3 seconds between requests
        )
        
        logger.info("Checking API health...")
        if not fetcher.check_api_health():
            logger.error("API is not accessible. Please check your internet connection.")
            return
        
        logger.info("API is accessible. Starting fetch...")
        
        # Fetch all persons
        count = fetcher.fetch_all_persons()
        
        # Final commit
        db.commit()
        
        logger.info(f"Fetch completed successfully! Fetched {count} persons.")
        logger.info(f"Data saved to database and JSON files in {fetcher.output_path}")
        
    except KeyboardInterrupt:
        logger.warning("Fetch interrupted by user")
        db.rollback()
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

