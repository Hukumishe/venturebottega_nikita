"""Fetch WebTV archive data: session index + per-event intervention metadata."""

import json
import re
from collections import defaultdict
from pathlib import Path
from time import sleep
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger

from engine.core.config import settings

BASE_URL = "https://webtv.camera.it"
ARCHIVE_WS_URL = f"{BASE_URL}/ws/archivio"


def _safe_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _extract_intervention_id(a_tag) -> Optional[int]:
    tag_id = a_tag.get("id", "")
    match = re.search(r"ora_indice_(\d+)", tag_id)
    if match:
        return int(match.group(1))
    onclick = a_tag.get("onclick", "")
    match = re.search(r"parse_oratore_click\((\d+)\)", onclick)
    if match:
        return int(match.group(1))
    return None


class WebTVArchiveFetcher:
    def __init__(
        self,
        legislature: int = 19,
        output_path: Optional[Path] = None,
        rate_limit_delay: float = 1.5,
    ):
        self.legislature = legislature
        self.output_path = output_path or Path(settings.RAW_DATA_PATH) / "webtv_archive"
        self.rate_limit_delay = rate_limit_delay
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Referer": f"{BASE_URL}/archivio",
        })

    def fetch_archive(self, skip_existing: bool = True) -> int:
        """Fetch full archive index via POST pagination, save webtv_archive.json."""
        logger.info("Fetching WebTV archive index...")

        all_items: List[Dict] = []
        page = 1
        total_records = None

        while True:
            payload = {
                "filter_label_leg_19": str(self.legislature),
                "filter_label_sez_1": "1",
                "page": str(page),
            }
            headers = {
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": BASE_URL,
            }

            try:
                resp = self.session.post(
                    ARCHIVE_WS_URL, data=payload, headers=headers, timeout=30
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Archive page {page} request failed: {e}")
                break

            try:
                soup = BeautifulSoup(resp.text, "xml")
            except Exception:
                soup = BeautifulSoup(resp.text, "html.parser")

            if total_records is None:
                tot_tag = soup.find("tot_records")
                if tot_tag:
                    total_records = _safe_int(tot_tag.text) or 0
                    logger.info(f"Total records in archive: {total_records}")

            items = soup.find_all("item")
            if not items:
                logger.info(f"No items on page {page}, stopping pagination.")
                break

            for item in items:
                event_id = _safe_int(item.find("id").text if item.find("id") else None)
                titolo = _clean_text(item.find("titolo").text if item.find("titolo") else "")
                dataora = _clean_text(
                    item.find("dataora_evento").text if item.find("dataora_evento") else ""
                )

                if not event_id:
                    continue

                session_number = self._extract_session_number(titolo)
                event_date = dataora[:10] if len(dataora) >= 10 else None

                all_items.append({
                    "event_id": event_id,
                    "title": titolo,
                    "date": event_date,
                    "session_number": session_number,
                })

            logger.info(f"Page {page}: got {len(items)} items (total so far: {len(all_items)})")

            if total_records and len(all_items) >= total_records:
                break

            page += 1
            sleep(self.rate_limit_delay)

        archive_path = self.output_path / "webtv_archive.json"
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(all_items, f, ensure_ascii=False, indent=2)

        logger.info(f"Archive saved: {len(all_items)} events -> {archive_path}")
        return len(all_items)

    def fetch_event_interventions(self, event_id: int) -> List[Dict]:
        """Fetch and parse intervention index for a single event."""
        url = f"{BASE_URL}/evento/{event_id}"

        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch event {event_id}: {e}")
            return []

        return self._parse_event_page(event_id, resp.text)

    def fetch_all_event_interventions(self, skip_existing: bool = True) -> int:
        """Fetch interventions for all events in the archive."""
        archive_path = self.output_path / "webtv_archive.json"
        if not archive_path.exists():
            logger.error("Archive index not found. Run fetch_archive() first.")
            return 0

        with open(archive_path, "r", encoding="utf-8") as f:
            archive = json.load(f)

        count = 0
        total = len(archive)
        for idx, item in enumerate(archive, 1):
            event_id = item.get("event_id")
            if not event_id:
                continue

            event_file = self.output_path / f"event_{event_id}.json"
            if skip_existing and event_file.exists():
                continue

            logger.info(f"Event {event_id} ({idx}/{total})")
            interventions = self.fetch_event_interventions(event_id)

            with open(event_file, "w", encoding="utf-8") as f:
                json.dump(interventions, f, ensure_ascii=False, indent=2)

            count += 1
            if idx < total:
                sleep(self.rate_limit_delay)

        logger.info(f"Fetched interventions for {count} new events")
        return count

    def _parse_event_page(self, event_id: int, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        indice = soup.find("ul", id="indice_container")
        if indice is None:
            logger.warning(f"No indice_container in event {event_id}")
            return []

        interventions = []
        for a_tag in indice.find_all("a", href=True):
            intervention_id = _extract_intervention_id(a_tag)
            if intervention_id is None:
                continue

            role_text = _clean_text(a_tag.get_text(" ", strip=True))
            speaker = _clean_text(a_tag.get("data-etichetta"))
            if not speaker:
                speaker = role_text

            start_tc = _safe_int(a_tag.get("data-tc_start"))
            end_tc = _safe_int(a_tag.get("data-tc_end"))
            dataora_c = a_tag.get("data-dataora_c")

            start_label = ""
            if start_tc is not None:
                total_seconds = start_tc // 1000 if start_tc > 100000 else start_tc
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                start_label = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            embedded_url = f"{BASE_URL}/embedded/evento/{event_id}?intervento={intervention_id}"

            interventions.append({
                "intervention_id": intervention_id,
                "speaker": speaker,
                "role_text": role_text,
                "start_tc": start_tc,
                "end_tc": end_tc,
                "start_time_label": start_label,
                "dataora_c": dataora_c,
                "embedded_url": embedded_url,
            })

        return interventions

    def _extract_session_number(self, title: str) -> Optional[int]:
        match = re.search(r"[Ss]eduta\s+(\d+)", title)
        if match:
            return int(match.group(1))
        return None

    def get_speaker_start_map(self, event_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """Map speaker -> sorted list of their interventions for an event."""
        interventions = self.fetch_event_interventions(event_id)

        result: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for x in interventions:
            result[x["speaker"]].append({
                "intervention_id": x["intervention_id"],
                "start_time_label": x["start_time_label"],
                "start_tc": x["start_tc"],
                "end_tc": x["end_tc"],
                "dataora_c": x["dataora_c"],
                "embedded_url": x["embedded_url"],
                "role_text": x["role_text"],
            })

        for speaker in result:
            result[speaker].sort(key=lambda d: (
                d["start_tc"] is None,
                d["start_tc"] if d["start_tc"] is not None else 10**12,
            ))

        return dict(result)
