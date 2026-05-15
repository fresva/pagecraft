"""MCP tool: write_getting_started — renders the getting started steps."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component


@mcp.tool()
def write_getting_started(
    steps: list[dict],
    annotations: list[dict] | None = None,
) -> str:
    """Render the getting started section with numbered steps.

    Args:
        steps: List of {number, title, description} dicts (typically 3)
        annotations: Optional list of {field, text, severity} annotations
    """
    data = {"steps": steps}
    html = render_component("components/getting_started.html", data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "getting_started",
        "annotations": annotations or [],
    })
