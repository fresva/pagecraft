"""Bridge between the orchestrator and MCP tools.

Provides tool discovery (list_tools) and invocation (call_tool),
plus conversion to OpenAI function-calling format.
"""
import json
import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


class MCPBridge:
    def __init__(self, mcp_server: FastMCP):
        self._server = mcp_server

    async def list_tools(self) -> list[dict]:
        """List all registered tools with their schemas."""
        tools = await self._server.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Invoke a tool by name and return its parsed result."""
        logger.info(f"Calling MCP tool: {name} with {list(arguments.keys())}")
        result = await self._server.call_tool(name, arguments)

        # FastMCP.call_tool returns (list[TextContent], ...) tuple
        content_list = result[0] if isinstance(result, tuple) else result
        if content_list and len(content_list) > 0:
            text_content = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
            return json.loads(text_content)

        raise ValueError(f"Tool {name} returned no content")

    def tools_to_openai_functions(self, tools: list[dict]) -> list[dict]:
        """Convert MCP tool schemas to OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool in tools
        ]
