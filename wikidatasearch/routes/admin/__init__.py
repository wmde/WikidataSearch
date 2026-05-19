"""Admin route modules exposed by the API package."""

from .analytics_api import router as analytics_api_router
from .analytics_ui import build_analytics_app

__all__ = ["analytics_api_router", "build_analytics_app"]
