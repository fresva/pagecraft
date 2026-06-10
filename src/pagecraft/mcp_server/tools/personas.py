"""MCP tool: write_personas — renders stakeholder personas."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component


@mcp.tool()
def write_personas(
    personas: list[dict],
) -> str:
    """Render the stakeholder personas section.

    Args:
        personas: List of {role, benefit, quote?} dicts (2-4 items)
    """
    data = {"personas": personas}
    html = render_component("components/personas.html", data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "personas",
    })
