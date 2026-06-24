"""Unit tests for the redacted request archive job."""

import importlib
import sys
import types

from sqlalchemy import JSON, Boolean, Column, Integer, MetaData, Table
from sqlalchemy.dialects import mysql
from sqlalchemy.sql.dml import Delete


class FakeResult:
    """Minimal result yielding mapping rows."""

    def __init__(self, rows):
        """Store rows returned by the fake query."""
        self.rows = rows

    def mappings(self):
        """Return the stored mapping rows."""
        return self.rows


class FakeConnection:
    """Capture archive queries and return configured batches."""

    def __init__(self, batches):
        """Store batches and executed delete statements."""
        self.batches = iter(batches)
        self.delete_statements = []
        self.select_statements = []

    def scalar(self, _statement):
        """Return the highest redacted ID."""
        return 3

    def execute(self, statement):
        """Return the next batch or capture a delete."""
        if isinstance(statement, Delete):
            self.delete_statements.append(statement)
            return None
        self.select_statements.append(statement)
        return FakeResult(next(self.batches))


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
    """Minimal transactional engine."""

    def __init__(self, batches):
        """Initialize a fake connection and MySQL dialect."""
        self.connection = FakeConnection(batches)
        self.dialect = mysql.dialect()
        self.transactions = 0

    def begin(self):
        """Return a new transaction context."""
        self.transactions += 1
        return FakeBegin(self.connection)


def load_archive_job(monkeypatch):
    """Import the archive job with a small fake requests table."""
    metadata = MetaData()
    requests = Table(
        "requests",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parameters", JSON, nullable=False),
        Column("is_redacted", Boolean, nullable=False),
    )
    fake_logger = types.ModuleType("wikidatasearch.services.logger")
    fake_logger.Logger = types.SimpleNamespace(
        __table__=requests,
        id=requests.c.id,
        is_redacted=requests.c.is_redacted,
    )
    fake_logger.engine = object()

    monkeypatch.setitem(sys.modules, "wikidatasearch.services.logger", fake_logger)
    monkeypatch.delitem(sys.modules, "jobs.archive_redacted_logs", raising=False)
    return importlib.import_module("jobs.archive_redacted_logs")


def test_archive_processes_large_runs_in_bounded_transactions(monkeypatch, tmp_path):
    """Archive and delete one bounded batch per transaction."""
    archive_job = load_archive_job(monkeypatch)
    monkeypatch.setattr(archive_job, "ARCHIVE_BATCH_SIZE", 2)
    batches = [
        [
            {"id": 1, "parameters": {"lang": "en"}, "is_redacted": True},
            {"id": 2, "parameters": {"lang": "fr"}, "is_redacted": True},
        ],
        [{"id": 3, "parameters": {"lang": "de"}, "is_redacted": True}],
        [],
    ]
    fake_engine = FakeEngine(batches)
    output_path = tmp_path / "redacted.sql"

    assert archive_job.archive_redacted_requests(output_path, fake_engine) == 3

    dump = output_path.read_text()
    assert dump.count("INSERT INTO requests") == 2
    assert '{"lang":"en"}' in dump
    assert fake_engine.transactions == 4
    assert len(fake_engine.connection.select_statements) == 3

    delete_params = [statement.compile().params for statement in fake_engine.connection.delete_statements]
    assert delete_params == [{"id_1": [1, 2]}, {"id_1": [3]}]

    for statement in fake_engine.connection.select_statements:
        assert statement._limit_clause.value == 2
