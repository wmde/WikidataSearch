"""Logging service for the FastAPI application."""

import re
import time
import traceback
from datetime import datetime, timedelta
from hashlib import sha256

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import declarative_base, sessionmaker

from ...config import settings

"""
MySQL database setup for storing Wikidata labels in all languages.
"""

DB_HOST = settings.DB_HOST
DB_NAME = settings.DB_NAME
DB_USER = settings.DB_USER
DB_PASS = settings.DB_PASS
DB_PORT = settings.DB_PORT

DATABASE_URL = f"mariadb+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

engine = create_engine(
    DATABASE_URL,
    pool_size=settings.LOG_DB_POOL_SIZE,
    max_overflow=settings.LOG_DB_MAX_OVERFLOW,
    pool_timeout=settings.LOG_DB_POOL_TIMEOUT,
    pool_recycle=settings.LOG_DB_POOL_RECYCLE,
    pool_use_lifo=True,
    pool_pre_ping=True,
)

Base = declarative_base()
Session = sessionmaker(bind=engine, expire_on_commit=False)


class Logger(Base):
    """Logging model for user requests."""

    __tablename__ = "requests"
    __table_args__ = (
        Index("ix_requests_route_timestamp", "route", "timestamp"),
        Index("ix_requests_status_timestamp", "status", "timestamp"),
        Index("ix_requests_redaction_scan", "is_redacted", "timestamp", "id"),
        {"mysql_charset": "utf8mb4"},
    )

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    route = Column(String(128), index=True, nullable=False)
    parameters = Column(JSON, default=dict, nullable=False)
    status = Column(Integer, index=True, nullable=False)
    error = Column(Text)
    response_time = Column(Float, nullable=False)
    is_redacted = Column(Boolean, default=False, index=True, nullable=False)

    # User Agent
    user_agent = Column(String(255))
    user_agent_hash = Column(String(64), index=True, nullable=False)
    on_browser = Column(Boolean, nullable=False, default=False)

    # For queries
    query = Column(Text)
    query_hash = Column(String(64), index=True, nullable=False)
    query_length = Column(Integer, nullable=False, default=0)
    query_words = Column(Integer, nullable=False, default=0)

    @staticmethod
    def add_request(request, status_code, start_time, error=""):
        """Add a new request log entry.

        Args:
            request (_type_): The incoming request object.
            status_code (_type_): The HTTP status code of the response.
            start_time (_type_): The time when the request was received.
            error (str, optional): The error message, if any. Defaults to "".
        """
        with Session() as session:
            try:
                user_agent = request.headers.get("user-agent", "unknown")[:255]
                user_agent_hash = sha256(user_agent.encode("utf-8")).hexdigest()
                on_browser = "Mozilla" in user_agent

                query = request.query_params.get("query", "")
                query_hash = sha256(query.encode("utf-8")).hexdigest()
                query_length = len(query)
                query_words = len(re.findall(r"\w+", query))

                parameters = dict(request.query_params)
                parameters.pop("query", None)

                # Add new log entry
                log_entry = Logger(
                    route=request.url.path[:128],
                    user_agent=user_agent,
                    user_agent_hash=user_agent_hash,
                    on_browser=on_browser,
                    parameters=parameters,
                    query=query,
                    query_hash=query_hash,
                    query_length=query_length,
                    query_words=query_words,
                    status=status_code,
                    error=error,
                    response_time=time.time() - start_time,
                    is_redacted=False,
                )
                session.add(log_entry)
                session.commit()
            except Exception:
                session.rollback()
                traceback.print_exc()

    @staticmethod
    def redact_old_requests(days: int = 90, batch_size: int = 1000) -> int:
        """Redacts old request logs in SQL batches.

        Args:
            days (int, optional): The age of logs to redact in days. Defaults to 90.
            batch_size (int, optional): The number of logs to process in each batch. Defaults to 1000.

        Returns:
            int: Total number of rows redacted.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        batch_size = max(1, int(batch_size))
        update_stmt = text(
            f"""
            UPDATE requests
            SET user_agent = '', query = '', is_redacted = 1
            WHERE (is_redacted = 0 OR is_redacted IS NULL)
              AND timestamp < :cutoff_date
            ORDER BY id
            LIMIT {batch_size}
            """
        )

        total_redacted = 0
        batches = 0
        while True:
            try:
                with engine.begin() as conn:
                    result = conn.execute(update_stmt, {"cutoff_date": cutoff_date})
                    redacted = max(0, int(result.rowcount or 0))
            except Exception:
                traceback.print_exc()
                break

            if redacted == 0:
                break

            total_redacted += redacted
            batches += 1

        return total_redacted


class Feedback(Base):
    """Feedback model for user interactions."""

    __tablename__ = "feedback"
    __table_args__ = (
        Index("ix_feedback_qid", "qid"),
        {"mysql_charset": "utf8mb4"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String(512))
    qid = Column(String(32))
    sentiment = Column(String(32))
    index = Column(Integer)

    @staticmethod
    def add_feedback(query, qid, sentiment, index):
        """Adds feedback for a user query.

        Args:
            query (str): The user query.
            qid (str): The Wikidata entity ID.
            sentiment (str): The sentiment of the feedback.
            index (int): The index of the feedback.
        """
        with Session() as session:
            try:
                # Add new feedback
                feedback_entry = Feedback(
                    query=query,
                    qid=qid,
                    sentiment=sentiment,
                    index=index,
                )
                session.add(feedback_entry)
                session.commit()
            except Exception:
                session.rollback()
                traceback.print_exc()


def initialize_database():
    """Create tables if they do not already exist."""
    try:
        Base.metadata.create_all(engine)
        return True
    except Exception as e:
        print(f"Error while initializing labels database: {e}")
        return False
