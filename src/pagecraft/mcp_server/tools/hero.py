"""MCP tool: write_hero — renders the hero/intro section."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component


@mcp.tool()
def write_hero(
    title: str,
    description: str,
) -> str:
    """Render the hero/intro section of the case study page.

    Args:
        title: The project or initiative name
        description: 2-3 sentence summary of the project
    """
    data = {"title": title, "description": description}
    html = render_component("components/hero.html", data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "hero",
    })
