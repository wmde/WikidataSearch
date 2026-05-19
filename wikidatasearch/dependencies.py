"""Dependencies for the FastAPI application."""

import base64
import binascii
import time

from fastapi import FastAPI, HTTPException, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import settings
from .services.logger import Logger


def user_agent_key(request: Request) -> str:
    """Rate limit key based on User-Agent.

    If User-Agent is missing or empty, fall back to a shared 'unknown' bucket.
    """
    ua = (request.headers.get("user-agent") or "").strip()

    if not ua:
        # All "no UA" clients share a single bucket
        return "ua:unknown"

    return f"ua:{ua}"


# Consider the user agent for rate limiting since WMcloud requests share the same IP.
limiter = Limiter(key_func=user_agent_key)


def verify_admin_auth(request: Request) -> str:
    """Verify HTTP Basic auth against for admin page."""
    expected = settings.ANALYTICS_API_SECRET
    if not expected:
        raise HTTPException(status_code=404, detail="Not found")

    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Basic "):
        decoded = None
    else:
        token = authorization[6:].strip()
        try:
            payload = base64.b64decode(token).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            payload = ""
        decoded = payload.split(":", 1) if ":" in payload else None

    if not decoded or decoded[1] != expected:
        raise HTTPException(
            status_code=401,
            detail="Incorrect admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return decoded[0] or "admin"


def require_descriptive_user_agent(request: Request) -> None:
    """Enforce a descriptive User-Agent and blocks generic HTTP clients."""
    ua = request.headers.get("user-agent", "").strip()
    if not ua or " " not in ua or len(ua) < 10:
        error = "A more descriptive User-Agent is required"
        Logger.add_request(request, 400, time.time(), error=error)
        raise HTTPException(status_code=400, detail=error)


def _logged_rate_limit_exceeded_handler(request: Request, exc: Exception):
    """Custom handler for rate limit breaches that logs the event."""
    error = str(exc) or "Rate limit exceeded"
    Logger.add_request(request, 429, time.time(), error=error)
    return _rate_limit_exceeded_handler(request, exc)


def register_rate_limit(app: FastAPI) -> None:
    """Attach SlowAPI handler. Call once in main.py after creating the app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _logged_rate_limit_exceeded_handler)
