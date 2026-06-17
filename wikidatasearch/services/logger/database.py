"""Logging service for the FastAPI application."""

import re
import time
import traceback
from datetime import datetime, timedelta
from hashlib import sha256

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    bindparam,
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
    QUERY_ROUTES = ("/item/query/", "/property/query/", "/similarity-score/")
    __table_args__ = (
        Index("ix_requests_route_timestamp", "route", "timestamp"),
        Index("ix_requests_status_timestamp", "status", "timestamp"),
        Index("ix_requests_redaction_scan", "is_redacted", "timestamp", "id"),
        Index("ix_requests_redacted_id", "is_redacted", "id"),
        {"mysql_charset": "utf8mb4"},
    )

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    route = Column(String(128), nullable=False)
    parameters = Column(JSON, default=dict, nullable=False)
    status = Column(Integer, nullable=False)
    error = Column(Text)
    response_time = Column(Float, nullable=False)
    is_redacted = Column(Boolean, default=False, nullable=False)

    # User Agent
    user_agent = Column(String(255))
    user_agent_hash = Column(String(64), index=True, nullable=False)
    on_browser = Column(Boolean, nullable=False, default=False)

    # For queries
    query = Column(Text)
    query_hash = Column(String(64), nullable=False)
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
                timestamp = datetime.utcnow()
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
                    timestamp=timestamp,
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
                UserAgents.add_request(
                    session=session,
                    user_agent_hash=user_agent_hash,
                    seen_at=timestamp,
                    on_browser=on_browser,
                    is_query_route=request.url.path in Logger.QUERY_ROUTES,
                )
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


class UserAgents(Base):
    """Aggregated history for unique user agents."""

    __tablename__ = "user_agent_history"
    __table_args__ = (
        Index("ix_user_agent_history_query_first_seen", "query_first_seen"),
        Index("ix_user_agent_history_query_distinct_days", "query_distinct_days"),
        {"mysql_charset": "utf8mb4"},
    )

    user_agent_hash = Column(String(64), primary_key=True)

    # Fields for all requests
    first_seen = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, nullable=False)
    on_browser = Column(Boolean, nullable=False)
    distinct_days = Column(Integer, nullable=False, default=0)
    total_requests = Column(BigInteger, nullable=False, default=0)

    # Separate fields for query requests
    query_first_seen = Column(DateTime)
    query_last_seen = Column(DateTime)
    query_distinct_days = Column(Integer, nullable=False, default=0)
    query_total_requests = Column(BigInteger, nullable=False, default=0)

    @staticmethod
    def add_request(session, user_agent_hash: str, seen_at: datetime, on_browser: bool, is_query_route: bool) -> None:
        """Upsert aggregate user-agent history for one logged request."""
        session.execute(
            text(
                """
                INSERT INTO user_agent_history (
                    user_agent_hash,
                    first_seen,
                    last_seen,
                    on_browser,
                    distinct_days,
                    total_requests,
                    query_first_seen,
                    query_last_seen,
                    query_distinct_days,
                    query_total_requests
                )
                VALUES (
                    :user_agent_hash,
                    :seen_at,
                    :seen_at,
                    :on_browser,
                    1,
                    1,
                    :query_seen_at,
                    :query_seen_at,
                    :query_distinct_days,
                    :query_total_requests
                )
                ON DUPLICATE KEY UPDATE
                    first_seen = LEAST(first_seen, VALUES(first_seen)),
                    distinct_days = distinct_days + IF(DATE(VALUES(last_seen)) > DATE(last_seen), 1, 0),
                    last_seen = GREATEST(last_seen, VALUES(last_seen)),
                    on_browser = on_browser OR VALUES(on_browser),
                    total_requests = total_requests + 1,
                    query_first_seen = CASE
                        WHEN VALUES(query_first_seen) IS NULL THEN query_first_seen
                        WHEN query_first_seen IS NULL THEN VALUES(query_first_seen)
                        ELSE LEAST(query_first_seen, VALUES(query_first_seen))
                    END,
                    query_distinct_days = query_distinct_days + IF(
                        VALUES(query_last_seen) IS NOT NULL
                        AND (query_last_seen IS NULL OR DATE(VALUES(query_last_seen)) > DATE(query_last_seen)),
                        1,
                        0
                    ),
                    query_last_seen = CASE
                        WHEN VALUES(query_last_seen) IS NULL THEN query_last_seen
                        WHEN query_last_seen IS NULL THEN VALUES(query_last_seen)
                        ELSE GREATEST(query_last_seen, VALUES(query_last_seen))
                    END,
                    query_total_requests = query_total_requests + VALUES(query_total_requests)
                """
            ),
            {
                "user_agent_hash": user_agent_hash,
                "seen_at": seen_at,
                "on_browser": on_browser,
                "query_seen_at": seen_at if is_query_route else None,
                "query_distinct_days": 1 if is_query_route else 0,
                "query_total_requests": 1 if is_query_route else 0,
            },
        )

    @staticmethod
    def build_from_requests() -> int:
        """Merge available request logs into user-agent history.

        Existing aggregates are preserved because the requests table may no longer
        contain old redacted rows. Counts use the greatest known value instead of
        being added, making repeated builds safe when requests overlap history.
        """
        with engine.begin() as conn:
            stmt = text(
                """
                    INSERT INTO user_agent_history (
                        user_agent_hash,
                        first_seen,
                        last_seen,
                        on_browser,
                        distinct_days,
                        total_requests,
                        query_first_seen,
                        query_last_seen,
                        query_distinct_days,
                        query_total_requests
                    )
                    SELECT
                        user_agent_hash,
                        MIN(timestamp) AS first_seen,
                        MAX(timestamp) AS last_seen,
                        MAX(COALESCE(on_browser, 0)) AS on_browser,
                        COUNT(DISTINCT DATE(timestamp)) AS distinct_days,
                        COUNT(*) AS total_requests,
                        MIN(CASE WHEN route IN :query_routes THEN timestamp END) AS query_first_seen,
                        MAX(CASE WHEN route IN :query_routes THEN timestamp END) AS query_last_seen,
                        COUNT(DISTINCT CASE WHEN route IN :query_routes THEN DATE(timestamp) END)
                            AS query_distinct_days,
                        SUM(CASE WHEN route IN :query_routes THEN 1 ELSE 0 END) AS query_total_requests
                    FROM requests
                    GROUP BY user_agent_hash
                    ON DUPLICATE KEY UPDATE
                        first_seen = LEAST(first_seen, VALUES(first_seen)),
                        last_seen = GREATEST(last_seen, VALUES(last_seen)),
                        on_browser = on_browser OR VALUES(on_browser),
                        distinct_days = GREATEST(distinct_days, VALUES(distinct_days)),
                        total_requests = GREATEST(total_requests, VALUES(total_requests)),
                        query_first_seen = CASE
                            WHEN VALUES(query_first_seen) IS NULL THEN query_first_seen
                            WHEN query_first_seen IS NULL THEN VALUES(query_first_seen)
                            ELSE LEAST(query_first_seen, VALUES(query_first_seen))
                        END,
                        query_last_seen = CASE
                            WHEN VALUES(query_last_seen) IS NULL THEN query_last_seen
                            WHEN query_last_seen IS NULL THEN VALUES(query_last_seen)
                            ELSE GREATEST(query_last_seen, VALUES(query_last_seen))
                        END,
                        query_distinct_days = GREATEST(query_distinct_days, VALUES(query_distinct_days)),
                        query_total_requests = GREATEST(query_total_requests, VALUES(query_total_requests))
                    """
            ).bindparams(bindparam("query_routes", expanding=True))
            result = conn.execute(
                stmt,
                {"query_routes": list(Logger.QUERY_ROUTES)},
            )
            return max(0, int(result.rowcount or 0))


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
