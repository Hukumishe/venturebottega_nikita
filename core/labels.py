"""Unified party (and role) normalization for engine and search."""

from __future__ import annotations

import re

# Normalized key (uppercase, no punctuation) -> canonical OpenSearch/UI value
PARTY_ALIASES = {
    "FDI": "FDI",
    "FRATELLI D ITALIA": "FDI",
    "M5S": "M5S",
    "MOVIMENTO 5 STELLE": "M5S",
    "PD IDP": "PD-IDP",
    "PARTITO DEMOCRATICO ITALIA DEMOCRATICA E PROGRESSISTA": "PD-IDP",
    "FI PPE": "FI-PPE",
    "FI BP PPE": "FI-PPE",
    "LEGA": "LEGA",
    "LSP PSDAZ": "LEGA",
    "LSP PSD AZ": "LEGA",
    "MISTO": "MISTO",
    "IV C RE": "IV-C-RE",
    "AZ PER RE": "AZ-PER-RE",
    "AVS": "AVS",
    "NM N C U I M": "NM",
    "NM(N-C-U-I)-M": "NM",
}
# Raw value from DB (indexer) -> canonical
PARTY_INDEXER_ALIASES = {
    "FdI": "FDI",
    "FI-BP-PPE": "FI-PPE",
    "LSP-PSd'Az": "LEGA",
    "NM(N-C-U-I)-M": "NM",
}
# Search/query: user input (e.g. "PD", "FI") -> canonical
PARTY_SEARCH_ALIASES = {
    "PD": "PD-IDP",
    "FI": "FI-PPE",
    "LEGA": "LEGA",
    "FDI": "FDI",
    "M5S": "M5S",
    "AVS": "AVS",
    "MISTO": "MISTO",
    "NM": "NM",
}
# Friendly (lowercase) name in natural language -> canonical (for QA / NL)
PARTY_FRIENDLY_NAMES = {
    "pd": "PD-IDP",
    "partito democratico": "PD-IDP",
    "fratelli d'italia": "FDI",
    "fratelli d italia": "FDI",
    "fdi": "FDI",
    "forza italia": "FI-PPE",
    "fi": "FI-PPE",
    "lega": "LEGA",
    "movimento 5 stelle": "M5S",
    "m5s": "M5S",
    "cinque stelle": "M5S",
    "avs": "AVS",
    "alleanza verdi sinistra": "AVS",
    "misto": "MISTO",
    "italia viva": "IV-C-RE",
    "azione": "AZ-PER-RE",
    "noi moderati": "NM",
}

NON_ALNUM_PATTERN = re.compile(r"[^A-Z0-9]+")
WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_space(value: str) -> str:
    return WHITESPACE_PATTERN.sub(" ", (value or "").strip())


def normalize_key(value: str) -> str:
    collapsed = NON_ALNUM_PATTERN.sub(" ", (value or "").upper()).strip()
    return normalize_space(collapsed)


def normalize_party(raw_party: str | None) -> str | None:
    """Return canonical party key for OpenSearch (or None). Prefer indexer raw map, then normalized key."""
    if not raw_party:
        return None
    s = raw_party.strip()
    if s in PARTY_INDEXER_ALIASES:
        return PARTY_INDEXER_ALIASES[s]
    key = normalize_key(s)
    return PARTY_ALIASES.get(key, s)


def resolve_party_for_search(party: str | None) -> str | None:
    """Resolve user-facing party query to canonical value for OpenSearch."""
    if not party:
        return None
    upper = party.upper().strip()
    return PARTY_SEARCH_ALIASES.get(upper, party)


def party_key_from_raw(raw_party: str | None) -> tuple[str, str]:
    """Return (canonical_key, display_label) for politicians monitor / UI."""
    cleaned = normalize_space(raw_party or "")
    if not cleaned:
        return "NO-GROUP", "Senza gruppo"
    normalized = normalize_key(cleaned)
    alias = PARTY_ALIASES.get(normalized)
    if alias:
        return alias, alias
    return normalized.replace(" ", "-") or "NO-GROUP", cleaned


def role_key_from_raw(raw_role: str | None) -> tuple[str, str]:
    """Return (canonical_key, display_label) for role."""
    cleaned = normalize_space(raw_role or "")
    if not cleaned:
        return "NO-ROLE", "Ruolo non disponibile"
    normalized = normalize_key(cleaned)
    return normalized.replace(" ", "-"), cleaned


def detect_parties_from_text(text: str) -> list[str]:
    """Detect party names mentioned in natural language (e.g. question). Returns list of canonical keys."""
    lower = text.lower()
    found: list[str] = []
    for name, canonical in PARTY_FRIENDLY_NAMES.items():
        if name in lower and canonical not in found:
            found.append(canonical)
    return found
