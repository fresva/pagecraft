"""MCP server instance with all PageCraft tools registered."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pagecraft-tools")

# Import tool modules to register them on the mcp instance.
# Each module uses @mcp.tool() to register its tool function.
from pagecraft.mcp_server.tools import (  # noqa: F401, E402
    contact,
    getting_started,
    hero,
    impact,
    implementation,
    kpis,
    metadata,
    personas,
    resources,
    situation,
)
