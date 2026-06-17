"""Unit tests for request-log aggregation."""

import importlib
import sys
import types

import sqlalchemy
from sqlalchemy.sql.schema import MetaData


class FakeResult:
    """Minimal SQLAlchemy result with a row count."""

    rowcount = 2


class FakeConnection:
    """Capture SQL statements executed by the logger service."""

    def __init__(self):
        """Initialize an empty statement list."""
        self.statements = []

    def execute(self, statement, _params=None):
        """Capture one SQL statement."""
        self.statements.append(str(statement))
        return FakeResult()


class FakeBegin:
    """Context manager returned by the fake engine."""

    def __init__(self, connection):
        """Store the fake connection."""
        self.connection = connection

    def __enter__(self):
        """Return the fake connection."""
        return self.connection

    def __exit__(self, *_args):
        """Leave the fake transaction context."""
        return False


class FakeEngine:
    """Minimal engine supporting transactional execution."""

    def __init__(self):
        """Initialize one reusable fake connection."""
        self.connection = FakeConnection()

    def begin(self):
        """Return a fake transaction context."""
        return FakeBegin(self.connection)


class FakeInspector:
    """Minimal database inspector."""

    def __init__(self, table_exists):
        """Store whether user-agent history already exists."""
        self.table_exists = table_exists

    def has_table(self, _name):
        """Return the configured table-existence result."""
        return self.table_exists


def load_logger(monkeypatch, table_exists=False):
    """Import the logger service with database operations stubbed."""
    fake_engine = FakeEngine()
    fake_config = types.ModuleType("wikidatasearch.config")
    fake_config.settings = types.SimpleNamespace(
        DB_HOST="db",
        DB_NAME="logs",
        DB_USER="user",
        DB_PASS="pass",
        DB_PORT=3306,
        LOG_DB_POOL_SIZE=1,
        LOG_DB_MAX_OVERFLOW=0,
        LOG_DB_POOL_TIMEOUT=1,
        LOG_DB_POOL_RECYCLE=1,
    )

    monkeypatch.setitem(sys.modules, "wikidatasearch.config", fake_config)
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_args, **_kwargs: fake_engine)
    monkeypatch.setattr(sqlalchemy, "inspect", lambda _engine: FakeInspector(table_exists))
    monkeypatch.setattr(MetaData, "create_all", lambda *_args, **_kwargs: None)
    monkeypatch.delitem(sys.modules, "wikidatasearch.services.logger", raising=False)
    monkeypatch.delitem(sys.modules, "wikidatasearch.services.logger.database", raising=False)

    return importlib.import_module("wikidatasearch.services.logger"), fake_engine.connection


def test_build_from_requests_uses_idempotent_merge(monkeypatch):
    """Build available logs without deleting or double-adding history."""
    logger, connection = load_logger(monkeypatch)
    connection.statements.clear()

    assert logger.UserAgents.build_from_requests() == 2
    assert logger.UserAgents.build_from_requests() == 2
    assert len(connection.statements) == 2
    assert connection.statements[0] == connection.statements[1]

    statement = connection.statements[0]
    assert "DELETE FROM user_agent_history" not in statement
    assert "ON DUPLICATE KEY UPDATE" in statement
    assert "first_seen = LEAST(first_seen, VALUES(first_seen))" in statement
    assert "last_seen = GREATEST(last_seen, VALUES(last_seen))" in statement
    assert "on_browser = on_browser OR VALUES(on_browser)" in statement
    assert "distinct_days = GREATEST(distinct_days, VALUES(distinct_days))" in statement
    assert "total_requests = GREATEST(total_requests, VALUES(total_requests))" in statement


def test_existing_history_skips_automatic_full_log_scan(monkeypatch):
    """Avoid scanning all request logs on ordinary process startup."""
    _logger, connection = load_logger(monkeypatch, table_exists=True)

    assert connection.statements == []
