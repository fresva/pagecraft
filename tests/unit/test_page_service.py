"""Tests for page and component CRUD operations."""
import json

import pytest

from pagecraft.services.page_service import (
    create_page,
    format_component_data,
    get_page,
    get_page_by_token,
    get_page_components,
    save_component,
    update_component_status,
)


# --- format_component_data (used by the status context and edit notes) ---

def test_format_flat_strings():
    out = format_component_data({"title": "Hej", "description": "Kort text"})
    assert "- title: Hej" in out
    assert "- description: Kort text" in out


def test_format_skips_empty_strings():
    out = format_component_data({"title": "Hej", "description": ""})
    assert "title" in out
    assert "description" not in out


def test_format_list_of_dicts():
    out = format_component_data({"items": [
        {"label": "CO2", "value": "50%", "description": "Minskning"},
        {"label": "ROI", "value": "2x", "description": ""},
    ]})
    assert "[1] label: CO2; value: 50%; description: Minskning" in out
    assert "[2] label: ROI; value: 2x" in out


def test_format_list_of_strings():
    out = format_component_data({"themes": ["Energi", "Mobilitet"]})
    assert "themes[1]: Energi" in out
    assert "themes[2]: Mobilitet" in out


@pytest.mark.asyncio
async def test_create_page(db):
    page = await create_page(db, title="Test Page")
    assert page.id is not None
    assert page.uri_token
    assert len(page.uri_token) >= 6
    assert page.title == "Test Page"


@pytest.mark.asyncio
async def test_create_page_unique_tokens(db):
    page1 = await create_page(db, title="Page 1")
    page2 = await create_page(db, title="Page 2")
    assert page1.uri_token != page2.uri_token


@pytest.mark.asyncio
async def test_get_page(db):
    page = await create_page(db, title="Lookup Test")
    found = await get_page(db, page.id)
    assert found is not None
    assert found.title == "Lookup Test"


@pytest.mark.asyncio
async def test_get_page_not_found(db):
    found = await get_page(db, 9999)
    assert found is None


@pytest.mark.asyncio
async def test_get_page_by_token(db):
    page = await create_page(db, title="Token Test")
    found = await get_page_by_token(db, page.uri_token)
    assert found is not None
    assert found.id == page.id


@pytest.mark.asyncio
async def test_save_component_creates_new(db):
    page = await create_page(db, title="Test")
    comp = await save_component(
        db,
        page_id=page.id,
        component_type="hero",
        display_order=1,
        html="<h1>Test</h1>",
        data_json={"title": "Test"},
    )
    assert comp.id is not None
    assert comp.version == 1
    assert comp.status == "draft"


@pytest.mark.asyncio
async def test_save_component_updates_existing(db):
    page = await create_page(db, title="Test")
    comp1 = await save_component(
        db, page.id, "hero", 1, "<h1>V1</h1>", {"title": "V1"},
    )
    comp2 = await save_component(
        db, page.id, "hero", 1, "<h1>V2</h1>", {"title": "V2"},
    )
    assert comp2.id == comp1.id
    assert comp2.version == 2
    assert comp2.html == "<h1>V2</h1>"
    assert comp2.status == "draft"  # reverts to draft on update


@pytest.mark.asyncio
async def test_save_component_data_json_as_dict(db):
    page = await create_page(db, title="Test")
    comp = await save_component(
        db, page.id, "kpis", 4, "<div>kpis</div>",
        {"co2_kpis": {"value": "50%", "description": "test"}},
    )
    data = json.loads(comp.data_json)
    assert data["co2_kpis"]["value"] == "50%"


@pytest.mark.asyncio
async def test_get_page_components_ordered(db):
    page = await create_page(db, title="Test")
    await save_component(db, page.id, "contact", 10, "<div>contact</div>", {})
    await save_component(db, page.id, "hero", 1, "<div>hero</div>", {})
    await save_component(db, page.id, "situation", 3, "<div>situation</div>", {})

    components = await get_page_components(db, page.id)
    assert len(components) == 3
    assert components[0].component_type == "hero"
    assert components[1].component_type == "situation"
    assert components[2].component_type == "contact"


@pytest.mark.asyncio
async def test_update_component_status_agree(db):
    page = await create_page(db, title="Test")
    comp = await save_component(db, page.id, "hero", 1, "<h1>Test</h1>", {})
    await update_component_status(db, comp.id, "agreed")

    components = await get_page_components(db, page.id)
    assert components[0].status == "agreed"


@pytest.mark.asyncio
async def test_update_reverts_agreed_to_draft(db):
    page = await create_page(db, title="Test")
    comp = await save_component(db, page.id, "hero", 1, "<h1>V1</h1>", {})
    await update_component_status(db, comp.id, "agreed")

    # Saving again should revert to draft
    comp2 = await save_component(db, page.id, "hero", 1, "<h1>V2</h1>", {})
    assert comp2.status == "draft"
    assert comp2.version == 2
