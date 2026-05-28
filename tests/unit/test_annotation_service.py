"""Tests for the annotation persistence + path helpers."""
from pagecraft.services.annotation_service import (
    clear_annotations_for_page,
    create_annotation,
    flatten_paths,
    get_annotations_for_page,
    set_annotation_decision,
    value_at_path,
)
from pagecraft.services.page_service import create_page, save_component


def test_flatten_paths_mixed():
    data = {
        "title": "Hej",
        "items": [{"label": "CO2", "value": "50%"}],
        "themes": ["Energi", "Mobilitet"],
    }
    paths = flatten_paths(data)
    assert paths["title"] == "Hej"
    assert paths["items.0.label"] == "CO2"
    assert paths["items.0.value"] == "50%"
    assert paths["themes.0"] == "Energi"
    assert paths["themes.1"] == "Mobilitet"


def test_value_at_path():
    data = {"items": [{"value": "50%"}]}
    assert value_at_path(data, "items.0.value") == "50%"
    assert value_at_path(data, "nope") is None


async def _seed_component(db):
    page = await create_page(db, title="T")
    comp = await save_component(
        db, page_id=page.id, component_type="situation", display_order=3,
        html="<div></div>", data_json={"challenge": "X"},
    )
    return page, comp


async def test_create_and_get_annotations(db):
    page, comp = await _seed_component(db)
    await create_annotation(db, comp.id, "challenge", "Kolla detta", "verify")
    anns = await get_annotations_for_page(db, page.id)
    assert len(anns) == 1
    assert anns[0].field == "challenge"
    assert anns[0].severity == "verify"
    assert anns[0].decision == "pending"


async def test_clear_annotations(db):
    page, comp = await _seed_component(db)
    await create_annotation(db, comp.id, "challenge", "x", "verify")
    await clear_annotations_for_page(db, page.id)
    assert await get_annotations_for_page(db, page.id) == []


async def test_set_annotation_decision(db):
    page, comp = await _seed_component(db)
    ann_id = await create_annotation(db, comp.id, "challenge", "x", "verify")
    await set_annotation_decision(db, ann_id, "acknowledged", curator_note="ok", resolved_by="forskare")
    anns = await get_annotations_for_page(db, page.id)
    assert anns[0].decision == "acknowledged"
    assert anns[0].curator_note == "ok"
    assert anns[0].resolved == 1
