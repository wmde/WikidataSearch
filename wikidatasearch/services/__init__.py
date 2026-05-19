"""Service-layer exports and lazy imports."""

from .search import HybridSearch

__all__ = ["HybridSearch", "Logger", "Feedback"]


def __getattr__(name: str):
    if name in {"Logger", "Feedback"}:
        from .logger import Feedback, Logger

        return {"Logger": Logger, "Feedback": Feedback}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
