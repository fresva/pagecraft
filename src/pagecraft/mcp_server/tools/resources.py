"""MCP tool: write_resources — renders the resources section."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component


@mcp.tool()
def write_resources(
    heading: str,
    body_text: str,
) -> str:
    """Render the resources section describing what is needed.

    Args:
        heading: Section heading (e.g. "Resurser")
        body_text: Description of required resources
    """
    data = {"heading": heading, "body_text": body_text}
    html = render_component("components/resources.html", data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "resources",
    })
