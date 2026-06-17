"""Unit tests for database initialization job."""

import importlib
import sys
import types


class FakeInspector:
    """Minimal inspector that reports selected tables as existing."""

    def __init__(self, existing_tables, existing_indexes=None):
        """Store existing table names."""
        self.existing_tables = set(existing_tables)
        self.existing_indexes = existing_indexes or {}

    def has_table(self, table_name):
        """Return whether a table exists."""
        return table_name in self.existing_tables

    def get_indexes(self, table_name):
        """Return existing index metadata for a table."""
        return [{"name": index_name} for index_name in self.existing_indexes.get(table_name, set())]


class FakeConnection:
    """Connection that records executed statements."""

    def __init__(self):
        """Initialize captured statements."""
        self.statements = []

    def execute(self, statement):
        """Record executed SQL."""
        self.statements.append(str(statement))


class FakeBegin:
    """Context manager returned by fake engine."""

    def __init__(self, connection):
        """Store connection."""
        self.connection = connection

    def __enter__(self):
        """Return fake connection."""
        return self.connection

    def __exit__(self, *_args):
        """Exit cleanly."""
        return False


class FakeEngine:
    """Minimal engine with transaction support."""

    def __init__(self):
        """Create reusable fake connection."""
        self.connection = FakeConnection()

    def begin(self):
        """Return transaction context."""
        return FakeBegin(self.connection)


class FakeIndex:
    """Minimal index object that records create calls."""

    def __init__(self, name):
        """Store the fake index name."""
        self.name = name
        self.calls = []

    def create(self, bind, checkfirst):
        """Record index creation options."""
        self.calls.append({"bind": bind, "checkfirst": checkfirst})


def load_initialize_job(monkeypatch, existing_tables, existing_indexes=None):
    """Import initialize job with database dependencies stubbed."""
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
    monkeypatch.delitem(sys.modules, "jobs.initialize_database", raising=False)
    monkeypatch.delitem(sys.modules, "wikidatasearch.services.logger.database", raising=False)

    initialize_job = importlib.import_module("jobs.initialize_database")
    monkeypatch.setattr(
        initialize_job,
        "sqlalchemy_inspect",
        lambda _engine: FakeInspector(existing_tables, existing_indexes),
    )
    return initialize_job


def test_sync_indexes_creates_model_indexes_and_drops_obsolete_managed_indexes(monkeypatch):
    """Create model indexes and drop obsolete managed indexes."""
    initialize_job = load_initialize_job(
        monkeypatch,
        existing_tables={"requests"},
        existing_indexes={
            "requests": {
                "ix_requests_route",
                "ix_requests_route_timestamp",
                "custom_keep_me",
            }
        },
    )
    fake_engine = FakeEngine()
    requests_index = FakeIndex("ix_requests_route_timestamp")
    user_agent_index = FakeIndex("ix_user_agent_history_query_first_seen")
    requests_table = types.SimpleNamespace(name="requests", indexes=[requests_index])
    user_agent_table = types.SimpleNamespace(name="user_agent_history", indexes=[user_agent_index])

    initialize_job.Logger = types.SimpleNamespace(__table__=requests_table)
    initialize_job.UserAgents = types.SimpleNamespace(__table__=user_agent_table)
    initialize_job.engine = fake_engine

    initialize_job.sync_indexes()

    assert requests_index.calls == [{"bind": fake_engine, "checkfirst": True}]
    assert user_agent_index.calls == []
    assert fake_engine.connection.statements == ["DROP INDEX ix_requests_route ON requests"]


def test_initialize_database_syncs_indexes_after_history_build(monkeypatch):
    """Run index sync after building user-agent history."""
    initialize_job = load_initialize_job(monkeypatch, existing_tables=set())
    calls = []
    fake_metadata = types.SimpleNamespace(create_all=lambda _engine: calls.append("create_all"))

    initialize_job.Base = types.SimpleNamespace(metadata=fake_metadata)
    initialize_job.UserAgents = types.SimpleNamespace(
        __tablename__="user_agent_history",
        build_from_requests=lambda: calls.append("build_history"),
    )
    monkeypatch.setattr(initialize_job, "sync_indexes", lambda: calls.append("sync_indexes"))

    assert initialize_job.initialize_database()
    assert calls == ["create_all", "build_history", "sync_indexes"]
