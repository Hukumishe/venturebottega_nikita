"""
Command-line interface for Politia data engine.

Standardized way to refresh data sources:

  engine-cli refresh --source webtv [webtv options]
  engine-cli refresh --source politicians
  engine-cli refresh --source dagospia

  engine-cli process --source webtv|politicians|all
  engine-cli serve --reload

Edge cases (webtv refresh):
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

from loguru import logger


def _configure_logging(verbose: bool = False) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level=level,
    )


DEFAULT_RECENT_MEETINGS = 100


def _cmd_refresh_webtv(args: argparse.Namespace) -> int:
    from engine.sources.fetch_webtv import WebTVFetcher

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
        start = min(from_meeting, to_meeting)
        end = max(from_meeting, to_meeting)
        logger.info(f"Range mode: meetings {start} to {end}")
    elif from_meeting is not None:
        start = from_meeting
        end = fetcher.discover_latest_session(probe_start=from_meeting)
        if end is None:
            logger.warning("No sessions found on server from %s upward; fetching single meeting.", start)
            end = start
        else:
            logger.info(f"From-meeting mode: {start} up to latest ({end})")
    elif to_meeting is not None:
        start = to_meeting
        end = to_meeting
        logger.info(f"Single meeting mode: {to_meeting}")
    else:
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

    if max_meetings is not None and max_meetings >= 1 and (end - start + 1) > max_meetings:
        start = end - max_meetings + 1
        logger.info(f"Capped to --max-meetings {max_meetings}: fetching {start}..{end}")

    logger.info(f"Will fetch meetings in range [{start}, {end}] (skip existing: {skip_existing})")
    count = fetcher.fetch_session_range(start, end, skip_existing=skip_existing)
    logger.info(f"=== WebTV refresh completed: {count} new sessions saved to {fetcher.output_path} ===")
    return 0


def _cmd_refresh_politicians(args: argparse.Namespace) -> int:
    from engine.core.config import settings
    from engine.core.db import init_db, get_db
    from engine.sources.fetch_politicians import PoliticiansFetcher

    logger.info("=== Politicians refresh started ===")
    logger.info("Initializing database...")
    init_db()
    db = next(get_db())
    rate_limit = getattr(args, "rate_limit", None) or settings.FETCH_RATE_LIMIT_DELAY

    try:
        fetcher = PoliticiansFetcher(
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


def _cmd_refresh_webtv_archive(args: argparse.Namespace) -> int:
    from engine.sources.fetch_webtv_archive import WebTVArchiveFetcher

    logger.info("=== WebTV Archive refresh started ===")
    legislature = getattr(args, "legislature", 19)
    rate_limit = getattr(args, "rate_limit", None) or 1.5
    skip_existing = getattr(args, "skip_existing", True)

    fetcher = WebTVArchiveFetcher(
        legislature=legislature,
        rate_limit_delay=rate_limit,
    )

    count = fetcher.fetch_archive(skip_existing=skip_existing)
    logger.info(f"Archive index: {count} events")

    event_count = fetcher.fetch_all_event_interventions(skip_existing=skip_existing)
    logger.info(f"=== WebTV Archive refresh completed: {count} events, {event_count} new event pages ===")
    return 0


def _cmd_refresh_dagospia(args: argparse.Namespace) -> int:
    from engine.sources.fetch_dagospia import DagospiaFetcher

    logger.info("=== Dagospia refresh started ===")
    try:
        fetcher = DagospiaFetcher(save_to_files=True)
        result = fetcher.refresh()
        logger.info(
            f"=== Dagospia refresh completed: latest={result['latest_records']}, "
            f"compacted={result['compacted_records']}, removed_files={result['removed_files']} ==="
        )
        return 0
    except KeyboardInterrupt:
        logger.warning("Refresh interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Refresh failed: {e}")
        raise


def _cmd_process(args: argparse.Namespace) -> int:
    from engine.core.db import init_db, get_db
    from engine.core.process import NameMatcher, WebTVProcessor
    from engine.sources.fetch_politicians import PoliticiansFetcher

    logger.info("=== Processing started ===")
    logger.info("Initializing database...")
    init_db()
    db = next(get_db())

    source = args.source

    try:
        total_persons = 0
        total_sessions = 0

        if source in ("politicians", "all"):
            logger.info("Processing OpenParlamento data...")
            fetcher = PoliticiansFetcher(db=db)
            total_persons = fetcher.process_all_from_files()
            logger.info(f"Processed {total_persons} persons")

        if source in ("webtv", "all"):
            logger.info("Processing WebTV data...")
            name_matcher = NameMatcher(db)
            processor = WebTVProcessor(db, name_matcher)
            total_sessions = processor.process_all()
            logger.info(f"Processed {total_sessions} sessions")
            logger.info("Enriching sessions from WebTV archive...")
            processor.enrich_from_archive()
            processor.enrich_video_urls()

        logger.info(f"=== Processing completed: {total_persons} persons, {total_sessions} sessions ===")
        return 0
    except KeyboardInterrupt:
        logger.warning("Processing interrupted by user")
        db.rollback()
        return 130
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def _cmd_index(args: argparse.Namespace) -> int:
    from engine.search.opensearch_index import create_index, delete_index

    if args.delete:
        logger.info("=== Deleting OpenSearch index ===")
        delete_index()
        return 0

    if args.create:
        logger.info("=== Creating OpenSearch index ===")
        create_index()
        return 0

    if args.reindex:
        from engine.core.db import init_db, get_db
        from engine.search.opensearch_indexer import reindex_all

        logger.info("=== Full reindex from SQLite -> OpenSearch ===")
        create_index()
        init_db()
        db = next(get_db())
        try:
            count = reindex_all(db)
            logger.info(f"=== Reindex completed: {count} documents ===")
            return 0
        finally:
            db.close()

    logger.error("Specify --create, --reindex, or --delete")
    return 1


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8000)
    reload = getattr(args, "reload", False)

    logger.info(f"=== Starting API server on http://{host}:{port} (reload={reload}) ===")
    uvicorn.run("engine.api:app", host=host, port=port, reload=reload)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="engine-cli",
        description="Politia data engine: refresh, process and manage parliamentary data sources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command")

    # --- refresh ---
    refresh_parser = subparsers.add_parser("refresh", help="Refresh a data source")
    refresh_parser.add_argument("-v", "--verbose", action="store_true", help="Enable DEBUG logs.")
    refresh_parser.add_argument(
        "--source", choices=["webtv", "politicians", "dagospia", "webtv-archive"], required=True,
        help="Data source to refresh.",
    )
    refresh_parser.add_argument(
        "--rate-limit", type=float, default=None,
        help="Seconds between requests (default 1.5).",
    )
    refresh_parser.add_argument(
        "--from-meeting", type=int, default=None, metavar="N",
        help="Start meeting number (webtv only).",
    )
    refresh_parser.add_argument(
        "--to-meeting", type=int, default=None, metavar="M",
        help="End meeting number (webtv only).",
    )
    refresh_parser.add_argument(
        "--max-meetings", type=int, default=None, metavar="K",
        help="Cap total meetings to fetch (webtv only).",
    )
    refresh_parser.add_argument(
        "--legislature", type=int, default=19,
        help="Legislature number (webtv only, default: 19).",
    )
    refresh_parser.add_argument(
        "--no-skip-existing", dest="skip_existing", action="store_false",
        help="Re-fetch existing session files (webtv only).",
    )

    # --- process ---
    process_parser = subparsers.add_parser("process", help="Process fetched data into DB")
    process_parser.add_argument("-v", "--verbose", action="store_true", help="Enable DEBUG logs.")
    process_parser.add_argument(
        "--source", choices=["webtv", "politicians", "all"], required=True,
        help="Data source to process.",
    )

    # --- index ---
    index_parser = subparsers.add_parser("index", help="Manage OpenSearch index")
    index_parser.add_argument("-v", "--verbose", action="store_true", help="Enable DEBUG logs.")
    index_parser.add_argument("--create", action="store_true", help="Create index with mapping and analyzer.")
    index_parser.add_argument("--reindex", action="store_true", help="Full reindex from SQLite to OpenSearch.")
    index_parser.add_argument("--delete", action="store_true", help="Delete index.")

    # --- serve ---
    serve_parser = subparsers.add_parser("serve", help="Run FastAPI app (frontend + APIs)")
    serve_parser.add_argument("-v", "--verbose", action="store_true", help="Enable DEBUG logs.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    serve_parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000).")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload.")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    _configure_logging(verbose=getattr(args, "verbose", False))

    if args.command == "refresh":
        if args.source == "webtv":
            return _cmd_refresh_webtv(args)
        if args.source == "politicians":
            return _cmd_refresh_politicians(args)
        if args.source == "dagospia":
            return _cmd_refresh_dagospia(args)
        if args.source == "webtv-archive":
            return _cmd_refresh_webtv_archive(args)
    elif args.command == "process":
        return _cmd_process(args)
    elif args.command == "index":
        return _cmd_index(args)
    elif args.command == "serve":
        return _cmd_serve(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
