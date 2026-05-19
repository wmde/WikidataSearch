"""Utility functions for Gradio analytics interface."""

from typing import Literal

import pandas as pd
import plotly.express as px

from .analytics_queries import AnalyticsQueryService

Period = Literal["Hour", "Day", "Week", "Month"]
GroupBy = Literal["None", "route", "user_agent", "status", "rerank", "lang", "client"]
PERIOD_FREQ = {"Hour": "H", "Day": "D", "Week": "W", "Month": "M"}


def aggregate_requests(df: pd.DataFrame, period: Period, group_by: GroupBy) -> pd.DataFrame:
    """Aggregate requests by time bucket and optional grouping dimension."""
    if df.empty:
        return df
    freq = PERIOD_FREQ[period]
    df = df.copy()

    if group_by == "client":
        if "on_browser" in df.columns:
            is_browser = df["on_browser"].fillna(False).astype(bool)
        else:
            ua = df.get("user_agent", pd.Series(index=df.index, dtype=object)).fillna("")
            is_browser = ua.str.contains("mozilla", case=False, na=False)
        df["client"] = is_browser.map({True: "browser", False: "api"})

    df = df.set_index("timestamp")

    if group_by == "None":
        out = df.groupby(pd.Grouper(freq=freq)).size().reset_index(name="requests")
    else:
        out = df.groupby([pd.Grouper(freq=freq), group_by]).size().reset_index(name="requests")

    return out.rename(columns={"timestamp": "bucket"})


def empty_ts(group_by: GroupBy):
    """Build an empty time-series chart placeholder for no-data scenarios."""
    if group_by == "None":
        base = pd.DataFrame({"bucket": [], "requests": []})
        return px.line(base, x="bucket", y="requests", title="No data", markers=True)
    base = pd.DataFrame({"bucket": [], "requests": [], group_by: []})
    return px.line(base, x="bucket", y="requests", color=group_by, title="No data", markers=True)


def empty_bar(group_by: GroupBy):
    """Build an empty bar chart placeholder for no-data scenarios."""
    if group_by == "None":
        base = pd.DataFrame({"category": [], "requests": []})
        return px.bar(base, x="category", y="requests", title="No data")
    base = pd.DataFrame({group_by: [], "requests": []})
    return px.bar(base, x=group_by, y="requests", title="No data")


def make_charts(agg: pd.DataFrame, group_by: GroupBy):
    """Generate timeseries and totals charts from aggregated request data."""
    if agg.empty:
        return empty_ts(group_by), empty_bar(group_by), pd.DataFrame()

    if group_by == "None":
        fig_ts = px.line(agg, x="bucket", y="requests", markers=True, title="Requests over time")
        totals = agg[["requests"]].sum().to_frame(name="requests")
        totals["category"] = "All"
        totals = totals[["category", "requests"]]
        fig_bar = px.bar(totals, x="category", y="requests", title="Total requests")
    else:
        fig_ts = px.line(
            agg,
            x="bucket",
            y="requests",
            color=group_by,
            markers=True,
            title=f"Requests over time by {group_by}",
        )
        totals = agg.groupby(group_by)["requests"].sum().sort_values(ascending=False).reset_index()
        fig_bar = px.bar(totals, x=group_by, y="requests", title=f"Requests by {group_by}")
    return fig_ts, fig_bar, totals


def summarize_totals_table(totals: pd.DataFrame) -> str:
    """Generate a summary string for the totals table."""
    rows = len(totals.index)
    if rows == 0 or "requests" not in totals.columns:
        return "Rows: 0 | Sum requests: 0"

    requests_sum = int(pd.to_numeric(totals["requests"], errors="coerce").fillna(0).sum())
    return f"Rows: {rows} | Sum requests: {requests_sum}"


def run_query(
    start,
    end,
    period_v,
    group_by_v,
    routes,
    statuses,
    ua_include,
    client_filter,
    rerank_filter,
    langs_filter,
):
    """Execute analytics query pipeline and return chart-ready outputs."""
    start, end = AnalyticsQueryService.normalize_dt_interval(start, end)

    normalized_routes = routes or []
    normalized_statuses = [int(x) for x in statuses] if statuses else []
    normalized_ua = ua_include or ""
    normalized_client = client_filter or "all"
    normalized_rerank = rerank_filter or "any"
    normalized_langs = langs_filter or []
    normalized_group_by = group_by_v

    df = AnalyticsQueryService.query_graph_requests(
        start=start,
        end=end,
        routes=normalized_routes,
        statuses=normalized_statuses,
        ua_include=normalized_ua,
        client_filter=normalized_client,
        rerank_filter=normalized_rerank,
        langs_filter=normalized_langs,
        group_by=normalized_group_by,
    )

    agg = aggregate_requests(df, period_v, normalized_group_by)
    fig_ts, fig_bar, totals = make_charts(agg, normalized_group_by)

    totals_summary = summarize_totals_table(totals)
    return fig_ts, fig_bar, totals, totals_summary
