"""FastAPI app exposing Dagospia monitor endpoints and static frontend."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import uvicorn
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from engine.services.dagospia_helpers import parse_keywords, parse_window_hours
from engine.services.dagospia_monitor import DagospiaService
from engine.services.politicians_monitor import PoliticiansService
from engine.services.speeches_service import SpeechesService
from agents.service import PolitiaAgentService


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None

app = FastAPI(
    title="Politia Dagospia API",
    version="0.1.0",
    description="Bridge layer between raw Dagospia dataset and frontend widgets.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

dagospia_service = DagospiaService(cache_ttl_seconds=60)
politicians_service = PoliticiansService(cache_ttl_seconds=120)
speeches_service = SpeechesService(cache_ttl_seconds=120)
agent_service = PolitiaAgentService()
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


@app.get("/api/dagospia/keywords")
def dagospia_keywords(limit: Annotated[int, Query(ge=1, le=500)] = 100):
    try:
        return dagospia_service.get_keywords(limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/dagospia/overview")
def dagospia_overview():
    try:
        return dagospia_service.get_overview()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/dagospia/widgets")
def dagospia_widgets(
    keywords: str | None = Query(default=None, description="Comma-separated keywords"),
    keyword: list[str] | None = Query(default=None, description="Repeated keyword query params"),
    window: str = Query(default="24h", description="Window size, e.g. 24h or 7d"),
    recent_limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    try:
        selected_keywords = parse_keywords(keywords=keywords, keyword=keyword)
        window_hours = parse_window_hours(window)
        return dagospia_service.get_widgets(
            selected_keywords=selected_keywords,
            window_hours=window_hours,
            recent_limit=recent_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/dagospia/cache/clear")
def clear_dagospia_cache():
    dagospia_service.cache.clear()
    return {"status": "ok"}


@app.get("/api/politicians/filters")
def politicians_filters():
    try:
        return politicians_service.get_filters()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/politicians/list")
def politicians_list(
    search: str = Query(default="", description="Search by person full name"),
    party: str | None = Query(default=None, description="Party canonical key"),
    role: str | None = Query(default=None, description="Current role canonical key"),
    limit: Annotated[int, Query(ge=1, le=2000)] = 1000,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    try:
        return politicians_service.get_list(
            search=search,
            party=party,
            role=role,
            limit=limit,
            offset=offset,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/politicians/widgets")
def politicians_widgets(
    search: str = Query(default="", description="Search by person full name"),
    party: str | None = Query(default=None, description="Party canonical key"),
    role: str | None = Query(default=None, description="Current role canonical key"),
):
    try:
        return politicians_service.get_widgets(
            search=search,
            party=party,
            role=role,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/politicians/detail")
def politicians_detail(
    slug: str | None = Query(default=None, description="Politician slug"),
    politician_id: int | None = Query(default=None, alias="id", description="Politician numeric id"),
):
    if not slug and politician_id is None:
        raise HTTPException(status_code=400, detail="Provide either slug or id.")
    try:
        return politicians_service.get_detail(slug=slug, politician_id=politician_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/politicians/cache/clear")
def clear_politicians_cache():
    politicians_service.cache.clear()
    return {"status": "ok"}


@app.get("/api/speeches/filters")
def speeches_filters():
    try:
        return speeches_service.get_filters()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/speeches/list")
def speeches_list(
    search: str = Query(default="", description="Search in text or speaker name"),
    party: str | None = Query(default=None, description="Filter by party"),
    date_from: str | None = Query(default=None, description="Start date (YYYY-MM-DD)"),
    date_to: str | None = Query(default=None, description="End date (YYYY-MM-DD)"),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    try:
        return speeches_service.get_list(
            search=search,
            party=party,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/speeches/widgets")
def speeches_widgets(
    search: str = Query(default="", description="Search in text or speaker name"),
    party: str | None = Query(default=None, description="Filter by party"),
    date_from: str | None = Query(default=None, description="Start date (YYYY-MM-DD)"),
    date_to: str | None = Query(default=None, description="End date (YYYY-MM-DD)"),
):
    try:
        return speeches_service.get_widgets(
            search=search,
            party=party,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/speeches/detail")
def speeches_detail(
    speech_id: str = Query(description="Speech ID"),
):
    try:
        return speeches_service.get_detail(speech_id=speech_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/speeches/cache/clear")
def clear_speeches_cache():
    speeches_service.cache.clear()
    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest):
    try:
        return agent_service.answer(request.message, history=request.history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/", include_in_schema=False)
def frontend_index():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend index not found.")
    return FileResponse(index_path)


@app.get("/monitor", include_in_schema=False)
def frontend_monitor():
    monitor_path = FRONTEND_DIR / "monitor.html"
    if not monitor_path.exists():
        raise HTTPException(status_code=404, detail="Frontend monitor page not found.")
    return FileResponse(monitor_path)


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


def run() -> None:
    uvicorn.run("engine.api:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
