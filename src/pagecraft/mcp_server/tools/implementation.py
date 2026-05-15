"""MCP tool: write_implementation — renders the implementation story section."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component, apply_annotations


@mcp.tool()
def write_implementation(
    heading: str,
    body_text: str,
    annotations: list[dict] | None = None,
) -> str:
    """Render the implementation story as a narrative section.

    Args:
        heading: Section heading (e.g. "Implementeringsberättelse")
        body_text: The implementation narrative — what happened, what worked, lessons learned
        annotations: Optional list of {field, text, severity} annotations
    """
    data = {"heading": heading, "body_text": body_text}
    display_data = apply_annotations(data, annotations)
    html = render_component("components/implementation.html", display_data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "implementation",
        "annotations": annotations or [],
    })
