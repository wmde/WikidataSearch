"""Unit tests for analytics query user-agent fallback behavior."""

from datetime import datetime

import pandas as pd
import pytest

import wikidatasearch.services.logger.analytics_queries as analytics_queries
from wikidatasearch.services.logger.analytics_queries import AnalyticsQueryService


class _DummyConnection:
    """No-op connection context manager for stubbing SQLAlchemy engine."""

    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyEngine:
    """No-op engine that returns a dummy context manager."""

    def connect(self):
        return _DummyConnection()


def _stub_read_sql(monkeypatch, df: pd.DataFrame) -> None:
    """Patch read_sql and engine to return a predefined DataFrame."""

    def _fake_read_sql(*_args, **_kwargs):
        return df.copy()

    monkeypatch.setattr(analytics_queries, "engine", _DummyEngine())
    monkeypatch.setattr(analytics_queries.pd, "read_sql", _fake_read_sql)


def _capture_sql(monkeypatch, df: pd.DataFrame) -> dict[str, str]:
    """Patch read_sql and capture the SQL text used by the query."""
    captured: dict[str, str] = {"query": ""}

    def _fake_read_sql(sql, *_args, **_kwargs):
        captured["query"] = str(sql)
        return df.copy()

    monkeypatch.setattr(analytics_queries, "engine", _DummyEngine())
    monkeypatch.setattr(analytics_queries.pd, "read_sql", _fake_read_sql)
    return captured


def _assert_vector_routes_and_status_filter(sql_text: str) -> None:
    """Assert vector-route queries exclude 400 and 422 statuses."""
    assert f"route IN {AnalyticsQueryService.VECTOR_QUERY_ROUTES_SQL}" in sql_text
    assert "status NOT IN (400, 422)" in sql_text
    assert "status <> 422" not in sql_text


def test_get_total_user_agents_prefers_original_user_agent(monkeypatch):
    """Return original user agents when available, otherwise fallback to hash."""
    df = pd.DataFrame(
        [
            {"client": "browser", "user_agent_hash": "hash_browser", "user_agent_value": "Mozilla/5.0 X"},
            {"client": "api", "user_agent_hash": "hash_api_a", "user_agent_value": "WikiBot/1.0"},
            {"client": "api", "user_agent_hash": "hash_api_b", "user_agent_value": "hash_api_b"},
        ]
    )
    _stub_read_sql(monkeypatch, df)

    out = AnalyticsQueryService.get_total_user_agents(
        datetime(2026, 4, 1),
        datetime(2026, 4, 23),
        include_user_agents=True,
    )

    assert out["browser"] == 1
    assert out["api"] == 2
    assert out["total"] == 3
    assert out["user_agents"] == ["Mozilla/5.0 X", "WikiBot/1.0", "hash_api_b"]


def test_get_new_user_agents_prefers_original_user_agent(monkeypatch):
    """Return original user agents in new-user-agents when available."""
    df = pd.DataFrame(
        [
            {"user_agent_hash": "hash_a", "user_agent_value": "CustomAgent/2.0"},
            {"user_agent_hash": "hash_b", "user_agent_value": "hash_b"},
        ]
    )
    _stub_read_sql(monkeypatch, df)

    out = AnalyticsQueryService.get_new_user_agents(
        datetime(2026, 4, 1),
        datetime(2026, 4, 23),
        include_user_agents=True,
    )

    assert out["total"] == 2
    assert out["user_agents"] == ["CustomAgent/2.0", "hash_b"]


def test_get_new_user_agents_count_only_uses_total_query(monkeypatch):
    """Return only total count when include_user_agents is False."""
    df = pd.DataFrame([{"total": 7}])
    _stub_read_sql(monkeypatch, df)

    out = AnalyticsQueryService.get_new_user_agents(
        datetime(2026, 4, 1),
        datetime(2026, 4, 23),
        include_user_agents=False,
    )

    assert out == {"total": 7}


def test_get_consistent_user_agents_prefers_original_user_agent(monkeypatch):
    """Return original user agents in consistent-user-agents when available."""
    df = pd.DataFrame(
        [
            {"user_agent_hash": "hash_a", "user_agent_value": "AgentA/1.2"},
            {"user_agent_hash": "hash_b", "user_agent_value": "hash_b"},
            {"user_agent_hash": "hash_c", "user_agent_value": "AgentC/3.4"},
        ]
    )
    _stub_read_sql(monkeypatch, df)

    out = AnalyticsQueryService.get_consistent_user_agents(
        datetime(2026, 4, 1),
        datetime(2026, 4, 23),
        include_user_agents=True,
    )

    assert out["total"] == 3
    assert out["user_agents"] == ["AgentA/1.2", "AgentC/3.4", "hash_b"]


def test_get_consistent_user_agents_count_only_uses_total_query(monkeypatch):
    """Return only total count when include_user_agents is False."""
    df = pd.DataFrame([{"total": 4}])
    _stub_read_sql(monkeypatch, df)

    out = AnalyticsQueryService.get_consistent_user_agents(
        datetime(2026, 4, 1),
        datetime(2026, 4, 23),
        include_user_agents=False,
    )

    assert out == {"total": 4}


@pytest.mark.parametrize(
    "call",
    [
        lambda: AnalyticsQueryService.get_total_user_agents(
            datetime(2026, 4, 1),
            datetime(2026, 4, 23),
            include_user_agents=True,
        ),
        lambda: AnalyticsQueryService.get_total_user_agents(
            datetime(2026, 4, 1),
            datetime(2026, 4, 23),
            include_user_agents=False,
        ),
        lambda: AnalyticsQueryService.get_total_requests(
            datetime(2026, 4, 1),
            datetime(2026, 4, 23),
        ),
        lambda: AnalyticsQueryService.get_total_requests_by_lang(
            datetime(2026, 4, 1),
            datetime(2026, 4, 23),
        ),
        lambda: AnalyticsQueryService.get_new_user_agents(
            datetime(2026, 4, 1),
            datetime(2026, 4, 23),
            include_user_agents=True,
        ),
        lambda: AnalyticsQueryService.get_new_user_agents(
            datetime(2026, 4, 1),
            datetime(2026, 4, 23),
            include_user_agents=False,
        ),
        lambda: AnalyticsQueryService.get_consistent_user_agents(
            datetime(2026, 4, 1),
            datetime(2026, 4, 23),
            include_user_agents=True,
        ),
        lambda: AnalyticsQueryService.get_consistent_user_agents(
            datetime(2026, 4, 1),
            datetime(2026, 4, 23),
            include_user_agents=False,
        ),
    ],
)
def test_vector_route_queries_exclude_400_and_422(monkeypatch, call):
    """Ensure all vector-route analytics queries exclude 400 and 422."""
    captured = _capture_sql(monkeypatch, pd.DataFrame())
    call()
    _assert_vector_routes_and_status_filter(captured["query"])
