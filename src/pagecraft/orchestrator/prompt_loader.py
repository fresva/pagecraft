"""Loads prompt files from the prompts/ directory at startup.

Prompts are Markdown files with {{PLACEHOLDER}} tokens that get replaced
with dynamic content (agenda state, current section, etc.). File contents
are read once at construction time; restart the app to pick up edits.
"""
from pathlib import Path


class PromptLoader:
    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir
        self._cache: dict[str, str] = {}

    def _load(self, filename: str) -> str:
        if filename not in self._cache:
            path = self.prompts_dir / filename
            self._cache[filename] = path.read_text(encoding="utf-8") if path.exists() else ""
        return self._cache[filename]

    def system_prompt(self, agenda_state: str, current_section: str = "") -> str:
        """Return system.md with dynamic state injected."""
        content = self._load("system.md")
        content = content.replace("{{AGENDA}}", agenda_state)
        content = content.replace("{{CURRENT_SECTION}}", current_section)
        return content

    def annotation_guidance(self) -> str:
        """Return annotation instructions."""
        return self._load("annotation_guidance.md")
