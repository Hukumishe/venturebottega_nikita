#!/usr/bin/env python3
"""
Script to fetch WebTV (parliamentary transcript) data from Camera dei Deputati
Supports incremental fetching (only new sessions) or manual range specification
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from politia.pipeline.webtv_fetcher import WebTVFetcher
from loguru import logger


def main():
    """Fetch WebTV data from Camera dei Deputati"""
    
    parser = argparse.ArgumentParser(
        description="Fetch WebTV parliamentary transcript data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Incremental fetch (default - only new sessions)
  python scripts/fetch_webtv.py
  
  # Manual range
  python scripts/fetch_webtv.py --start 347 --end 450
  
  # Incremental with max limit
  python scripts/fetch_webtv.py --max-sessions 50
        """
    )
    
    parser.add_argument(
        "--legislature",
        type=int,
        default=19,
        help="Legislature number (default: 19)"
    )
    parser.add_argument(
        "--start",
        type=int,
        default=None,
        help="Starting session number (if not specified, uses incremental mode)"
    )
    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help="Ending session number (only used with --start)"
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        default=True,
        help="Fetch only new sessions incrementally (default: True)"
    )
    parser.add_argument(
        "--no-incremental",
        dest="incremental",
        action="store_false",
        help="Disable incremental mode (requires --start)"
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=None,
        help="Maximum number of new sessions to fetch in incremental mode"
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=5.0,
        help="Seconds to wait between requests (default: 5.0)"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip sessions that already have files (default: True)"
    )
    parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Re-fetch existing sessions"
    )
    
    args = parser.parse_args()
    
    logger.info("Starting WebTV data fetch...")
    logger.info(f"Legislature: {args.legislature}")
    logger.info(f"Rate limit: {args.rate_limit} seconds between requests")
    
    fetcher = WebTVFetcher(
        legislature=args.legislature,
        save_to_files=True,
        rate_limit_delay=args.rate_limit,
    )
    
    # Show existing sessions info
    existing = fetcher.get_existing_sessions()
    if existing:
        logger.info(f"Found {len(existing)} existing sessions (last: {max(existing)})")
    else:
        logger.info("No existing sessions found")
    
    try:
        if args.start is not None:
            # Manual range mode
            end = args.end if args.end is not None else args.start + 100
            logger.info(f"Manual range mode: sessions {args.start} to {end}")
            count = fetcher.fetch_session_range(
                args.start, 
                end, 
                skip_existing=args.skip_existing
            )
        else:
            # Incremental mode
            logger.info("Incremental mode: fetching only new sessions")
            count = fetcher.fetch_incremental(max_sessions=args.max_sessions)
        
        logger.info(f"Fetch completed! Successfully fetched {count} new sessions.")
        logger.info(f"Files saved to: {fetcher.output_path}")
        
        if count > 0:
            logger.info("You can now run the pipeline to process these files:")
            logger.info("  python scripts/run_pipeline.py")
        else:
            logger.info("No new sessions to process.")
        
    except KeyboardInterrupt:
        logger.warning("Fetch interrupted by user")
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        raise


if __name__ == "__main__":
    main()



