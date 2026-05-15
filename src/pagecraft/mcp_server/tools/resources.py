"""MCP tool: write_resources — renders the resources section."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component, apply_annotations


@mcp.tool()
def write_resources(
    heading: str,
    body_text: str,
    annotations: list[dict] | None = None,
) -> str:
    """Render the resources section describing what is needed.

    Args:
        heading: Section heading (e.g. "Resurser")
        body_text: Description of required resources
        annotations: Optional list of {field, text, severity} annotations
    """
    data = {"heading": heading, "body_text": body_text}
    display_data = apply_annotations(data, annotations)
    html = render_component("components/resources.html", display_data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "resources",
        "annotations": annotations or [],
    })
