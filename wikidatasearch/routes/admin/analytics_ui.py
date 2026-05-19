"""Analytics service for the FastAPI application."""

from datetime import datetime, timezone

import gradio as gr
import pandas as pd

from ...config import settings
from ...services.logger.gradio_utils import run_query

ROUTES_CHOICES = ["/", "/item/query/", "/property/query/", "/similarity-score/"]
RERANK_CHOICES = ["any", "true", "false", "unset"]
STATUS_CHOICES = ["200", "400", "422", "429", "500"]
LANG_CHOICES = ["all", "translated"] + settings.VECTORDb_LANGS
CLIENT_CHOICES = ["all", "browser", "api"]
PERIOD_CHOICES = ["Hour", "Day", "Week", "Month"]
GROUP_BY_CHOICES = ["None", "route", "user_agent", "status", "rerank", "lang", "client"]


def build_analytics_app():
    """Build and return the Gradio analytics dashboard application."""
    now = datetime.now(tz=timezone.utc).replace(microsecond=0)
    default_start = now - pd.Timedelta(days=7)

    with gr.Blocks(title="API Analytics") as demo:
        gr.Markdown("## API Analytics")

        with gr.Row():
            start_dt = gr.DateTime(label="Start UTC", value=default_start, interactive=True)
            end_dt = gr.DateTime(label="End UTC", value=now, interactive=True)
            period = gr.Dropdown(choices=PERIOD_CHOICES, value="Day", label="Time bucket")
            group_by = gr.Dropdown(choices=GROUP_BY_CHOICES, value="None", label="Group by")

        with gr.Row():
            route_dd = gr.CheckboxGroup(choices=ROUTES_CHOICES, label="Filter routes", value=[])
            status_dd = gr.CheckboxGroup(choices=STATUS_CHOICES, label="Filter status codes", value=[])
            ua_inc = gr.Textbox(label="User agent contains", placeholder="curl, python-requests, chrome")
            client_dd = gr.Dropdown(choices=CLIENT_CHOICES, value="all", label="Client type")

        with gr.Row():
            rerank_dd = gr.Dropdown(choices=RERANK_CHOICES, value="any", label="Filter rerank")
            langs_dd = gr.Dropdown(choices=LANG_CHOICES, value=[], multiselect=True, label="Filter lang")

        btn = gr.Button("Refresh", variant="primary")

        ts_plot = gr.Plot(label="Requests over time")
        bar_plot = gr.Plot(label="Totals")
        table = gr.Dataframe(label="Totals table", interactive=False)
        table_stats = gr.Markdown("Rows: 0 | Sum requests: 0")

        inputs = [start_dt, end_dt, period, group_by, route_dd, status_dd, ua_inc, client_dd, rerank_dd, langs_dd]

        btn.click(fn=run_query, inputs=inputs, outputs=[ts_plot, bar_plot, table, table_stats], queue=False)
        gr.on(
            triggers=[x.change for x in inputs],
            fn=run_query,
            inputs=inputs,
            outputs=[ts_plot, bar_plot, table, table_stats],
            queue=False,
        )

    return demo
