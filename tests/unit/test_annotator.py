"""Tests for the post-processing annotator."""
from pathlib import Path

from pagecraft.orchestrator.annotator import (
    _canned_annotations,
    _parse_annotations,
    generate_annotations_for_page,
)
from pagecraft.orchestrator.prompt_loader import PromptLoader
from pagecraft.registry import load_component_registry
from pagecraft.services.annotation_service import get_annotations_for_page
from pagecraft.services.page_service import create_page, save_component

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


# --- parsing ---

def test_parse_plain_json():
    data = {"current_situation": "X"}
    text = '[{"field": "current_situation", "severity": "verify", "message": "Kolla"}]'
    out = _parse_annotations(text, data)
    assert out == [{"field": "current_situation", "severity": "verify", "message": "Kolla"}]


def test_parse_fenced_json():
    data = {"current_situation": "X"}
    text = 'Här är resultatet:\n```json\n[{"field":"current_situation","severity":"missing","message":"Saknas"}]\n```'
    out = _parse_annotations(text, data)
    assert len(out) == 1
    assert out[0]["severity"] == "missing"


def test_parse_drops_unknown_field_and_bad_severity():
    data = {"current_situation": "X"}
    text = (
        '[{"field":"nope","severity":"verify","message":"a"},'
        '{"field":"current_situation","severity":"weird","message":"b"}]'
    )
    out = _parse_annotations(text, data)
    # unknown field dropped; bad severity coerced to verify
    assert out == [{"field": "current_situation", "severity": "verify", "message": "b"}]


def test_parse_empty_or_garbage():
    assert _parse_annotations("", {"a": "b"}) == []
    assert _parse_annotations("ingen json här", {"a": "b"}) == []


# --- canned ---

def test_canned_only_existing_fields():
    # situation canned targets "challenge"
    assert _canned_annotations("situation", {"challenge": "X"})
    assert _canned_annotations("situation", {"solution": "Y"}) == []


# --- end to end (demo / canned path) ---

async def test_generate_annotations_demo_mode(db):
    page = await create_page(db, title="T")
    await save_component(
        db, page_id=page.id, component_type="situation", display_order=3,
        html="<div></div>",
        data_json={"current_situation": "A", "challenge": "B", "solution": "C"},
    )
    registry = load_component_registry()
    loader = PromptLoader(PROMPTS_DIR)

    count = await generate_annotations_for_page(db, page.id, registry, None, loader)
    assert count == 1
    anns = await get_annotations_for_page(db, page.id)
    assert anns[0].field == "challenge"
    assert anns[0].severity == "assumption"


async def test_generate_is_idempotent(db):
    page = await create_page(db, title="T")
    await save_component(
        db, page_id=page.id, component_type="situation", display_order=3,
        html="<div></div>", data_json={"challenge": "B"},
    )
    registry = load_component_registry()
    loader = PromptLoader(PROMPTS_DIR)

    await generate_annotations_for_page(db, page.id, registry, None, loader)
    await generate_annotations_for_page(db, page.id, registry, None, loader)
    anns = await get_annotations_for_page(db, page.id)
    assert len(anns) == 1  # cleared and regenerated, not duplicated
