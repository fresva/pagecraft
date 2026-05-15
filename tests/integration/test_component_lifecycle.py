"""Integration tests for component lifecycle: draft → agreed → revise → draft."""
import json

import pytest

from pagecraft.services.page_service import (
    create_page,
    get_page_components,
    save_component,
    update_component_status,
)


@pytest.mark.asyncio
async def test_full_lifecycle_draft_agree_revise(db):
    """Component goes draft → agreed → back to draft on re-save."""
    page = await create_page(db, title="Lifecycle Test")

    # Create component (draft)
    comp = await save_component(db, page.id, "hero", 1, "<h1>V1</h1>", {"v": 1})
    assert comp.status == "draft"
    assert comp.version == 1

    # Agree
    await update_component_status(db, comp.id, "agreed")
    components = await get_page_components(db, page.id)
    assert components[0].status == "agreed"

    # Re-save (revise) — should go back to draft and increment version
    comp2 = await save_component(db, page.id, "hero", 1, "<h1>V2</h1>", {"v": 2})
    assert comp2.status == "draft"
    assert comp2.version == 2


@pytest.mark.asyncio
async def test_multiple_components_independent_status(db):
    """Each component has independent status."""
    page = await create_page(db, title="Multi Test")

    c1 = await save_component(db, page.id, "hero", 1, "<h1>Hero</h1>", {})
    c2 = await save_component(db, page.id, "situation", 3, "<div>Situation</div>", {})

    await update_component_status(db, c1.id, "agreed")

    components = await get_page_components(db, page.id)
    statuses = {c.component_type: c.status for c in components}
    assert statuses["hero"] == "agreed"
    assert statuses["situation"] == "draft"


@pytest.mark.asyncio
async def test_component_version_only_increments_on_update(db):
    """Version starts at 1 and increments only when content changes."""
    page = await create_page(db, title="Version Test")

    comp = await save_component(db, page.id, "hero", 1, "<h1>V1</h1>", {})
    assert comp.version == 1

    # Status change doesn't increment version
    await update_component_status(db, comp.id, "agreed")
    components = await get_page_components(db, page.id)
    assert components[0].version == 1

    # Content change does
    comp2 = await save_component(db, page.id, "hero", 1, "<h1>V2</h1>", {})
    assert comp2.version == 2

    comp3 = await save_component(db, page.id, "hero", 1, "<h1>V3</h1>", {})
    assert comp3.version == 3


@pytest.mark.asyncio
async def test_data_json_preserved_through_lifecycle(db):
    """data_json survives the full lifecycle."""
    page = await create_page(db, title="JSON Test")

    data = {"title": "Test", "metrics": [{"value": "50%"}]}
    comp = await save_component(db, page.id, "hero", 1, "<h1>Test</h1>", data)

    parsed = json.loads(comp.data_json)
    assert parsed["title"] == "Test"
    assert parsed["metrics"][0]["value"] == "50%"

    # Update with new data
    data2 = {"title": "Updated", "metrics": [{"value": "75%"}]}
    comp2 = await save_component(db, page.id, "hero", 1, "<h1>Updated</h1>", data2)

    parsed2 = json.loads(comp2.data_json)
    assert parsed2["title"] == "Updated"
    assert parsed2["metrics"][0]["value"] == "75%"
