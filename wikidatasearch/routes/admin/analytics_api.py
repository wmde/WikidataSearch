"""Admin analytics API routes for the FastAPI application."""

import traceback
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from ...dependencies import verify_admin_auth
from ...services.logger import AnalyticsQueryService

router = APIRouter(
    prefix="/admin/analytics",
    tags=["Admin Analytics"],
    dependencies=[Depends(verify_admin_auth)],
)


@router.get("/page-views")
def page_views_route(
    start: datetime = Query(...),
    end: datetime = Query(...),
):
    """Return total page views between start and end datetimes."""
    try:
        start_utc, end_utc = AnalyticsQueryService.normalize_dt_interval(start, end)
        return AnalyticsQueryService.get_page_views(start_utc, end_utc)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/total-user-agents")
def total_user_agents_route(
    start: datetime = Query(...),
    end: datetime = Query(...),
    requests_threshold: int = Query(0, ge=0),
):
    """Return unique user agents between start and end datetimes."""
    try:
        start_utc, end_utc = AnalyticsQueryService.normalize_dt_interval(start, end)
        return AnalyticsQueryService.get_total_user_agents(
            start_utc,
            end_utc,
            requests_threshold=requests_threshold,
        )
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/total-requests")
def total_requests_route(
    start: datetime = Query(...),
    end: datetime = Query(...),
):
    """Return total requests between start and end datetimes."""
    try:
        start_utc, end_utc = AnalyticsQueryService.normalize_dt_interval(start, end)
        return AnalyticsQueryService.get_total_requests(start_utc, end_utc)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/total-requests-by-lang")
def total_requests_by_lang_route(
    start: datetime = Query(...),
    end: datetime = Query(...),
):
    """Return total requests by language between start and end datetimes."""
    try:
        start_utc, end_utc = AnalyticsQueryService.normalize_dt_interval(start, end)
        return AnalyticsQueryService.get_total_requests_by_lang(start_utc, end_utc)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/new-user-agents")
def new_user_agents_route(
    start: datetime = Query(...),
    end: datetime = Query(...),
    include_user_agents: bool = Query(False),
):
    """Return newly seen user agents between start and end datetimes."""
    try:
        start_utc, end_utc = AnalyticsQueryService.normalize_dt_interval(start, end)
        return AnalyticsQueryService.get_new_user_agents(
            start_utc,
            end_utc,
            include_user_agents=include_user_agents,
        )
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/consistent-user-agents")
def consistent_user_agents_route(
    start: datetime = Query(...),
    end: datetime = Query(...),
    consistent_days: int = Query(3, ge=1),
    include_user_agents: bool = Query(False),
):
    """Return consistent user agents between start and end datetimes."""
    try:
        start_utc, end_utc = AnalyticsQueryService.normalize_dt_interval(start, end)
        return AnalyticsQueryService.get_consistent_user_agents(
            start_utc,
            end_utc,
            consistent_days=consistent_days,
            include_user_agents=include_user_agents,
        )
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")
