"""Analytics query service for request log analysis."""

from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd
from sqlalchemy import bindparam, text

from .database import engine


class AnalyticsQueryService:
    """Database read/query methods used by analytics."""

    VECTOR_QUERY_ROUTES_SQL = "('/item/query/', '/property/query/', '/similarity-score/')"

    @staticmethod
    def _extract_user_agent_values(df: pd.DataFrame) -> list[str]:
        """Extract unique user-agent values from query results."""
        if df.empty or "user_agent_value" not in df.columns:
            return []

        values = df["user_agent_value"].fillna("").astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
        return sorted(values)

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
                COALESCE(SUM(CASE WHEN COALESCE(on_browser, 0) = 1 THEN 1 ELSE 0 END), 0) AS browser,
                COALESCE(SUM(CASE WHEN COALESCE(on_browser, 0) = 0 THEN 1 ELSE 0 END), 0) AS api
            FROM requests
            WHERE route = '/'
              AND timestamp BETWEEN :start AND :end
        """
        )

        with engine.connect() as conn:
            df = pd.read_sql(q, conn, params={"start": start, "end": end})

        row = df.iloc[0] if not df.empty else {}
        browser = row.get("browser", 0)
        browser = int(browser) if pd.notna(browser) else 0
        api = row.get("api", 0)
        api = int(api) if pd.notna(api) else 0
        return {"browser": browser, "api": api, "total": browser + api}

    @staticmethod
    def get_total_user_agents(
        start: datetime,
        end: datetime,
        requests_threshold: int = 0,
        include_user_agents: bool = False,
    ) -> dict[str, Any]:
        """Return unique user agents for vector-query routes between start and end."""
        params = {
            "start": start,
            "end": end,
            "requests_threshold": int(requests_threshold),
        }
        if include_user_agents:
            q = text(
                f"""
                SELECT
                    CASE
                        WHEN COALESCE(on_browser, 0) = 1 THEN 'browser'
                        ELSE 'api'
                    END AS client,
                    user_agent_hash,
                    COALESCE(MAX(NULLIF(user_agent, '')), user_agent_hash) AS user_agent_value
                FROM requests
                WHERE route IN {AnalyticsQueryService.VECTOR_QUERY_ROUTES_SQL}
                  AND status NOT IN (400, 422)
                  AND timestamp BETWEEN :start AND :end
                  AND user_agent_hash IS NOT NULL
                  AND user_agent_hash != ''
                GROUP BY client, user_agent_hash
                HAVING :requests_threshold <= 0 OR COUNT(*) > :requests_threshold
                ORDER BY user_agent_hash
            """
            )
            with engine.connect() as conn:
                df = pd.read_sql(q, conn, params=params)

            out: dict[str, Any] = {"browser": 0, "api": 0, "total": 0}
            if df.empty:
                out["user_agents"] = []
                return out

            counts = df["client"].astype(str).value_counts()
            out["browser"] = int(counts.get("browser", 0))
            out["api"] = int(counts.get("api", 0))
            out["total"] = out["browser"] + out["api"]
            out["user_agents"] = AnalyticsQueryService._extract_user_agent_values(df)
            return out

        q = text(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN t.client = 'browser' THEN 1 ELSE 0 END), 0) AS browser,
                COALESCE(SUM(CASE WHEN t.client = 'api' THEN 1 ELSE 0 END), 0) AS api
            FROM (
                SELECT
                    CASE
                        WHEN COALESCE(on_browser, 0) = 1 THEN 'browser'
                        ELSE 'api'
                    END AS client,
                    user_agent_hash
                FROM requests
                WHERE route IN {AnalyticsQueryService.VECTOR_QUERY_ROUTES_SQL}
                  AND status NOT IN (400, 422)
                  AND timestamp BETWEEN :start AND :end
                  AND user_agent_hash IS NOT NULL
                  AND user_agent_hash != ''
                GROUP BY client, user_agent_hash
                HAVING :requests_threshold <= 0 OR COUNT(*) > :requests_threshold
            ) AS t
        """
        )
        with engine.connect() as conn:
            df = pd.read_sql(q, conn, params=params)

        row = df.iloc[0] if not df.empty else {}
        browser = row.get("browser", 0)
        browser = int(browser) if pd.notna(browser) else 0
        api = row.get("api", 0)
        api = int(api) if pd.notna(api) else 0
        return {"browser": browser, "api": api, "total": browser + api}

    @staticmethod
    def get_total_requests(start: datetime, end: datetime) -> dict[str, int]:
        """Return the number of requests for routes that query the vector database between start and end."""
        q = text(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN COALESCE(on_browser, 0) = 1 THEN 1 ELSE 0 END), 0) AS browser,
                COALESCE(SUM(CASE WHEN COALESCE(on_browser, 0) = 0 THEN 1 ELSE 0 END), 0) AS api
            FROM requests
            WHERE route IN {AnalyticsQueryService.VECTOR_QUERY_ROUTES_SQL}
              AND status NOT IN (400, 422)
              AND timestamp BETWEEN :start AND :end
        """
        )

        with engine.connect() as conn:
            df = pd.read_sql(q, conn, params={"start": start, "end": end})

        row = df.iloc[0] if not df.empty else {}
        browser = row.get("browser", 0)
        browser = int(browser) if pd.notna(browser) else 0
        api = row.get("api", 0)
        api = int(api) if pd.notna(api) else 0
        return {"browser": browser, "api": api, "total": browser + api}

    @staticmethod
    def get_total_requests_by_lang(start: datetime, end: datetime) -> dict[str, int]:
        """Return API request counts for vector database query routes, grouped by requested language."""
        q = text(
            f"""
            SELECT
                COALESCE(
                    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(parameters, '$.lang')), ''),
                    'all'
                ) AS lang,
                COUNT(*) AS requests
            FROM requests
            WHERE route IN {AnalyticsQueryService.VECTOR_QUERY_ROUTES_SQL}
              AND status NOT IN (400, 422)
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

        lang_df = df.assign(
            lang=df["lang"].astype(str),
            requests=pd.to_numeric(df["requests"], errors="coerce").fillna(0).astype(int),
        )
        out.update({row.lang: int(row.requests) for row in lang_df.itertuples(index=False)})
        out["total"] = int(lang_df["requests"].sum())
        return out

    @staticmethod
    def get_new_user_agents(
        start: datetime,
        end: datetime,
        include_user_agents: bool = False,
    ) -> dict[str, Any]:
        """Return new user agents between start and end and optionally list original values."""
        params = {"start": start, "end": end}
        if include_user_agents:
            q = text(
                f"""
                SELECT
                    user_agent_hash,
                    COALESCE(MAX(NULLIF(user_agent, '')), user_agent_hash) AS user_agent_value
                FROM requests
                WHERE route IN {AnalyticsQueryService.VECTOR_QUERY_ROUTES_SQL}
                  AND status NOT IN (400, 422)
                  AND timestamp <= :end
                  AND user_agent_hash IS NOT NULL
                  AND user_agent_hash != ''
                  AND COALESCE(on_browser, 0) = 0
                GROUP BY user_agent_hash
                HAVING
                    SUM(CASE WHEN timestamp BETWEEN :start AND :end THEN 1 ELSE 0 END) > 0
                    AND SUM(CASE WHEN timestamp < :start THEN 1 ELSE 0 END) = 0
                ORDER BY user_agent_hash
                """
            )
            with engine.connect() as conn:
                df = pd.read_sql(q, conn, params=params)

            out = {"total": len(df.index)}
            out["user_agents"] = AnalyticsQueryService._extract_user_agent_values(df)
            return out

        q = text(
            f"""
            SELECT COUNT(*) AS total
            FROM (
                SELECT user_agent_hash
                FROM requests
                WHERE route IN {AnalyticsQueryService.VECTOR_QUERY_ROUTES_SQL}
                  AND status NOT IN (400, 422)
                  AND timestamp <= :end
                  AND user_agent_hash IS NOT NULL
                  AND user_agent_hash != ''
                  AND COALESCE(on_browser, 0) = 0
                GROUP BY user_agent_hash
                HAVING
                    SUM(CASE WHEN timestamp BETWEEN :start AND :end THEN 1 ELSE 0 END) > 0
                    AND SUM(CASE WHEN timestamp < :start THEN 1 ELSE 0 END) = 0
            ) AS t
            """
        )
        with engine.connect() as conn:
            df = pd.read_sql(q, conn, params=params)

        row = df.iloc[0] if not df.empty else {}
        total = row.get("total", 0)
        total = int(total) if pd.notna(total) else 0
        return {"total": total}

    @staticmethod
    def get_consistent_user_agents(
        start: datetime,
        end: datetime,
        consistent_days: int = 3,
        include_user_agents: bool = False,
    ) -> dict[str, Any]:
        """Return consistent user agents and optionally list original values."""
        min_days = max(1, int(consistent_days))

        params = {"start": start, "end": end, "min_days": min_days}
        if include_user_agents:
            q = text(
                f"""
                SELECT
                    user_agent_hash,
                    COALESCE(MAX(NULLIF(user_agent, '')), user_agent_hash) AS user_agent_value
                FROM requests
                WHERE route IN {AnalyticsQueryService.VECTOR_QUERY_ROUTES_SQL}
                  AND status NOT IN (400, 422)
                  AND timestamp <= :end
                  AND user_agent_hash IS NOT NULL
                  AND user_agent_hash != ''
                  AND COALESCE(on_browser, 0) = 0
                GROUP BY user_agent_hash
                HAVING
                    SUM(CASE WHEN timestamp BETWEEN :start AND :end THEN 1 ELSE 0 END) > 0
                    AND COUNT(DISTINCT DATE(timestamp)) >= :min_days
                ORDER BY user_agent_hash
                """
            )
            with engine.connect() as conn:
                df = pd.read_sql(q, conn, params=params)

            out = {"total": len(df.index)}
            out["user_agents"] = AnalyticsQueryService._extract_user_agent_values(df)
            return out

        q = text(
            f"""
            SELECT COUNT(*) AS total
            FROM (
                SELECT user_agent_hash
                FROM requests
                WHERE route IN {AnalyticsQueryService.VECTOR_QUERY_ROUTES_SQL}
                  AND status NOT IN (400, 422)
                  AND timestamp <= :end
                  AND user_agent_hash IS NOT NULL
                  AND user_agent_hash != ''
                  AND COALESCE(on_browser, 0) = 0
                GROUP BY user_agent_hash
                HAVING
                    SUM(CASE WHEN timestamp BETWEEN :start AND :end THEN 1 ELSE 0 END) > 0
                    AND COUNT(DISTINCT DATE(timestamp)) >= :min_days
            ) AS t
            """
        )
        with engine.connect() as conn:
            df = pd.read_sql(q, conn, params=params)

        row = df.iloc[0] if not df.empty else {}
        total = row.get("total", 0)
        total = int(total) if pd.notna(total) else 0
        return {"total": total}

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
