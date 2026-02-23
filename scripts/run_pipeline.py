#!/usr/bin/env python3
"""
Script to run the data pipeline
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from politia.models import init_db, get_db
from politia.pipeline import DataPipeline
from loguru import logger


def main():
    """Run the data pipeline"""
    logger.info("Initializing database...")
    init_db()
    
    logger.info("Starting data pipeline...")
    db = next(get_db())
    
    try:
        pipeline = DataPipeline(db)
        results = pipeline.run(
            process_openparlamento=True,
            process_webtv=True,
        )
        
        logger.info(f"Pipeline completed successfully!")
        logger.info(f"Results: {results}")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()






