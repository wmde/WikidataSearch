"""Frontend and utility routes for the public API UI."""

import time

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi_cache.decorator import cache

from ..config import SEARCH, settings
from ..dependencies import limiter
from ..services.logger import Feedback, Logger

router = APIRouter(include_in_schema=False)


@router.get("/")
@limiter.limit(settings.RATE_LIMIT)
async def root(request: Request, background_tasks: BackgroundTasks):
    """Serve the frontend index page."""
    background_tasks.add_task(Logger.add_request, request, 200, time.time())
    return FileResponse(f"{settings.FRONTEND_STATIC_DIR}/index.html")


def mount_static(app):
    """Mount the frontend static assets on the FastAPI app."""
    app.mount("/assets", StaticFiles(directory=f"{settings.FRONTEND_STATIC_DIR}/assets"), name="frontend-assets")


@router.get("/languages", summary="Supported languages")
@cache(expire=settings.CACHE_TTL)
@limiter.limit(settings.RATE_LIMIT)
async def languages(request: Request):
    """Return available vector-database and translated language codes."""
    vectordb_langs = set(SEARCH.vectordb_langs)
    other_langs = set(SEARCH.translator.mint_langs) - vectordb_langs
    return {
        "vectordb_langs": sorted(vectordb_langs),
        "other_langs": sorted(other_langs),
    }


@router.post("/feedback", include_in_schema=False)
@limiter.limit(settings.RATE_LIMIT)
async def feedback(
    request: Request,
    query: str = Query(..., examples=["testing"]),
    id: str = Query(..., examples=["Q5"]),
    sentiment: str = Query(..., examples=["up"]),
    index: int = Query(..., examples=[0]),
):
    """Record user feedback for a search result."""
    Feedback.add_feedback(query, id, sentiment, index)
    return True
