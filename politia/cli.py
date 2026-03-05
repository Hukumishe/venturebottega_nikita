"""
Command-line interface for Politia data engine.

Standardized way to refresh data sources:

  politia-engine refresh --source webtv [webtv options]
  politia-engine refresh --source politicians

Edge cases (webtv):
  - Neither --from-meeting nor --to-meeting: fetch the 100 most recent meetings
    (discover latest on server, then fetch latest-99..latest).
  - Only --from-meeting N: fetch from meeting N up to the latest available.
  - Only --to-meeting M: fetch the single meeting M.
  - Both --from-meeting N --to-meeting M: fetch range [N, M] (inclusive).
  - Single meeting: use --from-meeting X --to-meeting X.
  - --max-meetings caps how many meetings are retrieved in any scenario.
"""
import argparse
import sys
from pathlib import Path
from typing import Optional

# Ensure package is importable when run as script
if __name__ == "__main__" and __package__ is None:
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from loguru import logger

from politia.config import settings


def _configure_logging(verbose: bool = False) -> None:
    """Configure loguru so logs are visible with a clear format."""
    logger.remove()  # remove default handler
    level = "DEBUG" if verbose else getattr(settings, "LOG_LEVEL", "INFO")
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level=level,
    )


# Default number of "most recent" meetings when no range is specified
DEFAULT_RECENT_MEETINGS = 100


def _cmd_refresh_webtv(args: argparse.Namespace) -> int:
    from politia.pipeline.webtv_fetcher import WebTVFetcher

    logger.info("=== WebTV refresh started ===")
    legislature = getattr(args, "legislature", 19)
    rate_limit = getattr(args, "rate_limit", None) or 1.5
    skip_existing = getattr(args, "skip_existing", True)
    from_meeting: Optional[int] = getattr(args, "from_meeting", None)
    to_meeting: Optional[int] = getattr(args, "to_meeting", None)
    max_meetings: Optional[int] = getattr(args, "max_meetings", None)

    fetcher = WebTVFetcher(
        legislature=legislature,
        save_to_files=True,
        rate_limit_delay=rate_limit,
    )

    existing = fetcher.get_existing_sessions()
    if existing:
        logger.info(f"Found {len(existing)} existing sessions (last: {max(existing)})")
    else:
        logger.info("No existing sessions found")

    start: Optional[int] = None
    end: Optional[int] = None

    if from_meeting is not None and to_meeting is not None:
        # Explicit range [from_meeting, to_meeting]
        start = min(from_meeting, to_meeting)
        end = max(from_meeting, to_meeting)
        logger.info(f"Range mode: meetings {start} to {end}")
    elif from_meeting is not None:
        # From --from-meeting up to latest available
        start = from_meeting
        end = fetcher.discover_latest_session(probe_start=from_meeting)
        if end is None:
            logger.warning("No sessions found on server from %s upward; fetching single meeting.", start)
            end = start
        else:
            logger.info(f"From-meeting mode: {start} up to latest ({end})")
    elif to_meeting is not None:
        # Only --to-meeting: single meeting
        start = to_meeting
        end = to_meeting
        logger.info(f"Single meeting mode: {to_meeting}")
    else:
        # Neither: 100 most recent (discover latest, then fetch last DEFAULT_RECENT_MEETINGS)
        # Cap discovery at 120 probes so we don't scan hundreds of sessions
        latest = fetcher.discover_latest_session(max_probe=120)
        if latest is None:
            logger.error(
                "Could not discover latest session (no local data and probe found nothing). "
                "Use --from-meeting N to set a starting point."
            )
            return 1
        end = latest
        start = max(1, latest - DEFAULT_RECENT_MEETINGS + 1)
        logger.info(f"Most-recent mode: fetching meetings {start}..{end} (up to {DEFAULT_RECENT_MEETINGS} meetings)")

    # Apply --max-meetings cap: shrink range from the left so we take at most max_meetings
    if max_meetings is not None and max_meetings >= 1 and (end - start + 1) > max_meetings:
        start = end - max_meetings + 1
        logger.info(f"Capped to --max-meetings {max_meetings}: fetching {start}..{end}")

    logger.info(f"Will fetch meetings in range [{start}, {end}] (skip existing: {skip_existing})")
    count = fetcher.fetch_session_range(start, end, skip_existing=skip_existing)
    logger.info(f"=== WebTV refresh completed: {count} new sessions saved to {fetcher.output_path} ===")
    return 0


def _cmd_refresh_politicians(args: argparse.Namespace) -> int:
    from politia.models import init_db, get_db
    from politia.pipeline.openparlamento_fetcher import OpenParlamentoFetcher

    logger.info("=== Politicians refresh started ===")
    logger.info("Initializing database...")
    init_db()
    db = next(get_db())
    rate_limit = getattr(args, "rate_limit", None) or settings.FETCH_RATE_LIMIT_DELAY

    try:
        fetcher = OpenParlamentoFetcher(
            db=db,
            save_to_files=True,
            rate_limit_delay=rate_limit,
        )
        logger.info("Checking OpenParlamento API health...")
        if not fetcher.check_api_health():
            logger.error("OpenParlamento API is not accessible. Check network or API status.")
            return 1
        logger.info("Performing full politicians refresh...")
        count = fetcher.fetch_all_persons()
        db.commit()
        logger.info(f"=== Politicians refresh completed: {count} persons saved ===")
        return 0
    except KeyboardInterrupt:
        logger.warning("Refresh interrupted by user")
        db.rollback()
        return 130
    except Exception as e:
        logger.error(f"Refresh failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="politia-engine",
        description="Politia data engine: refresh and manage parliamentary data sources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command")

    # refresh
    refresh_parser = subparsers.add_parser("refresh", help="Refresh a data source")
    refresh_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG logs (show more detail).",
    )
    refresh_parser.add_argument(
        "--source",
        choices=["webtv", "politicians"],
        required=True,
        help="Data source to refresh: webtv (Camera transcripts) or politicians (OpenParlamento).",
    )
    refresh_parser.add_argument(
        "--rate-limit",
        type=float,
        default=None,
        help="Seconds between requests (default 1.5 for both; increase if you get 429/blocked).",
    )

    # webtv-specific options (only meaningful when --source webtv)
    refresh_parser.add_argument(
        "--from-meeting",
        type=int,
        default=None,
        metavar="N",
        help="Start meeting number. With webtv: fetch from N to latest if --to-meeting not set.",
    )
    refresh_parser.add_argument(
        "--to-meeting",
        type=int,
        default=None,
        metavar="M",
        help="End meeting number. With webtv: range [--from-meeting, M], or single meeting M if only this is set.",
    )
    refresh_parser.add_argument(
        "--max-meetings",
        type=int,
        default=None,
        metavar="K",
        help="Cap total meetings to fetch (webtv only). Applies to range or 'most recent' mode.",
    )
    refresh_parser.add_argument(
        "--legislature",
        type=int,
        default=19,
        help="Legislature number (webtv only, default: 19).",
    )
    refresh_parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Re-fetch and overwrite existing session files (webtv only).",
    )

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if getattr(args, "verbose", False):
        _configure_logging(verbose=True)
    else:
        _configure_logging(verbose=False)

    if args.command == "refresh":
        if args.source == "webtv":
            return _cmd_refresh_webtv(args)
        if args.source == "politicians":
            return _cmd_refresh_politicians(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
