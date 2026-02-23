"""
Main data pipeline orchestrator
"""
from sqlalchemy.orm import Session
from loguru import logger

from politia.pipeline.openparlamento_processor import OpenParlamentoProcessor
from politia.pipeline.webtv_processor import WebTVProcessor
from politia.pipeline.name_matcher import NameMatcher


class DataPipeline:
    """
    Main pipeline orchestrator that processes all data sources
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.openparlamento_processor = OpenParlamentoProcessor(db)
        self.name_matcher = NameMatcher(db)
        self.webtv_processor = WebTVProcessor(db, self.name_matcher)
    
    def run(self, process_openparlamento: bool = True, process_webtv: bool = True):
        """
        Run the complete data pipeline
        
        Args:
            process_openparlamento: Whether to process OpenParlamento data
            process_webtv: Whether to process WebTV data
        """
        logger.info("Starting data pipeline...")
        
        total_persons = 0
        total_sessions = 0
        
        # Step 1: Process OpenParlamento (persons)
        if process_openparlamento:
            logger.info("Step 1: Processing OpenParlamento data...")
            total_persons = self.openparlamento_processor.process_all()
            logger.info(f"Processed {total_persons} persons")
        
        # Step 2: Process WebTV (sessions, topics, speeches)
        if process_webtv:
            logger.info("Step 2: Processing WebTV data...")
            # Reload name matcher cache after processing persons
            if process_openparlamento:
                self.name_matcher._load_person_cache()
            total_sessions = self.webtv_processor.process_all()
            logger.info(f"Processed {total_sessions} sessions")
        
        logger.info("Data pipeline completed successfully!")
        return {
            'persons': total_persons,
            'sessions': total_sessions,
        }






