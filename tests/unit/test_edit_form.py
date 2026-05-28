"""Unit tests for the structured edit-form service."""
from pagecraft.services.edit_form import apply_edits, build_edit_form_html


# --- apply_edits ---

def test_apply_edits_flat_field():
    data = {"title": "Old", "description": "Keep"}
    out = apply_edits(data, {"title": "New"})
    assert out["title"] == "New"
    assert out["description"] == "Keep"
    # original is not mutated
    assert data["title"] == "Old"


def test_apply_edits_list_of_dicts():
    data = {"items": [{"label": "A", "value": "1"}, {"label": "B", "value": "2"}]}
    out = apply_edits(data, {"items.1.value": "99"})
    assert out["items"][1]["value"] == "99"
    assert out["items"][0]["value"] == "1"


def test_apply_edits_list_of_strings():
    data = {"themes": ["X", "Y"]}
    out = apply_edits(data, {"themes.0": "Z"})
    assert out["themes"] == ["Z", "Y"]


def test_apply_edits_ignores_unknown_paths():
    data = {"title": "T"}
    out = apply_edits(data, {"nope": "x", "items.5.value": "y"})
    assert out == {"title": "T"}


def test_apply_edits_does_not_overwrite_structure():
    data = {"items": [{"label": "A"}]}
    out = apply_edits(data, {"items": "boom"})
    assert out["items"] == [{"label": "A"}]


# --- build_edit_form_html ---

def test_build_edit_form_contains_paths():
    data = {"title": "Hej", "items": [{"label": "CO2", "value": "50%"}]}
    html = build_edit_form_html(7, "Introduktion", data)
    assert 'data-component-id="7"' in html
    assert 'name="title"' in html
    assert 'name="items.0.label"' in html
    assert 'name="items.0.value"' in html
    assert "Hej" in html


def test_build_edit_form_escapes_values():
    html = build_edit_form_html(1, "L", {"title": "<script>"})
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
