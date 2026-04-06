"""OpenParlamento politicians analytics for filtered listings and lobby widgets."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Protocol, Sequence

from engine.core.config import settings
from engine.core.labels import normalize_key, normalize_space, party_key_from_raw, role_key_from_raw
from engine.services.dagospia_monitor import TTLCache


@dataclass(frozen=True)
class PoliticianRecord:
    politician_id: int | None
    slug: str
    full_name: str
    given_name: str
    family_name: str
    initials: str
    image: str | None
    birth_date: str | None
    birth_place: str | None
    days_in_parliament_label: str | None
    party_key: str
    party_label: str
    role_key: str
    role_label: str
    election_area: str | None
    supports_majority: bool | None
    current_mandate: dict[str, object]
    historical_mandates: tuple[dict[str, object], ...]
    current_positions: tuple[dict[str, object], ...]
    bio: str
    fidelity_current: float | None
    rebel_count: int
    key_votes_count: int
    confidence_votes_count: int
    n_voting: int
    n_present: int
    n_absent: int
    n_mission: int
    attendance_rate: float | None
    first_signer_count: int
    first_signer_recent_90d: int
    first_signer_is_law: int
    first_signer_first_step: int
    first_signer_to_begin: int
    first_signer_rejected: int
    parliamentary_positions_count: int
    source_date: date | None
    bills: tuple[dict[str, object], ...]
    recent_votes: tuple[dict[str, object], ...]


class OpenParlamentoRepository(Protocol):
    def load_persons(self) -> list[dict[str, object]]:
        """Load OpenParlamento person payloads."""


class FileOpenParlamentoRepository:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path(str(settings.OPENPARLAMENTO_DATA_PATH))

    def load_persons(self) -> list[dict[str, object]]:
        if not self.data_dir.exists():
            raise FileNotFoundError(f"OpenParlamento data path not found: {self.data_dir}")

        payloads: list[dict[str, object]] = []
        for file_path in sorted(self.data_dir.glob("*.json")):
            try:
                raw_payload = json.loads(file_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(raw_payload, dict):
                payloads.append(raw_payload)
        return payloads


def to_int(value: object, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_iso_date(raw_value: object) -> date | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def branch_to_institution(branch: object) -> str:
    normalized = normalize_space(str(branch or "").lower())
    if normalized in {"camera", "c"}:
        return "Camera dei Deputati"
    if normalized in {"senato", "s"}:
        return "Senato della Repubblica"
    return "Parlamento"


def compute_attendance_rate(n_present: int, n_voting: int) -> float | None:
    if n_voting <= 0:
        return None
    return round((n_present / n_voting) * 100, 2)


def initials_from_name(given_name: str, family_name: str) -> str:
    first = (given_name[:1] if given_name else "").upper()
    second = (family_name[:1] if family_name else "").upper()
    initials = (first + second).strip()
    return initials or "NA"


def summarize_bio(raw_payload: dict[str, object]) -> str:
    career_positions = raw_payload.get("carreer_positions")
    results = career_positions.get("results") if isinstance(career_positions, dict) else []
    first = results[0] if isinstance(results, list) and results else None

    if isinstance(first, dict):
        role = normalize_space(str(first.get("role") or ""))
        org = normalize_space(str(first.get("org") or ""))
        if role and org:
            return f"Esperienza in {role} presso {org}."
        if role:
            return f"Esperienza istituzionale come {role}."

    return "Profilo parlamentare attivo su dossier legislativi e istituzionali."


def current_mandate_from_payload(raw_payload: dict[str, object]) -> tuple[dict[str, object], str, str, str, str, str | None, bool | None]:
    current_roles = raw_payload.get("current_roles")
    parl = current_roles.get("parl") if isinstance(current_roles, dict) else None

    if not isinstance(parl, dict):
        mandate = {
            "institution": "Parlamento",
            "role": "Ruolo non disponibile",
            "start_date": None,
            "end_date": None,
            "election_area": None,
            "is_active": False,
        }
        return mandate, "NO-GROUP", "Senza gruppo", "NO-ROLE", "Ruolo non disponibile", None, None

    latest_group = parl.get("latest_group") if isinstance(parl.get("latest_group"), dict) else {}
    party_key, party_label = party_key_from_raw(latest_group.get("acronym") or latest_group.get("name"))
    role_key, role_label = role_key_from_raw(parl.get("role"))

    start_date = parl.get("start_date")
    end_date = parl.get("end_date")
    election_area = parl.get("election_area")
    supports_majority = parl.get("supports_majority")

    mandate = {
        "institution": branch_to_institution(latest_group.get("branch")),
        "role": role_label,
        "start_date": start_date,
        "end_date": end_date,
        "election_area": election_area,
        "is_active": end_date is None,
    }

    return (
        mandate,
        party_key,
        party_label,
        role_key,
        role_label,
        str(election_area) if election_area else None,
        supports_majority if isinstance(supports_majority, bool) else None,
    )


def historical_mandates_from_payload(raw_payload: dict[str, object]) -> tuple[dict[str, object], ...]:
    mandates: list[dict[str, object]] = []

    career_positions = raw_payload.get("carreer_positions")
    career_results = career_positions.get("results") if isinstance(career_positions, dict) else []
    if isinstance(career_results, list):
        for item in career_results:
            if not isinstance(item, dict):
                continue
            org = normalize_space(str(item.get("org") or ""))
            role = normalize_space(str(item.get("role") or ""))
            if not org and not role:
                continue
            mandates.append(
                {
                    "institution": org or "Istituzione non disponibile",
                    "role": role or "Ruolo non disponibile",
                    "start_date": item.get("date_start"),
                    "end_date": item.get("date_end"),
                }
            )

    prev_positions = raw_payload.get("parliamentary_positions_prev")
    prev_results = prev_positions.get("results") if isinstance(prev_positions, dict) else []
    if isinstance(prev_results, list):
        for item in prev_results:
            if not isinstance(item, dict):
                continue
            legislature = normalize_space(str(item.get("legislature") or ""))
            role = normalize_space(str(item.get("role") or ""))
            group = normalize_space(str(item.get("group") or ""))
            if not legislature and not role:
                continue
            mandates.append(
                {
                    "institution": f"Legislatura {legislature}" if legislature else "Precedente mandato",
                    "role": role or "Ruolo non disponibile",
                    "group": group,
                    "start_date": None,
                    "end_date": None,
                }
            )

    def sort_key(item: dict[str, object]) -> tuple[int, str]:
        end = parse_iso_date(item.get("end_date"))
        start = parse_iso_date(item.get("start_date"))
        if end:
            return int(end.strftime("%Y%m%d")), normalize_space(str(item.get("institution") or ""))
        if start:
            return int(start.strftime("%Y%m%d")), normalize_space(str(item.get("institution") or ""))
        return 0, normalize_space(str(item.get("institution") or ""))

    return tuple(sorted(mandates, key=sort_key, reverse=True)[:12])


def current_positions_from_payload(raw_payload: dict[str, object]) -> tuple[dict[str, object], ...]:
    positions_current = raw_payload.get("parliamentary_positions_current")
    results = positions_current.get("results") if isinstance(positions_current, dict) else []
    if not isinstance(results, list):
        return tuple()

    rows: list[dict[str, object]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "org": normalize_space(str(item.get("org") or "")) or "Organismo non disponibile",
                "role": normalize_space(str(item.get("role") or "")) or "Ruolo non disponibile",
                "date_start": item.get("date_start"),
                "date_end": item.get("date_end"),
                "original_org": normalize_space(str(item.get("original_org") or "")),
            }
        )

    def sort_key(item: dict[str, object]) -> tuple[int, str]:
        start = parse_iso_date(item.get("date_start"))
        end = parse_iso_date(item.get("date_end"))
        if start:
            return int(start.strftime("%Y%m%d")), normalize_space(str(item.get("org") or ""))
        if end:
            return int(end.strftime("%Y%m%d")), normalize_space(str(item.get("org") or ""))
        return 0, normalize_space(str(item.get("org") or ""))

    return tuple(sorted(rows, key=sort_key, reverse=True)[:30])


def recent_votes_from_payload(raw_payload: dict[str, object]) -> tuple[dict[str, object], ...]:
    vote_behaviours = raw_payload.get("vote_behaviours")
    if not isinstance(vote_behaviours, dict):
        return tuple()

    votes: list[dict[str, object]] = []
    for vote_type in ("key", "rebel", "confidence"):
        wrapper = vote_behaviours.get(vote_type)
        results = wrapper.get("results") if isinstance(wrapper, dict) else []
        if not isinstance(results, list):
            continue
        for row in results:
            if not isinstance(row, dict):
                continue
            sitting = row.get("sitting") if isinstance(row.get("sitting"), dict) else {}
            votes.append(
                {
                    "type": vote_type,
                    "id": row.get("id"),
                    "title": normalize_space(str(row.get("title") or "")) or "Votazione",
                    "voting_slug": row.get("voting_slug"),
                    "date": sitting.get("date"),
                    "branch": branch_to_institution(sitting.get("branch")),
                    "vote": row.get("vote"),
                    "group_vote": row.get("group_vote"),
                }
            )

    def sort_key(item: dict[str, object]) -> tuple[int, int]:
        parsed = parse_iso_date(item.get("date"))
        date_key = int(parsed.strftime("%Y%m%d")) if parsed else 0
        return date_key, to_int(item.get("id"))

    return tuple(sorted(votes, key=sort_key, reverse=True)[:20])


def bills_from_payload(raw_payload: dict[str, object], ref_date: date | None) -> tuple[tuple[dict[str, object], ...], int]:
    wrapper = raw_payload.get("first_signer_bills")
    results = wrapper.get("results") if isinstance(wrapper, dict) else []
    if not isinstance(results, list):
        return tuple(), 0

    rows: list[dict[str, object]] = []
    recent_count = 0
    threshold = (ref_date - timedelta(days=90)) if ref_date else None

    for item in results:
        if not isinstance(item, dict):
            continue
        parsed_date = parse_iso_date(item.get("date_presenting"))
        if threshold and parsed_date and parsed_date >= threshold:
            recent_count += 1

        rows.append(
            {
                "id": item.get("id"),
                "title": normalize_space(str(item.get("title") or "")),
                "identifier": item.get("identifier"),
                "date_presenting": item.get("date_presenting"),
                "branch": item.get("branch"),
                "status_phase": item.get("status", {}).get("phase") if isinstance(item.get("status"), dict) else None,
            }
        )

    return tuple(rows), recent_count


class PoliticiansService:
    def __init__(
        self,
        repository: OpenParlamentoRepository | None = None,
        cache_ttl_seconds: int = 120,
        now_provider: Callable[[], datetime] | None = None,
    ):
        self.repository = repository or FileOpenParlamentoRepository()
        self.cache = TTLCache(ttl_seconds=cache_ttl_seconds)
        self.now_provider = now_provider or datetime.now

    def _load_reference_date(self, payloads: Sequence[dict[str, object]]) -> date:
        dates: list[date] = []

        for payload in payloads:
            current_roles = payload.get("current_roles")
            if isinstance(current_roles, dict):
                parsed = parse_iso_date(current_roles.get("date"))
                if parsed:
                    dates.append(parsed)

            first_signer = payload.get("first_signer_bills")
            results = first_signer.get("results") if isinstance(first_signer, dict) else []
            if isinstance(results, list):
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    parsed = parse_iso_date(item.get("date_presenting"))
                    if parsed:
                        dates.append(parsed)

        return max(dates) if dates else self.now_provider().date()

    def _build_record(self, payload: dict[str, object], ref_date: date) -> PoliticianRecord:
        given_name = normalize_space(str(payload.get("given_name") or ""))
        family_name = normalize_space(str(payload.get("family_name") or ""))
        full_name = normalize_space(f"{given_name} {family_name}".strip()) or "Nome non disponibile"
        slug = normalize_space(str(payload.get("slug") or ""))

        (
            current_mandate,
            party_key,
            party_label,
            role_key,
            role_label,
            election_area,
            supports_majority,
        ) = current_mandate_from_payload(payload)

        fidelity = payload.get("fidelity") if isinstance(payload.get("fidelity"), dict) else {}
        fidelity_current = to_float(fidelity.get("current"))

        vote_behaviours = payload.get("vote_behaviours") if isinstance(payload.get("vote_behaviours"), dict) else {}
        rebel_count = to_int((vote_behaviours.get("rebel") or {}).get("count") if isinstance(vote_behaviours.get("rebel"), dict) else payload.get("n_rebels"))
        key_votes_count = to_int((vote_behaviours.get("key") or {}).get("count") if isinstance(vote_behaviours.get("key"), dict) else 0)
        confidence_votes_count = to_int((vote_behaviours.get("confidence") or {}).get("count") if isinstance(vote_behaviours.get("confidence"), dict) else 0)

        n_voting = to_int(payload.get("n_voting"))
        n_present = to_int(payload.get("n_present"))
        n_absent = to_int(payload.get("n_absent"))
        n_mission = to_int(payload.get("n_mission"))

        first_signer = payload.get("first_signer_bills") if isinstance(payload.get("first_signer_bills"), dict) else {}
        first_signer_count = to_int(first_signer.get("count"))
        bills, first_signer_recent_90d = bills_from_payload(payload, ref_date)

        current_positions = current_positions_from_payload(payload)
        recent_votes = recent_votes_from_payload(payload)

        return PoliticianRecord(
            politician_id=to_int(payload.get("id"), default=-1),
            slug=slug,
            full_name=full_name,
            given_name=given_name,
            family_name=family_name,
            initials=initials_from_name(given_name, family_name),
            image=str(payload.get("image")) if payload.get("image") else None,
            birth_date=str(payload.get("birth_date")) if payload.get("birth_date") else None,
            birth_place=normalize_space(str(payload.get("birth_place") or "")) or None,
            days_in_parliament_label=normalize_space(str(payload.get("parse_days_in_parliament") or "")) or None,
            party_key=party_key,
            party_label=party_label,
            role_key=role_key,
            role_label=role_label,
            election_area=election_area,
            supports_majority=supports_majority,
            current_mandate=current_mandate,
            historical_mandates=historical_mandates_from_payload(payload),
            current_positions=current_positions,
            bio=summarize_bio(payload),
            fidelity_current=fidelity_current,
            rebel_count=rebel_count,
            key_votes_count=key_votes_count,
            confidence_votes_count=confidence_votes_count,
            n_voting=n_voting,
            n_present=n_present,
            n_absent=n_absent,
            n_mission=n_mission,
            attendance_rate=compute_attendance_rate(n_present, n_voting),
            first_signer_count=first_signer_count,
            first_signer_recent_90d=first_signer_recent_90d,
            first_signer_is_law=to_int(first_signer.get("is_law")),
            first_signer_first_step=to_int(first_signer.get("first_step")),
            first_signer_to_begin=to_int(first_signer.get("to_begin")),
            first_signer_rejected=to_int(first_signer.get("rejected")),
            parliamentary_positions_count=to_int((payload.get("parliamentary_positions_current") or {}).get("count") if isinstance(payload.get("parliamentary_positions_current"), dict) else 0),
            source_date=parse_iso_date((payload.get("current_roles") or {}).get("date") if isinstance(payload.get("current_roles"), dict) else None),
            bills=bills,
            recent_votes=recent_votes,
        )

    def _load_records_cached(self) -> tuple[list[PoliticianRecord], date]:
        cached = self.cache.get("records")
        if cached is not None:
            return cached  # type: ignore[return-value]

        payloads = self.repository.load_persons()
        ref_date = self._load_reference_date(payloads)
        records = [self._build_record(payload, ref_date) for payload in payloads if isinstance(payload, dict)]
        records.sort(key=lambda item: item.full_name.lower())

        value = (records, ref_date)
        self.cache.set("records", value)
        return value

    def _match_search(self, record: PoliticianRecord, search: str) -> bool:
        if not search:
            return True
        haystack = f"{record.full_name} {record.given_name} {record.family_name} {record.slug}".lower()
        return search in haystack

    def _filter_records(self, records: Sequence[PoliticianRecord], search: str, party: str | None, role: str | None) -> list[PoliticianRecord]:
        normalized_search = normalize_space(search).lower()
        party_key = normalize_space(party or "")
        role_key = normalize_space(role or "")

        filtered: list[PoliticianRecord] = []
        for record in records:
            if not self._match_search(record, normalized_search):
                continue
            if party_key and record.party_key != party_key:
                continue
            if role_key and record.role_key != role_key:
                continue
            filtered.append(record)
        return filtered

    def _record_to_item(self, record: PoliticianRecord) -> dict[str, object]:
        historical_preview = list(record.historical_mandates[:2])
        return {
            "id": record.politician_id,
            "slug": record.slug,
            "full_name": record.full_name,
            "given_name": record.given_name,
            "family_name": record.family_name,
            "initials": record.initials,
            "image": record.image,
            "party": {
                "key": record.party_key,
                "label": record.party_label,
            },
            "role": record.role_label,
            "role_key": record.role_key,
            "election_area": record.election_area,
            "supports_majority": record.supports_majority,
            "current_mandate": record.current_mandate,
            "historical_preview": historical_preview,
            "historical_remaining": max(0, len(record.historical_mandates) - len(historical_preview)),
            "bio": record.bio,
            "metrics": {
                "fidelity_current": record.fidelity_current,
                "rebel_count": record.rebel_count,
                "key_votes_count": record.key_votes_count,
                "attendance_rate": record.attendance_rate,
                "first_signer_count": record.first_signer_count,
                "first_signer_recent_90d": record.first_signer_recent_90d,
                "parliamentary_positions_count": record.parliamentary_positions_count,
            },
        }

    def get_filters(self) -> dict[str, object]:
        records, _ = self._load_records_cached()

        party_counts: Counter[str] = Counter()
        role_counts: Counter[str] = Counter()
        party_labels: dict[str, str] = {}
        role_labels: dict[str, str] = {}

        for record in records:
            party_counts[record.party_key] += 1
            role_counts[record.role_key] += 1
            party_labels.setdefault(record.party_key, record.party_label)
            role_labels.setdefault(record.role_key, record.role_label)

        parties = [
            {
                "value": key,
                "label": party_labels.get(key, key),
                "count": count,
            }
            for key, count in sorted(party_counts.items(), key=lambda item: (-item[1], party_labels.get(item[0], item[0])))
        ]

        roles = [
            {
                "value": key,
                "label": role_labels.get(key, key),
                "count": count,
            }
            for key, count in sorted(role_counts.items(), key=lambda item: (-item[1], role_labels.get(item[0], item[0])))
        ]

        return {
            "counts": {
                "total_politicians": len(records),
                "total_parties": len(parties),
                "total_roles": len(roles),
            },
            "parties": parties,
            "roles": roles,
        }

    def get_list(
        self,
        search: str = "",
        party: str | None = None,
        role: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> dict[str, object]:
        records, _ = self._load_records_cached()
        safe_limit = max(1, min(limit, 2000))
        safe_offset = max(0, offset)

        filtered = self._filter_records(records, search=search, party=party, role=role)
        page_items = filtered[safe_offset : safe_offset + safe_limit]

        page = (safe_offset // safe_limit) + 1
        page_count = max(1, ((len(filtered) - 1) // safe_limit) + 1) if filtered else 1

        return {
            "filters": {
                "search": search,
                "party": party,
                "role": role,
            },
            "meta": {
                "total_records": len(records),
                "filtered_records": len(filtered),
                "offset": safe_offset,
                "limit": safe_limit,
                "page": page,
                "page_count": page_count,
                "has_prev": safe_offset > 0,
                "has_next": safe_offset + safe_limit < len(filtered),
            },
            "items": [self._record_to_item(item) for item in page_items],
        }

    def get_detail(self, slug: str | None = None, politician_id: int | None = None) -> dict[str, object]:
        records, ref_date = self._load_records_cached()
        normalized_slug = normalize_space(slug or "").lower()

        target: PoliticianRecord | None = None
        if normalized_slug:
            for record in records:
                if record.slug.lower() == normalized_slug:
                    target = record
                    break

        if target is None and politician_id is not None:
            for record in records:
                if record.politician_id == politician_id:
                    target = record
                    break

        if target is None:
            raise KeyError("Politician not found")

        mandates: list[dict[str, object]] = [
            {
                **target.current_mandate,
                "party": target.party_label,
                "is_current": True,
            }
        ]
        mandates.extend({**item, "is_current": False} for item in target.historical_mandates)

        def bill_sort_key(item: dict[str, object]) -> tuple[int, int]:
            parsed = parse_iso_date(item.get("date_presenting"))
            date_key = int(parsed.strftime("%Y%m%d")) if parsed else 0
            return date_key, to_int(item.get("id"))

        return {
            "id": target.politician_id,
            "slug": target.slug,
            "full_name": target.full_name,
            "given_name": target.given_name,
            "family_name": target.family_name,
            "initials": target.initials,
            "image": target.image,
            "birth_date": target.birth_date,
            "birth_place": target.birth_place,
            "days_in_parliament_label": target.days_in_parliament_label,
            "party": {
                "key": target.party_key,
                "label": target.party_label,
            },
            "role": target.role_label,
            "role_key": target.role_key,
            "election_area": target.election_area,
            "supports_majority": target.supports_majority,
            "bio": target.bio,
            "stats": {
                "fidelity_current": target.fidelity_current,
                "rebel_count": target.rebel_count,
                "key_votes_count": target.key_votes_count,
                "confidence_votes_count": target.confidence_votes_count,
                "n_voting": target.n_voting,
                "n_present": target.n_present,
                "n_absent": target.n_absent,
                "n_mission": target.n_mission,
                "attendance_rate": target.attendance_rate,
                "first_signer_count": target.first_signer_count,
                "first_signer_recent_90d": target.first_signer_recent_90d,
                "first_signer_is_law": target.first_signer_is_law,
                "first_signer_first_step": target.first_signer_first_step,
                "first_signer_to_begin": target.first_signer_to_begin,
                "first_signer_rejected": target.first_signer_rejected,
                "parliamentary_positions_count": target.parliamentary_positions_count,
            },
            "current_mandate": target.current_mandate,
            "mandates": mandates,
            "current_positions": list(target.current_positions[:16]),
            "recent_votes": list(target.recent_votes[:12]),
            "recent_bills": sorted(list(target.bills), key=bill_sort_key, reverse=True)[:12],
            "generated_at": datetime.combine(ref_date, datetime.min.time()).isoformat(),
        }

    def _opportunity_scores(self, records: Sequence[PoliticianRecord]) -> tuple[dict[str, float], float, float, float]:
        if not records:
            return {}, 1.0, 1.0, 1.0

        max_bills = max(record.first_signer_count for record in records) or 1
        max_positions = max(record.parliamentary_positions_count for record in records) or 1
        max_key_votes = max(record.key_votes_count for record in records) or 1

        scores: dict[str, float] = {}
        for record in records:
            bills_component = record.first_signer_count / max_bills
            positions_component = record.parliamentary_positions_count / max_positions
            key_votes_component = record.key_votes_count / max_key_votes
            majority_component = 1.0 if record.supports_majority is True else 0.9 if record.supports_majority is None else 0.85
            score = (0.4 * bills_component + 0.35 * positions_component + 0.25 * key_votes_component) * 100 * majority_component
            scores[record.slug] = round(score, 2)

        return scores, float(max_bills), float(max_positions), float(max_key_votes)

    def _build_opportunity_radar(self, filtered: Sequence[PoliticianRecord], score_map: dict[str, float]) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for record in filtered:
            items.append(
                {
                    "full_name": record.full_name,
                    "slug": record.slug,
                    "party": record.party_label,
                    "role": record.role_label,
                    "score": score_map.get(record.slug, 0.0),
                }
            )

        return sorted(items, key=lambda item: (float(item["score"]), item["full_name"]), reverse=True)[:8]

    def _build_party_matrix(self, filtered: Sequence[PoliticianRecord], score_map: dict[str, float]) -> list[dict[str, object]]:
        grouped: dict[str, list[PoliticianRecord]] = defaultdict(list)
        for record in filtered:
            grouped[record.party_key].append(record)

        rows: list[dict[str, object]] = []
        for _, members in grouped.items():
            party_label = members[0].party_label
            fidelity_values = [item.fidelity_current for item in members if item.fidelity_current is not None]
            fidelity_avg = round(sum(fidelity_values) / len(fidelity_values), 2) if fidelity_values else None

            rebel_rates = [(item.rebel_count / item.n_voting) * 100 for item in members if item.n_voting > 0]
            rebel_rate_avg = round(sum(rebel_rates) / len(rebel_rates), 2) if rebel_rates else None

            attendance_values = [item.attendance_rate for item in members if item.attendance_rate is not None]
            attendance_avg = round(sum(attendance_values) / len(attendance_values), 2) if attendance_values else None

            opportunity_avg = round(sum(score_map.get(item.slug, 0.0) for item in members) / len(members), 2)

            rows.append(
                {
                    "party": party_label,
                    "members": len(members),
                    "fidelity_avg": fidelity_avg,
                    "rebel_rate_avg": rebel_rate_avg,
                    "attendance_avg": attendance_avg,
                    "opportunity_score_avg": opportunity_avg,
                }
            )

        return sorted(rows, key=lambda item: (-item["members"], item["party"]))[:10]

    def _build_commission_distribution(self, filtered: Sequence[PoliticianRecord]) -> dict[str, object]:
        commission_party_counts: dict[str, Counter[str]] = defaultdict(Counter)

        for record in filtered:
            for position in record.current_positions:
                org = normalize_space(str(position.get("org") or ""))
                if not org:
                    continue
                commission_party_counts[org][record.party_label] += 1

        top_commissions = sorted(
            commission_party_counts.items(),
            key=lambda item: (-sum(item[1].values()), item[0]),
        )[:10]

        rows: list[dict[str, object]] = []
        for commission, counts in top_commissions:
            by_party = [{"party": party, "count": count} for party, count in counts.most_common(8)]
            rows.append(
                {
                    "commission": commission,
                    "total": int(sum(counts.values())),
                    "by_party": by_party,
                }
            )

        return {"rows": rows}

    def _build_legislative_momentum(self, filtered: Sequence[PoliticianRecord], ref_date: date) -> dict[str, object]:
        window_days = 90
        threshold = ref_date - timedelta(days=window_days)

        recent_bills: list[dict[str, object]] = []
        by_slug: Counter[str] = Counter()
        record_map = {record.slug: record for record in filtered}

        for record in filtered:
            for bill in record.bills:
                parsed_date = parse_iso_date(bill.get("date_presenting"))
                if parsed_date is None or parsed_date < threshold:
                    continue
                by_slug[record.slug] += 1
                recent_bills.append(
                    {
                        "title": bill.get("title"),
                        "identifier": bill.get("identifier"),
                        "date_presenting": bill.get("date_presenting"),
                        "status_phase": bill.get("status_phase"),
                        "politician": record.full_name,
                        "party": record.party_label,
                    }
                )

        recent_bills.sort(key=lambda item: str(item.get("date_presenting") or ""), reverse=True)

        top_politicians = []
        for slug, count in by_slug.most_common(8):
            record = record_map[slug]
            top_politicians.append(
                {
                    "full_name": record.full_name,
                    "slug": record.slug,
                    "party": record.party_label,
                    "recent_bills": count,
                    "total_bills": record.first_signer_count,
                }
            )

        return {
            "window_days": window_days,
            "reference_date": ref_date.isoformat(),
            "total_recent_bills": len(recent_bills),
            "top_politicians": top_politicians,
            "recent_bills": recent_bills[:10],
        }

    def get_widgets(
        self,
        search: str = "",
        party: str | None = None,
        role: str | None = None,
    ) -> dict[str, object]:
        records, ref_date = self._load_records_cached()
        filtered = self._filter_records(records, search=search, party=party, role=role)

        score_map, _, _, _ = self._opportunity_scores(filtered)

        unique_parties = {record.party_key for record in filtered}
        unique_roles = {record.role_key for record in filtered}
        unique_commissions = {
            normalize_space(str(position.get("org") or ""))
            for record in filtered
            for position in record.current_positions
            if normalize_space(str(position.get("org") or ""))
        }

        return {
            "generated_at": datetime.combine(ref_date, datetime.min.time()).isoformat(),
            "filters": {
                "search": search,
                "party": party,
                "role": role,
            },
            "counts": {
                "total_politicians": len(records),
                "filtered_politicians": len(filtered),
                "active_parties": len(unique_parties),
                "active_roles": len(unique_roles),
                "covered_commissions": len(unique_commissions),
            },
            "opportunity_radar": self._build_opportunity_radar(filtered, score_map),
            "party_reliability_matrix": self._build_party_matrix(filtered, score_map),
            "commission_distribution": self._build_commission_distribution(filtered),
            "legislative_momentum": self._build_legislative_momentum(filtered, ref_date),
        }
