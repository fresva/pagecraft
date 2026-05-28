"""MCP tool: write_kpis — renders the KPI section as a list of indicators."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component


@mcp.tool()
def write_kpis(
    items: list[dict],
    annotations: list[dict] | None = None,
) -> str:
    """Render the KPI section with one or more quantitative indicators.

    Args:
        items: List of {label, value, description} dicts. Typical labels are
            CO2-besparing, Lönsamhet/ROI and Investering, but use whatever the
            interviewee actually provides. Report only the KPIs they can give —
            one or more — and do not invent figures to reach a fixed count.
        annotations: Optional list of {field, text, severity} annotations
    """
    data = {"items": items}
    html = render_component("components/kpis.html", data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "kpis",
        "annotations": annotations or [],
    })
