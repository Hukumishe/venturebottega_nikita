#!/usr/bin/env python3
"""
Script to fetch WebTV (parliamentary transcript) data from Camera dei Deputati
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from politia.pipeline.webtv_fetcher import WebTVFetcher
from loguru import logger


def main():
    """Fetch WebTV data from Camera dei Deputati"""
    
    # Configuration
    LEGISLATURE = 19
    START_SESSION = 347  # Adjust based on what you need
    END_SESSION = 450    # Adjust based on what you need
    RATE_LIMIT = 5.0     # 5 seconds between requests (be respectful)
    
    logger.info("Starting WebTV data fetch...")
    logger.info(f"Legislature: {LEGISLATURE}")
    logger.info(f"Session range: {START_SESSION} to {END_SESSION}")
    logger.info(f"Rate limit: {RATE_LIMIT} seconds between requests")
    
    fetcher = WebTVFetcher(
        legislature=LEGISLATURE,
        save_to_files=True,
        rate_limit_delay=RATE_LIMIT,
    )
    
    try:
        count = fetcher.fetch_session_range(START_SESSION, END_SESSION)
        
        logger.info(f"Fetch completed! Successfully fetched {count} sessions.")
        logger.info(f"Files saved to: {fetcher.output_path}")
        logger.info("You can now run the pipeline to process these files:")
        logger.info("  python scripts/run_pipeline.py")
        
    except KeyboardInterrupt:
        logger.warning("Fetch interrupted by user")
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        raise


if __name__ == "__main__":
    main()

