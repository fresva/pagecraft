"""MCP tool: write_situation — renders the 3-column situation/challenge/solution section."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component, apply_annotations


@mcp.tool()
def write_situation(
    current_situation: str,
    challenge: str,
    solution: str,
    annotations: list[dict] | None = None,
) -> str:
    """Render the situation analysis as a three-column layout.

    Args:
        current_situation: Description of the current situation (Nuläge)
        challenge: Description of the challenge (Utmaning)
        solution: Description of the solution (Lösning)
        annotations: Optional list of {field, text, severity} annotations
    """
    data = {
        "current_situation": current_situation,
        "challenge": challenge,
        "solution": solution,
    }
    display_data = apply_annotations(data, annotations)
    html = render_component("components/situation.html", display_data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "situation",
        "annotations": annotations or [],
    })
