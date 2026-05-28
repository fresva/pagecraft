"""MCP tool: write_impact — renders the impact assessment section as a list."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component


@mcp.tool()
def write_impact(
    items: list[dict],
    annotations: list[dict] | None = None,
) -> str:
    """Render the impact assessment section with one or more impact dimensions.

    Args:
        items: List of {label, value, description} dicts. The three standard
            lenses are CO2e-minskningspotential, Klimat för pengarna and
            Spridningspotential — use them as labels when they apply, but only
            include the dimensions the interview actually covered. Do not pad
            to three if the material only supports two.
            IMPORTANT: `value` is a short headline figure shown in large type
            (e.g. ">50 %", "290 kommuner", "Hög"). Keep it brief; put any
            explanation in `description`, not in `value`.
        annotations: Optional list of {field, text, severity} annotations
    """
    data = {"items": items}
    html = render_component("components/impact.html", data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "impact",
        "annotations": annotations or [],
    })
