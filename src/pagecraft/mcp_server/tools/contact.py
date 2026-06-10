"""MCP tool: write_contact — renders contact information."""
import json

from pagecraft.mcp_server.server import mcp
from pagecraft.mcp_server.renderer import render_component


@mcp.tool()
def write_contact(
    name: str,
    title: str,
    organization: str,
    email: str | None = None,
    phone: str | None = None,
) -> str:
    """Render the contact information section.

    Args:
        name: Contact person's name
        title: Job title
        organization: Organization name
        email: Optional email address
        phone: Optional phone number
    """
    data = {
        "name": name,
        "title": title,
        "organization": organization,
        "email": email,
        "phone": phone,
    }
    html = render_component("components/contact.html", data)
    return json.dumps({
        "html": html,
        "data_json": data,
        "component_type": "contact",
    })
