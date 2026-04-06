"""QA service: retrieval-augmented generation for parliamentary questions."""

from __future__ import annotations

import re
from datetime import date, timedelta

from loguru import logger

from engine.core.config import settings
from engine.core.labels import PARTY_FRIENDLY_NAMES, detect_parties_from_text
from engine.search.opensearch_search import execute_search, execute_aggregations

# Italian time expressions -> days back
_TIME_PATTERNS = [
    (r"quest[ao] settimana", 7),
    (r"ultim[aoie] settimana", 7),
    (r"ultim[aoie] 7 giorni", 7),
    (r"ultimo mese", 30),
    (r"ultimi 30 giorni", 30),
    (r"oggi", 1),
    (r"ieri", 2),
]

SYSTEM_PROMPT = (
    "Sei un assistente esperto di politica parlamentare italiana. "
    "Rispondi alle domande dell'utente basandoti ESCLUSIVAMENTE sui dati parlamentari forniti come contesto.\n\n"
    "Regole:\n"
    "- Rispondi in italiano\n"
    "- Cita sempre le fonti: nome del parlamentare, data, e argomento della seduta\n"
    "- Se i dati non contengono informazioni sufficienti, dillo chiaramente\n"
    "- Non inventare informazioni non presenti nei dati\n"
    "- Sii conciso ma completo\n"
    "- Usa un tono professionale e oggettivo"
)


def _detect_parties(text: str) -> list[str]:
    return detect_parties_from_text(text)


def _detect_date_range(text: str) -> tuple[str | None, str | None]:
    lower = text.lower()
    today = date.today()

    # Dynamic pattern: "ultimi N giorni"
    m = re.search(r"ultimi (\d+) giorni", lower)
    if m:
        days = int(m.group(1))
        return (today - timedelta(days=days)).isoformat(), today.isoformat()

    for pattern, days in _TIME_PATTERNS:
        if re.search(pattern, lower):
            return (today - timedelta(days=days)).isoformat(), today.isoformat()

    return None, None


def _extract_search_terms(text: str) -> str:
    """Strip question scaffolding and party/time references to get core search terms."""
    noise = [
        r"chi ha parlato di\b", r"chi parla di\b",
        r"quanti discorsi\b", r"quali temi\b",
        r"confronta\b", r"confronto\b",
        r"mostrami\b", r"dimmi\b",
        r"quest[ao] settimana\b", r"ultimo mese\b",
        r"ultimi \d+ giorni\b", r"oggi\b", r"ieri\b",
        r"nell'ultimo\b", r"negli ultimi\b",
        r"ci sono stati\b", r"c'[eè] stato\b",
        r"sul tema\b", r"su[l]?\b", r"del\b", r"della\b",
        r"ha trattato\b", r"hanno trattato\b",
    ]

    result = text
    for p in noise:
        result = re.sub(p, " ", result, flags=re.IGNORECASE)
    for name in PARTY_FRIENDLY_NAMES:
        result = re.sub(re.escape(name), " ", result, flags=re.IGNORECASE)

    result = re.sub(r"[?\.,!]+", " ", result)
    return " ".join(result.split()).strip()


def _chunk_text(text: str, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            for sep in [". ", ".\n", "! ", "? "]:
                pos = text.rfind(sep, start + max_chars // 2, end)
                if pos > 0:
                    end = pos + 1
                    break
        chunks.append(text[start:end].strip())
        start = end - overlap
    return chunks


class QAService:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        from google import genai

        api_key = settings.GOOGLE_API_KEY
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY not set. Add it to .env or environment variables."
            )
        self._client = genai.Client(api_key=api_key)
        return self._client

    def answer(self, question: str) -> dict:
        # 1. Parse question
        parties = _detect_parties(question)
        date_from, date_to = _detect_date_range(question)
        search_terms = _extract_search_terms(question)

        logger.info(
            f"QA: terms='{search_terms}', parties={parties}, "
            f"dates={date_from}..{date_to}"
        )

        # 2. Retrieve from OpenSearch
        try:
            context_chunks, sources = self._retrieve(
                search_terms or question, parties, date_from, date_to
            )
        except Exception as e:
            # Keep returning a safe fallback answer, but log the full traceback.
            logger.exception(f"OpenSearch retrieval failed: {e}")
            return {
                "answer": "Errore nella ricerca dei dati parlamentari. Verifica che OpenSearch sia attivo.",
                "sources": [],
            }

        # 3. Get aggregations for count-type questions
        agg_context = ""
        if any(w in question.lower() for w in ["quanti", "quanto", "conteggio", "numero"]):
            agg_context = self._get_aggregation_context(
                search_terms or question, parties, date_from, date_to
            )

        if not context_chunks and not agg_context:
            return {
                "answer": (
                    "Non ho trovato dati parlamentari rilevanti per la tua domanda. "
                    "Prova a riformulare o a specificare meglio il periodo temporale."
                ),
                "sources": [],
            }

        # 4. Build prompt + call LLM
        context_text = "\n\n---\n\n".join(context_chunks)
        prompt = (
            f"Domanda dell'utente: {question}\n\n"
            f"CONTESTO - Estratti dai discorsi parlamentari alla Camera dei Deputati:\n"
            f"{context_text}\n"
            f"{agg_context}\n\n"
            f"Rispondi alla domanda basandoti sui dati sopra. "
            f"Cita i nomi dei parlamentari, le date e gli argomenti quando disponibili."
        )

        try:
            from google import genai

            client = self._get_client()
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.3,
                    max_output_tokens=2048,
                ),
            )
            answer_text = response.text
        except Exception as e:
            # Keep returning a safe fallback answer, but log the full traceback.
            logger.exception(f"LLM call failed: {e}")
            answer_text = self._build_fallback(context_chunks, agg_context)

        return {
            "answer": answer_text,
            "sources": sources,
        }

    def _retrieve(
        self,
        query: str,
        parties: list[str],
        date_from: str | None,
        date_to: str | None,
    ) -> tuple[list[str], list[dict]]:
        """Retrieve speech excerpts from OpenSearch."""
        # Comparison: separate queries per party
        if len(parties) >= 2 and query:
            all_chunks: list[str] = []
            all_sources: list[dict] = []
            for party in parties[:3]:
                response = execute_search(
                    q=query, party=party,
                    date_from=date_from, date_to=date_to, size=5,
                )
                c, s = self._extract_context(response, max_chunks=5)
                all_chunks.extend(c)
                all_sources.extend(s)
            return all_chunks, all_sources

        # Single query
        party_filter = parties[0] if len(parties) == 1 else None
        response = execute_search(
            q=query, party=party_filter,
            date_from=date_from, date_to=date_to, size=10,
        )
        return self._extract_context(response, max_chunks=10)

    def _extract_context(
        self, response: dict, max_chunks: int = 10,
    ) -> tuple[list[str], list[dict]]:
        chunks: list[str] = []
        sources: list[dict] = []

        for hit in response.get("hits", {}).get("hits", [])[:max_chunks]:
            src = hit["_source"]
            text = src.get("body", "")
            speaker = src.get("speaker_name", "Sconosciuto")
            party = src.get("party", "")
            date_str = src.get("date", "")
            topic = src.get("topic_title", "")

            text_parts = _chunk_text(text, max_chars=1500)
            for part in text_parts[:2]:
                header = f"[{speaker} ({party}) - {date_str} - {topic}]"
                chunks.append(f"{header}\n{part}")

            sources.append({
                "speech_id": src.get("doc_id"),
                "speaker_name": speaker,
                "party": party,
                "date": date_str,
                "topic": topic,
                "score": hit.get("_score"),
                "video_url": src.get("video_url"),
            })

        return chunks, sources

    def _get_aggregation_context(
        self, query: str, parties: list[str],
        date_from: str | None, date_to: str | None,
    ) -> str:
        try:
            party_filter = parties[0] if len(parties) == 1 else None
            response = execute_aggregations(
                q=query, party=party_filter,
                date_from=date_from, date_to=date_to,
            )
            total = response["hits"]["total"]["value"]
            aggs = response.get("aggregations", {})
            party_buckets = aggs.get("by_party", {}).get("buckets", [])
            speaker_buckets = aggs.get("by_speaker", {}).get("buckets", [])

            lines = [f"\n\nSTATISTICHE:\n- Totale discorsi trovati: {total}"]
            if party_buckets:
                lines.append(
                    "- Per partito: " +
                    ", ".join(f"{b['key']} ({b['doc_count']})" for b in party_buckets[:10])
                )
            if speaker_buckets:
                lines.append(
                    "- Per parlamentare: " +
                    ", ".join(f"{b['key']} ({b['doc_count']})" for b in speaker_buckets[:10])
                )
            return "\n".join(lines)
        except Exception as e:
            logger.exception(f"Aggregation query failed: {e}")
            return ""

    def _build_fallback(self, chunks: list[str], agg_context: str) -> str:
        parts = ["Impossibile generare una sintesi automatica (LLM non disponibile). Ecco i dati trovati:\n"]
        if agg_context:
            parts.append(agg_context.strip())
        if chunks:
            parts.append("\nEstratti dai discorsi piu rilevanti:")
            for i, chunk in enumerate(chunks[:5], 1):
                header = chunk.split("\n")[0]
                parts.append(f"{i}. {header}")
        return "\n".join(parts)
