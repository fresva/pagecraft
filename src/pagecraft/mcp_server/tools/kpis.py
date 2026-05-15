"""MCP tool: write_kpis — renders the KPI section with three specific cells."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component


@mcp.tool()
def write_kpis(
    co2_kpis: dict,
    profitability: dict,
    investment: dict,
    annotations: list[dict] | None = None,
) -> str:
    """Render the KPI section with three quantitative indicators.

    Args:
        co2_kpis: {value, description} for CO2 key performance indicators
        profitability: {value, description} for profitability/cost analysis
        investment: {value, description} for investment requirements
        annotations: Optional list of {field, text, severity} annotations
    """
    data = {
        "co2_kpis": co2_kpis,
        "profitability": profitability,
        "investment": investment,
    }
    html = render_component("components/kpis.html", data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "kpis",
        "annotations": annotations or [],
    })
