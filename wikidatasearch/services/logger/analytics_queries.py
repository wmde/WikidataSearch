"""Analytics query service for request log analysis."""

from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd
from sqlalchemy import bindparam, text

from .database import engine


class AnalyticsQueryService:
    """Database read/query methods used by analytics."""

    @classmethod
    def query_graph_requests(
        cls,
        start: datetime,
        end: datetime,
        routes: list[str],
        statuses: list[int],
        ua_include: Optional[str],
        client_filter: str = "all",
        rerank_filter: str = "any",
        langs_filter: Optional[list[str]] = None,
        group_by: Optional[str] = None,
    ) -> pd.DataFrame:
        """Load request logs for analytics with filtering applied in SQL.

        The selected columns are minimized based on `group_by` and active filters.
        """
        rerank_expr = """
            CASE
                WHEN LOWER(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(parameters, '$.rerank')), ''))
                     IN ('true', 'false')
                THEN LOWER(JSON_UNQUOTE(JSON_EXTRACT(parameters, '$.rerank')))
                ELSE 'unset'
            END
        """
        lang_expr = """
            COALESCE(
                NULLIF(LOWER(JSON_UNQUOTE(JSON_EXTRACT(parameters, '$.lang'))), ''),
                'all'
            )
        """

        langs = [str(v).strip().lower() for v in (langs_filter or []) if str(v).strip()]

        select_cols: list[str] = ["timestamp"]
        if group_by == "route":
            select_cols.append("route")
        elif group_by == "user_agent":
            select_cols.append("user_agent")
        elif group_by == "status":
            select_cols.append("status")
        elif group_by == "client":
            select_cols.append("on_browser")
        elif group_by == "rerank":
            select_cols.append(f"{rerank_expr} AS rerank")
        elif group_by == "lang":
            select_cols.append(f"{lang_expr} AS lang")

        base = (
            "SELECT "
            + ", ".join(select_cols)
            + """
            FROM requests
            WHERE timestamp BETWEEN :start AND :end
        """
        )

        params: dict = {"start": start, "end": end}
        clauses: list[str] = []

        if routes:
            clauses.append("route IN :routes")
        if statuses:
            clauses.append("status IN :statuses")
        if ua_include:
            clauses.append("LOWER(COALESCE(user_agent, '')) LIKE :ua_inc")
            params["ua_inc"] = f"%{ua_include.lower()}%"
        if client_filter == "browser":
            clauses.append("COALESCE(on_browser, 0) = 1")
        elif client_filter == "api":
            clauses.append("COALESCE(on_browser, 0) = 0")
        if rerank_filter in ("true", "false", "unset"):
            clauses.append(f"{rerank_expr} = :rerank_filter")
            params["rerank_filter"] = rerank_filter
        if langs:
            clauses.append(f"{lang_expr} IN :langs")
            params["langs"] = langs

        if clauses:
            base += " AND " + " AND ".join(clauses)

        stmt = text(base)
        if routes:
            stmt = stmt.bindparams(bindparam("routes", expanding=True))
            params["routes"] = list(routes)
        if statuses:
            stmt = stmt.bindparams(bindparam("statuses", expanding=True))
            params["statuses"] = list(statuses)
        if langs:
            stmt = stmt.bindparams(bindparam("langs", expanding=True))

        with engine.connect() as conn:
            df = pd.read_sql(stmt, conn, params=params, parse_dates=["timestamp"])

        if df.empty or "status" not in df.columns:
            return df

        df["status"] = df["status"].astype(int)
        return df

    @staticmethod
    def get_page_views(start: datetime, end: datetime) -> dict[str, int]:
        """Return page views for route '/' between start and end, split by client type (browser vs API)."""
        q = text(
            """
            SELECT
                CASE
                    WHEN COALESCE(on_browser, 0) = 1 THEN 'browser'
                    ELSE 'api'
                END AS client,
                COUNT(*) AS requests
            FROM requests
            WHERE route = '/'
              AND timestamp BETWEEN :start AND :end
            GROUP BY client
        """
        )

        with engine.connect() as conn:
            df = pd.read_sql(q, conn, params={"start": start, "end": end})

        out = {"browser": 0, "api": 0, "total": 0}
        if df.empty:
            return out

        for _, row in df.iterrows():
            client = str(row["client"])
            requests = int(row["requests"])
            if client in ("browser", "api"):
                out[client] = requests

        out["total"] = out["browser"] + out["api"]
        return out

    @staticmethod
    def get_total_user_agents(
        start: datetime,
        end: datetime,
        requests_threshold: int = 0,
        include_user_agents: bool = False,
    ) -> dict[str, Any]:
        """Return unique user agents for route '/' between start and end."""
        q = text(
            """
            SELECT
                CASE
                    WHEN COALESCE(on_browser, 0) = 1 THEN 'browser'
                    ELSE 'api'
                END AS client,
                user_agent_hash
            FROM requests
            WHERE route = '/'
              AND timestamp BETWEEN :start AND :end
              AND user_agent_hash IS NOT NULL
              AND user_agent_hash != ''
            GROUP BY client, user_agent_hash
            HAVING :requests_threshold <= 0 OR COUNT(*) > :requests_threshold
        """
        )

        with engine.connect() as conn:
            df = pd.read_sql(
                q,
                conn,
                params={
                    "start": start,
                    "end": end,
                    "requests_threshold": int(requests_threshold),
                },
            )

        out: dict[str, Any] = {"browser": 0, "api": 0, "total": 0}
        if df.empty:
            if include_user_agents:
                out["user_agents"] = []
            return out

        for _, row in df.iterrows():
            client = str(row["client"])
            if client in ("browser", "api"):
                out[client] += 1

        out["total"] = out["browser"] + out["api"]
        if include_user_agents:
            out["user_agents"] = sorted(df["user_agent_hash"].astype(str).unique().tolist())
        return out

    @staticmethod
    def get_total_requests(start: datetime, end: datetime) -> dict[str, int]:
        """Return the number of requests for routes that query the vector database between start and end."""
        q = text(
            """
            SELECT
                CASE
                    WHEN COALESCE(on_browser, 0) = 1 THEN 'browser'
                    ELSE 'api'
                END AS client,
                COUNT(*) AS requests
            FROM requests
            WHERE route IN ('/item/query/', '/property/query/', '/similarity-score/')
              AND status <> 422
              AND timestamp BETWEEN :start AND :end
            GROUP BY client
        """
        )

        with engine.connect() as conn:
            df = pd.read_sql(q, conn, params={"start": start, "end": end})

        out = {"browser": 0, "api": 0, "total": 0}
        if df.empty:
            return out

        for _, row in df.iterrows():
            client = str(row["client"])
            requests = int(row["requests"])
            if client in ("browser", "api"):
                out[client] = requests

        out["total"] = out["browser"] + out["api"]
        return out

    @staticmethod
    def get_total_requests_by_lang(start: datetime, end: datetime) -> dict[str, int]:
        """Return API request counts for vector database query routes, grouped by requested language."""
        q = text(
            """
            SELECT
                COALESCE(
                    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(parameters, '$.lang')), ''),
                    'all'
                ) AS lang,
                COUNT(*) AS requests
            FROM requests
            WHERE route IN ('/item/query/', '/property/query/', '/similarity-score/')
              AND status <> 422
              AND COALESCE(on_browser, 0) = 0
              AND timestamp BETWEEN :start AND :end
            GROUP BY lang
            ORDER BY requests DESC
        """
        )

        with engine.connect() as conn:
            df = pd.read_sql(q, conn, params={"start": start, "end": end})

        out: dict[str, int] = {"total": 0}
        if df.empty:
            return out

        total = 0
        for _, row in df.iterrows():
            lang = str(row["lang"])
            requests = int(row["requests"])
            out[lang] = requests
            total += requests

        out["total"] = total
        return out

    @staticmethod
    def get_new_user_agents(
        start: datetime,
        end: datetime,
        include_user_agents: bool = False,
    ) -> dict[str, Any]:
        """Return User Agent hashes seen between start and end but never seen before start."""
        q = text(
            """
            SELECT
                interval_uas.user_agent_hash
            FROM (
                SELECT
                    user_agent_hash
                FROM requests
                WHERE route IN ('/item/query/', '/property/query/', '/similarity-score/')
                  AND status <> 422
                  AND timestamp BETWEEN :start AND :end
                  AND user_agent_hash IS NOT NULL
                  AND user_agent_hash != ''
                GROUP BY user_agent_hash
            ) AS interval_uas
            LEFT JOIN (
                SELECT DISTINCT user_agent_hash
                FROM requests
                WHERE route IN ('/item/query/', '/property/query/', '/similarity-score/')
                  AND status <> 422
                  AND timestamp < :start
                  AND user_agent_hash IS NOT NULL
                  AND user_agent_hash != ''
            ) AS past_uas
              ON past_uas.user_agent_hash = interval_uas.user_agent_hash
            WHERE past_uas.user_agent_hash IS NULL
            ORDER BY interval_uas.user_agent_hash
            """
        )

        with engine.connect() as conn:
            df = pd.read_sql(q, conn, params={"start": start, "end": end})

        out = {"total": 0}
        if df.empty:
            if include_user_agents:
                out["user_agents"] = []
            return out

        user_agents = df["user_agent_hash"].astype(str).tolist()
        out["total"] = len(user_agents)
        if include_user_agents:
            out["user_agents"] = user_agents
        return out

    @staticmethod
    def get_consistent_user_agents(
        start: datetime,
        end: datetime,
        consistent_days: int = 3,
        include_user_agents: bool = False,
    ) -> dict[str, Any]:
        """Return User Agent hashes seen between start and end and on at least `consistent_days` distinct days."""
        min_days = max(1, int(consistent_days))

        q = text(
            """
            SELECT
                interval_uas.user_agent_hash
            FROM (
                SELECT
                    user_agent_hash
                FROM requests
                WHERE route IN ('/item/query/', '/property/query/', '/similarity-score/')
                  AND status <> 422
                  AND timestamp BETWEEN :start AND :end
                  AND user_agent_hash IS NOT NULL
                  AND user_agent_hash != ''
                GROUP BY user_agent_hash
            ) AS interval_uas
            INNER JOIN (
                SELECT
                    user_agent_hash,
                    COUNT(DISTINCT DATE(timestamp)) AS days_seen
                FROM requests
                WHERE route IN ('/item/query/', '/property/query/', '/similarity-score/')
                  AND status <> 422
                  AND timestamp <= :end
                  AND user_agent_hash IS NOT NULL
                  AND user_agent_hash != ''
                GROUP BY user_agent_hash
            ) AS ua_days
              ON ua_days.user_agent_hash = interval_uas.user_agent_hash
            WHERE ua_days.days_seen >= :min_days
            ORDER BY interval_uas.user_agent_hash
            """
        )

        with engine.connect() as conn:
            df = pd.read_sql(
                q,
                conn,
                params={"start": start, "end": end, "min_days": min_days},
            )

        out = {"total": 0}
        if df.empty:
            if include_user_agents:
                out["user_agents"] = []
            return out

        user_agents = df["user_agent_hash"].astype(str).tolist()
        out["total"] = len(user_agents)
        if include_user_agents:
            out["user_agents"] = user_agents
        return out

    @staticmethod
    def normalize_dt_interval(start: Any, end: Any) -> tuple[datetime, datetime]:
        """Normalize and validate start and end datetimes for queries."""
        if isinstance(start, datetime):
            start = start.astimezone(timezone.utc).replace(tzinfo=None)
        if isinstance(end, datetime):
            end = end.astimezone(timezone.utc).replace(tzinfo=None)

        if isinstance(start, (int, float)):
            start = datetime.utcfromtimestamp(float(start))
        if isinstance(end, (int, float)):
            end = datetime.utcfromtimestamp(float(end))

        if pd.isna(start):
            # lowest time ever
            start = datetime(1970, 1, 1)
        if pd.isna(end):
            # highest time ever
            end = datetime(3000, 1, 1)

        start = pd.to_datetime(start, utc=True, errors="coerce")
        end = pd.to_datetime(end, utc=True, errors="coerce")

        start = start.tz_convert(None).to_pydatetime()
        end = end.tz_convert(None).to_pydatetime()

        if start > end:
            return end, start
        return start, end
