"""Tests for MCP tools — each tool renders HTML and returns correct structure."""
import json


def _call_tool(tool_fn, **kwargs) -> dict:
    result = tool_fn(**kwargs)
    return json.loads(result)


# --- write_hero ---

def test_hero_renders_title():
    from pagecraft.mcp_server.tools.hero import write_hero
    result = _call_tool(write_hero, title="Testprojekt", description="En beskrivning.")
    assert "Testprojekt" in result["html"]
    assert result["component_type"] == "hero"


def test_hero_data_json_preserved():
    from pagecraft.mcp_server.tools.hero import write_hero
    result = _call_tool(write_hero, title="T", description="D")
    assert result["data_json"]["title"] == "T"
    assert result["data_json"]["description"] == "D"


# --- write_metadata ---

def test_metadata_renders_municipality():
    from pagecraft.mcp_server.tools.metadata import write_metadata
    result = _call_tool(
        write_metadata,
        municipality="Göteborg", sector="Transport", twin_transition="Elbilar",
        themes=["Laddning", "Energi"], technical_solution=["Smart grid"],
    )
    assert "Göteborg" in result["html"]
    assert "Transport" in result["html"]
    assert result["component_type"] == "metadata"


def test_metadata_renders_tags():
    from pagecraft.mcp_server.tools.metadata import write_metadata
    result = _call_tool(
        write_metadata,
        municipality="Test", sector="Test", twin_transition="Test",
        themes=["Tema A", "Tema B"], technical_solution=["Teknik X"],
    )
    assert "Tema A" in result["html"]
    assert "Tema B" in result["html"]
    assert "Teknik X" in result["html"]


# --- write_situation ---

def test_situation_renders_three_columns():
    from pagecraft.mcp_server.tools.situation import write_situation
    result = _call_tool(
        write_situation,
        current_situation="Nuläget är X", challenge="Utmaningen är Y", solution="Lösningen är Z",
    )
    assert "Nuläget är X" in result["html"]
    assert "Utmaningen är Y" in result["html"]
    assert "Lösningen är Z" in result["html"]
    assert result["component_type"] == "situation"


def test_situation_data_json():
    from pagecraft.mcp_server.tools.situation import write_situation
    result = _call_tool(
        write_situation,
        current_situation="A", challenge="B", solution="C",
    )
    assert result["data_json"]["current_situation"] == "A"
    assert result["data_json"]["challenge"] == "B"
    assert result["data_json"]["solution"] == "C"


# --- write_kpis ---

def test_kpis_renders_three_cells():
    from pagecraft.mcp_server.tools.kpis import write_kpis
    result = _call_tool(
        write_kpis,
        co2_kpis={"value": "50%", "description": "Minskning"},
        profitability={"value": "Hög", "description": "Bra ROI"},
        investment={"value": "2M SEK", "description": "Initial investering"},
    )
    assert "50%" in result["html"]
    assert "Hög" in result["html"]
    assert "2M SEK" in result["html"]
    assert result["component_type"] == "kpis"


# --- write_impact ---

def test_impact_renders_three_cards():
    from pagecraft.mcp_server.tools.impact import write_impact
    result = _call_tool(
        write_impact,
        co2_reduction={"value": ">50%", "description": "Stor minskning"},
        cost_benefit={"value": "Hög", "description": "Positiv"},
        spread_potential={"value": "290 kommuner", "description": "Alla kommuner"},
    )
    assert ">50%" in result["html"]
    assert "Hög" in result["html"]
    assert "290 kommuner" in result["html"]
    assert result["component_type"] == "impact"


# --- write_implementation ---

def test_implementation_renders_narrative():
    from pagecraft.mcp_server.tools.implementation import write_implementation
    result = _call_tool(
        write_implementation,
        heading="Implementeringsberättelse",
        body_text="Vi började med en pilot i två kommuner.",
    )
    assert "Implementeringsberättelse" in result["html"]
    assert "Vi började med en pilot" in result["html"]
    assert result["component_type"] == "implementation"


# --- write_resources ---

def test_resources_renders():
    from pagecraft.mcp_server.tools.resources import write_resources
    result = _call_tool(
        write_resources,
        heading="Resurser", body_text="Det behövs projektledare och budget.",
    )
    assert "Resurser" in result["html"]
    assert "projektledare" in result["html"]
    assert result["component_type"] == "resources"


# --- write_getting_started ---

def test_getting_started_renders_steps():
    from pagecraft.mcp_server.tools.getting_started import write_getting_started
    result = _call_tool(
        write_getting_started,
        steps=[
            {"number": 1, "title": "Steg ett", "description": "Gör detta"},
            {"number": 2, "title": "Steg två", "description": "Sen detta"},
            {"number": 3, "title": "Steg tre", "description": "Till sist"},
        ],
    )
    assert "Steg ett" in result["html"]
    assert result["component_type"] == "getting_started"


# --- write_personas ---

def test_personas_renders():
    from pagecraft.mcp_server.tools.personas import write_personas
    result = _call_tool(
        write_personas,
        personas=[
            {"role": "Planerare", "benefit": "Bättre underlag"},
            {"role": "Politiker", "benefit": "Tydligare beslut"},
        ],
    )
    assert "Planerare" in result["html"]
    assert result["component_type"] == "personas"


# --- write_contact ---

def test_contact_renders():
    from pagecraft.mcp_server.tools.contact import write_contact
    result = _call_tool(
        write_contact,
        name="Anna Svensson", title="Projektledare", organization="Testkommun",
        email="anna@test.se",
    )
    assert "Anna Svensson" in result["html"]
    assert result["component_type"] == "contact"


def test_contact_minimal():
    from pagecraft.mcp_server.tools.contact import write_contact
    result = _call_tool(
        write_contact,
        name="Test", title="Test", organization="Test",
    )
    assert "Test" in result["html"]


# --- Cross-cutting ---

def test_all_tools_return_required_fields():
    """Every tool result must have html, data_json, component_type, annotations."""
    from pagecraft.mcp_server.tools.hero import write_hero
    from pagecraft.mcp_server.tools.metadata import write_metadata
    from pagecraft.mcp_server.tools.situation import write_situation
    from pagecraft.mcp_server.tools.kpis import write_kpis
    from pagecraft.mcp_server.tools.impact import write_impact
    from pagecraft.mcp_server.tools.implementation import write_implementation
    from pagecraft.mcp_server.tools.resources import write_resources
    from pagecraft.mcp_server.tools.getting_started import write_getting_started
    from pagecraft.mcp_server.tools.personas import write_personas
    from pagecraft.mcp_server.tools.contact import write_contact

    calls = [
        (write_hero, {"title": "T", "description": "D"}),
        (write_metadata, {"municipality": "M", "sector": "S", "twin_transition": "TT", "themes": ["T"], "technical_solution": ["TS"]}),
        (write_situation, {"current_situation": "A", "challenge": "B", "solution": "C"}),
        (write_kpis, {"co2_kpis": {"value": "V", "description": "D"}, "profitability": {"value": "V", "description": "D"}, "investment": {"value": "V", "description": "D"}}),
        (write_impact, {"co2_reduction": {"value": "V", "description": "D"}, "cost_benefit": {"value": "V", "description": "D"}, "spread_potential": {"value": "V", "description": "D"}}),
        (write_implementation, {"heading": "H", "body_text": "B"}),
        (write_resources, {"heading": "H", "body_text": "B"}),
        (write_getting_started, {"steps": [{"number": 1, "title": "S", "description": "D"}]}),
        (write_personas, {"personas": [{"role": "R", "benefit": "B"}]}),
        (write_contact, {"name": "N", "title": "T", "organization": "O"}),
    ]
    for fn, kwargs in calls:
        result = _call_tool(fn, **kwargs)
        assert "html" in result, f"{fn.__name__} missing html"
        assert "data_json" in result, f"{fn.__name__} missing data_json"
        assert "component_type" in result, f"{fn.__name__} missing component_type"
        assert "annotations" in result, f"{fn.__name__} missing annotations"
