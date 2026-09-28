"""Tests for PromptLoader — loading and injecting prompt files."""

from pathlib import Path

from pagecraft.orchestrator.prompt_loader import PromptLoader

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def test_system_prompt_loads():
    loader = PromptLoader(PROMPTS_DIR)
    result = loader.system_prompt()
    assert len(result) > 0
    assert "PageCraft" in result


def test_system_prompt_has_no_legacy_placeholders():
    """Dynamic state is injected by the engine now, not via template tokens."""
    loader = PromptLoader(PROMPTS_DIR)
    result = loader.system_prompt()
    assert "{{AGENDA}}" not in result
    assert "{{CURRENT_SECTION}}" not in result


def test_system_prompt_contains_interview_guidance():
    """The unified prompt should contain guidance for all component types."""
    loader = PromptLoader(PROMPTS_DIR)
    result = loader.system_prompt()
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
    result = loader.system_prompt()
    assert "synthesis" in result.lower()


def test_loader_with_missing_dir():
    """PromptLoader with nonexistent dir returns empty strings."""
    loader = PromptLoader(Path("/nonexistent/path"))
    assert loader.system_prompt() == ""


def test_no_section_prompt_method():
    """section_prompt was removed — PromptLoader should not have it."""
    loader = PromptLoader(PROMPTS_DIR)
    assert not hasattr(loader, "section_prompt")


def test_opening_is_split_into_separate_messages():
    """opening.md is split on `---` so the greeting and first question
    arrive as two chat bubbles instead of one block of text."""
    loader = PromptLoader(PROMPTS_DIR)
    messages = loader.opening_messages()
    assert len(messages) == 2
    assert messages[0].startswith("Hej och välkommen!")
    assert messages[1].startswith("Vi börjar med lite bakgrund")


def test_opening_drops_info_url_line_when_unset():
    """No unresolved {{INFO_URL}} token may reach the interviewee."""
    loader = PromptLoader(PROMPTS_DIR)
    messages = loader.opening_messages()
    assert all("{{INFO_URL}}" not in m for m in messages)
    assert all("Läs gärna mer" not in m for m in messages)


def test_opening_substitutes_info_url_when_set():
    loader = PromptLoader(PROMPTS_DIR)
    messages = loader.opening_messages("https://example.org/info")
    assert len(messages) == 2
    assert "https://example.org/info" in messages[0]
    assert all("{{INFO_URL}}" not in m for m in messages)


def test_opening_parts_have_no_separator_or_edge_whitespace():
    loader = PromptLoader(PROMPTS_DIR)
    for message in loader.opening_messages("https://example.org/info"):
        assert message == message.strip()
        assert "---" not in message


def test_opening_with_missing_dir_returns_empty_list():
    loader = PromptLoader(Path("/nonexistent/path"))
    assert loader.opening_messages() == []


def test_no_singular_opening_message_method():
    """opening_message was replaced by opening_messages (plural)."""
    loader = PromptLoader(PROMPTS_DIR)
    assert not hasattr(loader, "opening_message")
