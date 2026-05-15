"""MCP tool: write_impact — renders the impact assessment section."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component


@mcp.tool()
def write_impact(
    co2_reduction: dict,
    cost_benefit: dict,
    spread_potential: dict,
    annotations: list[dict] | None = None,
) -> str:
    """Render the impact assessment section with three impact cards.

    Args:
        co2_reduction: {value, description} for CO2 reduction potential
        cost_benefit: {value, description} for cost-benefit analysis
        spread_potential: {value, description} for spread potential
        annotations: Optional list of {field, text, severity} annotations
    """
    data = {
        "co2_reduction": co2_reduction,
        "cost_benefit": cost_benefit,
        "spread_potential": spread_potential,
    }
    html = render_component("components/impact.html", data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "impact",
        "annotations": annotations or [],
    })
