"""Unit tests for the engine's per-turn status block builder.

The status block now carries only the agenda and the current focus. The page's
content lives in the conversation (the bot's tool calls and participant edit
notes), so it is intentionally absent here.
"""
from pagecraft.orchestrator.agenda import InterviewAgenda
from pagecraft.orchestrator.engine import _build_status_block
from pagecraft.registry import load_component_registry


def test_status_block_includes_agenda_and_focus():
    registry = load_component_registry()
    agenda = InterviewAgenda(registry)
    agenda.update_from_db({"situation": "agreed"})

    block = _build_status_block(agenda)
    assert "AKTUELL STATUS" in block
    assert "Agenda:" in block
    assert "Nuvarande fokus:" in block


def test_status_block_omits_page_content():
    """The block must not dump component content — that lives in the conversation."""
    registry = load_component_registry()
    agenda = InterviewAgenda(registry)
    agenda.update_from_db({"situation": "agreed"})

    block = _build_status_block(agenda)
    assert "Sidans nuvarande innehåll" not in block


def test_status_block_all_done():
    registry = load_component_registry()
    agenda = InterviewAgenda(registry)
    agenda.update_from_db({c.type: "agreed" for c in registry})

    block = _build_status_block(agenda)
    assert "Alla sektioner klara" in block
