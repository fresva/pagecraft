"""MCP tool: write_metadata — renders the metadata/tags bar."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component


@mcp.tool()
def write_metadata(
    municipality: str,
    sector: str,
    twin_transition: str,
    themes: list[str],
    technical_solution: list[str],
    annotations: list[dict] | None = None,
) -> str:
    """Render the metadata bar with municipality, sector, and tags.

    Args:
        municipality: Municipality or organization name
        sector: Primary sector (e.g. "Transport och Mobilitet")
        twin_transition: How this enables twin transition
        themes: List of theme tags
        technical_solution: List of technical solution tags
        annotations: Optional list of {field, text, severity} annotations
    """
    data = {
        "municipality": municipality,
        "sector": sector,
        "twin_transition": twin_transition,
        "themes": themes,
        "technical_solution": technical_solution,
    }
    html = render_component("components/metadata.html", data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "metadata",
        "annotations": annotations or [],
    })
