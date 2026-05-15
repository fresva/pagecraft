"""Tests for PromptLoader — loading and injecting prompt files."""
from pathlib import Path

from pagecraft.orchestrator.prompt_loader import PromptLoader

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def test_system_prompt_loads():
    loader = PromptLoader(PROMPTS_DIR)
    result = loader.system_prompt(agenda_state="test-agenda", current_section="Intro")
    assert "test-agenda" in result
    assert "Intro" in result


def test_system_prompt_replaces_placeholders():
    loader = PromptLoader(PROMPTS_DIR)
    result = loader.system_prompt(agenda_state="[x] Done", current_section="Nyckeltal")
    assert "{{AGENDA}}" not in result
    assert "{{CURRENT_SECTION}}" not in result
    assert "[x] Done" in result
    assert "Nyckeltal" in result


def test_system_prompt_contains_interview_guidance():
    """The unified prompt should contain guidance for all component types."""
    loader = PromptLoader(PROMPTS_DIR)
    result = loader.system_prompt(agenda_state="", current_section="")
    assert "write_situation" in result
    assert "write_hero" in result
    assert "write_kpis" in result
    assert "write_metadata" in result
    assert "write_contact" in result
    assert "write_implementation" in result
    assert "write_resources" in result
    assert "write_impact" in result
    assert "write_getting_started" in result
    assert "write_personas" in result


def test_system_prompt_mentions_synthesis_components():
    """Hero and metadata are synthesis components — prompt should indicate that."""
    loader = PromptLoader(PROMPTS_DIR)
    result = loader.system_prompt(agenda_state="", current_section="")
    assert "syntes" in result.lower()


def test_annotation_guidance_loads():
    loader = PromptLoader(PROMPTS_DIR)
    result = loader.annotation_guidance()
    assert len(result) > 0
    assert "annotation" in result.lower() or "verify" in result.lower()


def test_loader_with_missing_dir():
    """PromptLoader with nonexistent dir returns empty strings."""
    loader = PromptLoader(Path("/nonexistent/path"))
    assert loader.system_prompt("x") == ""
    assert loader.annotation_guidance() == ""


def test_no_section_prompt_method():
    """section_prompt was removed — PromptLoader should not have it."""
    loader = PromptLoader(PROMPTS_DIR)
    assert not hasattr(loader, "section_prompt")
