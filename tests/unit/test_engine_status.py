"""Unit tests for the engine's per-turn status block builder."""
import json

from pagecraft.models.page import Component
from pagecraft.orchestrator.agenda import InterviewAgenda
from pagecraft.orchestrator.engine import _build_status_block, _format_component_data
from pagecraft.registry import load_component_registry


def test_format_flat_strings():
    out = _format_component_data({"title": "Hej", "description": "Kort text"})
    assert "- title: Hej" in out
    assert "- description: Kort text" in out


def test_format_skips_empty_strings():
    out = _format_component_data({"title": "Hej", "description": ""})
    assert "title" in out
    assert "description" not in out


def test_format_list_of_dicts():
    out = _format_component_data({"items": [
        {"label": "CO2", "value": "50%", "description": "Minskning"},
        {"label": "ROI", "value": "2x", "description": ""},
    ]})
    assert "[1] label: CO2; value: 50%; description: Minskning" in out
    assert "[2] label: ROI; value: 2x" in out


def test_format_list_of_strings():
    out = _format_component_data({"themes": ["Energi", "Mobilitet"]})
    assert "themes[1]: Energi" in out
    assert "themes[2]: Mobilitet" in out


def _component(ctype, status, data):
    return Component(
        id=1, page_id=1, component_type=ctype, display_order=1,
        html="<div></div>", data_json=json.dumps(data), status=status,
    )


def test_status_block_includes_agenda_and_content():
    registry = load_component_registry()
    agenda = InterviewAgenda(registry)
    components = [_component("situation", "agreed", {
        "current_situation": "Nuläget", "challenge": "Utmaningen", "solution": "Lösningen",
    })]
    agenda.update_from_db({"situation": "agreed"})

    block = _build_status_block(registry, agenda, components)
    assert "AKTUELL STATUS" in block
    assert "Agenda:" in block
    assert "Sidans nuvarande innehåll:" in block
    # uses the human label and the Swedish status word
    assert "Nuläge / Utmaning / Lösning (godkänd)" in block
    assert "Nuläget" in block


def test_status_block_empty_page():
    registry = load_component_registry()
    agenda = InterviewAgenda(registry)
    block = _build_status_block(registry, agenda, [])
    assert "Sidan är ännu tom" in block
