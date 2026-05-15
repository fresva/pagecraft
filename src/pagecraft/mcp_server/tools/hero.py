"""MCP tool: write_hero — renders the hero/intro section."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component, apply_annotations


@mcp.tool()
def write_hero(
    title: str,
    description: str,
    annotations: list[dict] | None = None,
) -> str:
    """Render the hero/intro section of the case study page.

    Args:
        title: The project or initiative name
        description: 2-3 sentence summary of the project
        annotations: Optional list of {field, text, severity} annotations
    """
    data = {"title": title, "description": description}
    display_data = apply_annotations(data, annotations)
    html = render_component("components/hero.html", display_data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "hero",
        "annotations": annotations or [],
    })
