"""MCP tool: write_implementation — renders the implementation story section."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component


@mcp.tool()
def write_implementation(
    heading: str,
    body_text: str,
) -> str:
    """Render the implementation story as a narrative section.

    Args:
        heading: Section heading (e.g. "Implementeringsberättelse")
        body_text: The implementation narrative — what happened, what worked, lessons learned
    """
    data = {"heading": heading, "body_text": body_text}
    html = render_component("components/implementation.html", data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "implementation",
    })
