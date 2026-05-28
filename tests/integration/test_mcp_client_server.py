"""Integration tests for MCP tool discovery and invocation via bridge."""
import pytest

from pagecraft.mcp_server.server import mcp
from pagecraft.orchestrator.mcp_bridge import MCPBridge


@pytest.fixture(scope="module")
def bridge():
    return MCPBridge(mcp)


@pytest.mark.asyncio
async def test_all_ten_tools_discovered(bridge):
    tools = await bridge.list_tools()
    assert len(tools) == 10


@pytest.mark.asyncio
async def test_tool_names_match_registry(bridge, component_registry):
    tools = await bridge.list_tools()
    tool_names = {t["name"] for t in tools}
    registry_tools = {c.tool for c in component_registry}
    assert tool_names == registry_tools


@pytest.mark.asyncio
async def test_all_tools_have_schemas(bridge):
    tools = await bridge.list_tools()
    for tool in tools:
        assert "input_schema" in tool
        assert "properties" in tool["input_schema"]


@pytest.mark.asyncio
async def test_openai_function_format(bridge):
    tools = await bridge.list_tools()
    funcs = bridge.tools_to_openai_functions(tools)
    assert len(funcs) == 10
    for f in funcs:
        assert f["type"] == "function"
        assert "name" in f["function"]
        assert "description" in f["function"]
        assert "parameters" in f["function"]


@pytest.mark.asyncio
async def test_tool_invocation_returns_valid_component(bridge):
    result = await bridge.call_tool("write_hero", {
        "title": "Test", "description": "Test desc",
    })
    assert "html" in result
    assert "data_json" in result
    assert "component_type" in result
    assert result["component_type"] == "hero"
    assert len(result["html"]) > 50


@pytest.mark.asyncio
async def test_all_tools_callable_with_minimal_args(bridge):
    """Every tool should be callable and return a valid component dict."""
    minimal_args = {
        "write_hero": {"title": "T", "description": "D"},
        "write_metadata": {
            "municipality": "M", "sector": "S", "twin_transition": "TT",
            "themes": ["T1"], "technical_solution": ["TS1"],
        },
        "write_situation": {"current_situation": "C", "challenge": "Ch", "solution": "S"},
        "write_kpis": {"items": [{"label": "L", "value": "V", "description": "D"}]},
        "write_impact": {"items": [{"label": "L", "value": "V", "description": "D"}]},
        "write_implementation": {"heading": "H", "body_text": "B"},
        "write_resources": {"heading": "H", "body_text": "B"},
        "write_getting_started": {"steps": [{"number": 1, "title": "T", "description": "D"}]},
        "write_personas": {"personas": [{"role": "R", "benefit": "B"}]},
        "write_contact": {"name": "N", "title": "T", "organization": "O"},
    }
    for tool_name, args in minimal_args.items():
        result = await bridge.call_tool(tool_name, args)
        assert "html" in result, f"{tool_name} missing html"
        assert "data_json" in result, f"{tool_name} missing data_json"
        assert "component_type" in result, f"{tool_name} missing component_type"
