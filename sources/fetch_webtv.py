import json
from pathlib import Path
from time import sleep
from typing import List, Dict, Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from loguru import logger

from engine.core.config import settings


class WebTVFetcher:
    BASE_URL = "https://documenti.camera.it/apps/commonServices/getDocumento.ashx"

    def __init__(
        self,
        legislature: int = 19,
        save_to_files: bool = True,
        output_path: Optional[Path] = None,
        rate_limit_delay: float = 1.5,
    ):
        self.legislature = legislature
        self.save_to_files = save_to_files
        self.output_path = output_path or Path(settings.RAW_DATA_PATH) / "camera"
        self.rate_limit_delay = rate_limit_delay

        if self.save_to_files:
            self.output_path.mkdir(parents=True, exist_ok=True)

    def fetch_session(self, session_number: int) -> Optional[Dict]:
        url = self._build_session_url(session_number)

        try:
            logger.debug(f"Fetching session {session_number}...")
            response = requests.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "xml")

            seduta = soup.find('seduta')
            if not seduta:
                logger.warning(f"No <seduta> tag found in session {session_number}")
                return None

            numero_legislatura = seduta.get('legislatura', str(self.legislature))
            numero_seduta = seduta.get('numero', str(session_number))

            date_str = seduta.get('data') or seduta.get('dataSeduta')
            session_date = None
            if date_str:
                try:
                    session_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except Exception:
                    pass

            if session_date is None:
                anno = seduta.get('anno')
                mese = seduta.get('mese')
                giorno = seduta.get('giorno')
                if anno and mese and giorno:
                    try:
                        session_date = datetime(int(anno), int(mese), int(giorno)).date()
                    except (ValueError, TypeError):
                        pass

            contents = {}
            dibattiti = soup.find_all('dibattito')

            for dibattito in dibattiti:
                titolo_tag = dibattito.find('titolo')
                if not titolo_tag or not titolo_tag.text.strip():
                    continue

                titolo = titolo_tag.text.strip()
                interventions = []

                self._gather_interventions(dibattito, interventions)

                if interventions:
                    contents[titolo] = interventions

            if not contents:
                logger.warning(f"No debates found in session {session_number}")
                return None

            return {
                'legislature': numero_legislatura,
                'session_number': numero_seduta,
                'date': session_date.isoformat() if session_date else None,
                'contents': contents,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching session {session_number}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing session {session_number}: {e}")
            return None

    def fetch_session_range(self, start: int, end: int, skip_existing: bool = True) -> int:
        logger.info(f"Fetching sessions {start} to {end}...")

        existing_sessions = set()
        if skip_existing:
            existing_sessions = set(self.get_existing_sessions())
            skipped = [s for s in range(start, end + 1) if s in existing_sessions]
            if skipped:
                logger.info(f"Skipping {len(skipped)} existing sessions: {skipped[:10]}{'...' if len(skipped) > 10 else ''}")

        count = 0
        skipped_count = 0
        total_attempted = end - start + 1
        for idx, session_num in enumerate(range(start, end + 1), 1):
            if skip_existing and session_num in existing_sessions:
                skipped_count += 1
                continue

            logger.info(f"Session {session_num} ({idx}/{total_attempted}) — fetching...")
            session_data = self.fetch_session(session_num)

            if session_data:
                if self.save_to_files:
                    filename = f"{session_data['legislature']}__{session_data['session_number']}.json"
                    file_path = self.output_path / filename
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(session_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"Session {session_num} — saved to {file_path.name} ({count + 1} new so far)")
                count += 1
            else:
                logger.warning(f"Session {session_num} — not found or empty, skipping")
            if session_num < end:
                sleep(self.rate_limit_delay)

        logger.info(f"Fetched {count} new sessions, skipped {skipped_count} existing, out of {total_attempted} attempted")
        return count

    def _build_session_url(self, session_number: int) -> str:
        return (
            f"{self.BASE_URL}?"
            f"sezione=assemblea&"
            f"tipoDoc=formato_xml&"
            f"tipologia=stenografico&"
            f"idNumero={session_number:04d}&"
            f"idLegislatura={self.legislature}"
        )

    def _gather_interventions(self, parent_tag, conversation_list: List[Dict]):
        for child in parent_tag.children:
            if child.name == 'intervento':
                intervention = self._parse_intervention(child)
                if intervention:
                    conversation_list.append(intervention)
            elif child.name == 'fase':
                self._gather_interventions(child, conversation_list)

    def _parse_intervention(self, intervento_tag) -> Optional[Dict]:
        try:
            nom_tag = intervento_tag.find("nominativo")
            speaker = nom_tag.get("cognomeNome") if nom_tag else "Unknown"

            text_blocks = []

            testo_tag = intervento_tag.find("testoXHTML")
            if testo_tag:
                text_blocks.append(testo_tag.get_text(strip=True))

            iv_tags = intervento_tag.find_all("interventoVirtuale")
            for iv in iv_tags:
                text_blocks.append(iv.get_text(strip=False))

            full_text = "\n".join(text_blocks).strip()

            if not full_text:
                return None

            return {
                "speaker": speaker,
                "text": full_text
            }
        except Exception as e:
            logger.debug(f"Error parsing intervention: {e}")
            return None

    def check_session_exists(self, session_number: int) -> bool:
        url = self._build_session_url(session_number)
        try:
            response = requests.head(url, timeout=3, allow_redirects=True)
            return response.status_code == 200
        except Exception:
            return False

    def get_existing_sessions(self) -> List[int]:
        if not self.output_path.exists():
            return []

        existing = []
        for file_path in self.output_path.glob(f"{self.legislature}__*.json"):
            try:
                parts = file_path.stem.split('__')
                if len(parts) == 2 and parts[0] == str(self.legislature):
                    session_num = int(parts[1])
                    existing.append(session_num)
            except (ValueError, IndexError):
                continue

        return sorted(existing)

    def get_last_session_number(self) -> Optional[int]:
        existing = self.get_existing_sessions()
        return max(existing) if existing else None

    def discover_latest_session(
        self,
        probe_start: Optional[int] = None,
        max_consecutive_missing: int = 5,
        max_probe: int = 200,
    ) -> Optional[int]:
        start = probe_start
        if start is None:
            last_local = self.get_last_session_number()
            start = (last_local + 1) if last_local is not None else 1
        logger.info(
            f"Discovering latest session (probing from {start}, max {max_probe} attempts; "
            f"will stop after 5 consecutive missing or at probe limit)"
        )
        latest = None
        consecutive_missing = 0
        for i in range(max_probe):
            session_num = start + i
            if self.check_session_exists(session_num):
                latest = session_num
                consecutive_missing = 0
            else:
                consecutive_missing += 1
                if consecutive_missing >= max_consecutive_missing:
                    logger.info(f"Stopped probing after {consecutive_missing} consecutive missing (last found: {latest})")
                    break
            if i > 0 and i % 10 == 0:
                logger.info(f"Probing... checked up to session {session_num} (latest so far: {latest})")
                sleep(0.2)
        if latest is not None:
            logger.info(f"Discovered latest session on server: {latest}")
        elif start is not None:
            logger.warning(f"Probe limit reached ({max_probe}); no session found in range [{start}, {start + max_probe - 1}]")
        return latest
