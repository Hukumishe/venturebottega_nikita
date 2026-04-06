import json
from pathlib import Path
from time import sleep
from typing import List, Dict, Optional

import requests
from loguru import logger
from sqlalchemy.orm import Session

from engine.core.config import settings
from engine.core.db import Person


class PoliticiansFetcher:
    BASE_URL = "https://service.opdm.openpolis.io/api-openparlamento/v1/19"
    PERSONS_LIST_URL = f"{BASE_URL}/persons/"

    def __init__(
        self,
        db: Optional[Session] = None,
        save_to_files: bool = False,
        output_path: Optional[Path] = None,
        rate_limit_delay: float = 1.5,
    ):
        self.db = db
        self.save_to_files = save_to_files
        self.output_path = output_path or Path(settings.RAW_DATA_PATH) / "openparlamento"
        self.rate_limit_delay = rate_limit_delay

        if self.save_to_files:
            self.output_path.mkdir(parents=True, exist_ok=True)

    def fetch_all_persons(self) -> int:
        logger.info("Starting to fetch persons from OpenParlamento API...")

        all_persons = []
        page_url = f"{self.PERSONS_LIST_URL}?page=1"
        page_num = 1

        while page_url:
            try:
                logger.info(f"Fetching page {page_num}...")
                response = requests.get(page_url, timeout=20)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                all_persons.extend(results)
                logger.info(f"Page {page_num}: Found {len(results)} persons (total: {len(all_persons)})")

                page_url = data.get("next")
                page_num += 1

                if page_url:
                    sleep(self.rate_limit_delay)

            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching page {page_url}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break

        logger.info(f"Fetched {len(all_persons)} persons from list endpoint")

        total_fetched = 0
        for idx, person_summary in enumerate(all_persons, 1):
            try:
                person_url = person_summary.get("url")
                if not person_url:
                    logger.warning(f"Person {idx} has no URL, skipping")
                    continue

                person_data = self._fetch_person_details(person_url)
                if person_data:
                    if self.db:
                        self._save_to_database(person_data)

                    if self.save_to_files:
                        self._save_to_file(person_data)

                    total_fetched += 1

                    if idx % 50 == 0:
                        logger.info(f"Processed {idx}/{len(all_persons)} persons")

                    sleep(self.rate_limit_delay)

            except Exception as e:
                logger.error(f"Error processing person {idx}: {e}")
                continue

        logger.info(f"Successfully fetched {total_fetched} person details")
        return total_fetched

    def _fetch_person_details(self, person_url: str) -> Optional[Dict]:
        try:
            response = requests.get(person_url, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching person details from {person_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching person: {e}")
            return None

    def _save_to_database(self, person_data: Dict):
        if not self.db:
            return

        try:
            person_id = f"op_{person_data.get('id', 'unknown')}"

            existing = self.db.query(Person).filter(Person.person_id == person_id).first()
            if existing:
                self._update_person(existing, person_data)
            else:
                person = self._create_person(person_id, person_data)
                self.db.add(person)

            if not hasattr(self, '_save_count'):
                self._save_count = 0
            self._save_count += 1

            if self._save_count % 50 == 0:
                self.db.commit()
                logger.debug(f"Committed {self._save_count} persons to database")
        except Exception as e:
            logger.error(f"Error saving person to database: {e}")
            self.db.rollback()

    def _save_to_file(self, person_data: Dict):
        if not self.save_to_files:
            return

        try:
            family_name = person_data.get('family_name', 'Unknown')
            given_name = person_data.get('given_name', 'Unknown')
            filename = f"{family_name}__{given_name}_openparlamento.json"
            filename = filename.replace('/', '_').replace('\\', '_')

            file_path = self.output_path / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(person_data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Saved to {file_path}")
        except Exception as e:
            logger.error(f"Error saving person to file: {e}")

    def _create_person(self, person_id: str, data: Dict) -> Person:
        family_name = data.get('family_name', '')
        given_name = data.get('given_name', '')
        full_name = f"{family_name} {given_name}".strip()

        party = None
        roles = []
        if 'current_roles' in data and data['current_roles']:
            parl_role = data['current_roles'].get('parl', {})
            if parl_role:
                latest_group = parl_role.get('latest_group', {})
                party = latest_group.get('acronym') or latest_group.get('name')
                roles.append({
                    'role': parl_role.get('role'),
                    'start_date': parl_role.get('start_date'),
                    'end_date': parl_role.get('end_date'),
                    'party': party,
                })

        source_ids = {
            'openparlamento': f"p{data.get('id', '')}",
            'slug': data.get('slug'),
        }

        return Person(
            person_id=person_id,
            full_name=full_name,
            family_name=family_name,
            given_name=given_name,
            party=party,
            roles=roles,
            source_ids=source_ids,
            birth_date=data.get('birth_date'),
            birth_place=data.get('birth_place'),
            image_url=data.get('image'),
            slug=data.get('slug'),
            raw_data=data,
        )

    def _update_person(self, person: Person, data: Dict):
        if not person.family_name:
            person.family_name = data.get('family_name', '')
        if not person.given_name:
            person.given_name = data.get('given_name', '')
        if not person.full_name:
            person.full_name = f"{person.family_name} {person.given_name}".strip()

        if 'current_roles' in data and data['current_roles']:
            parl_role = data['current_roles'].get('parl', {})
            if parl_role:
                latest_group = parl_role.get('latest_group', {})
                party = latest_group.get('acronym') or latest_group.get('name')
                if party:
                    person.party = party

        if person.source_ids:
            person.source_ids['openparlamento'] = f"p{data.get('id', '')}"
        else:
            person.source_ids = {
                'openparlamento': f"p{data.get('id', '')}",
                'slug': data.get('slug'),
            }

        person.raw_data = data

    def check_api_health(self) -> bool:
        try:
            response = requests.get(self.PERSONS_LIST_URL, params={"page": 1}, timeout=8)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False

    # --- Processing from files ---

    def process_all_from_files(self) -> int:
        data_path = Path(settings.OPENPARLAMENTO_DATA_PATH) if settings.OPENPARLAMENTO_DATA_PATH else None
        if not data_path or not data_path.exists():
            logger.warning(f"OpenParlamento data path not found: {data_path}")
            return 0

        if not self.db:
            logger.error("No database session provided for processing")
            return 0

        count = 0
        json_files = list(data_path.glob("*.json"))
        logger.info(f"Found {len(json_files)} OpenParlamento JSON files")

        for json_file in json_files:
            try:
                self.process_file(json_file)
                count += 1
                if count % 50 == 0:
                    logger.info(f"Processed {count}/{len(json_files)} files")
                    self.db.commit()
            except Exception as e:
                logger.error(f"Error processing {json_file}: {e}")
                self.db.rollback()
                continue

        self.db.commit()
        logger.info(f"Successfully processed {count} OpenParlamento files")
        return count

    def process_file(self, file_path: Path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        person_id = f"op_{data.get('id', 'unknown')}"

        existing = self.db.query(Person).filter(Person.person_id == person_id).first()
        if existing:
            self._update_person(existing, data)
        else:
            person = self._create_person(person_id, data)
            self.db.add(person)
