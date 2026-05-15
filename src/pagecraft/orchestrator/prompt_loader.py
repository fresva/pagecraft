"""Loads prompt files from the prompts/ directory at runtime.

Prompts are Markdown files with {{PLACEHOLDER}} tokens that get replaced
with dynamic content (agenda state, current section, etc.).
"""
from pathlib import Path


class PromptLoader:
    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir

    def _load(self, filename: str) -> str:
        path = self.prompts_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def system_prompt(self, agenda_state: str, current_section: str = "") -> str:
        """Load system.md and inject dynamic state."""
        content = self._load("system.md")
        content = content.replace("{{AGENDA}}", agenda_state)
        content = content.replace("{{CURRENT_SECTION}}", current_section)
        return content

    def annotation_guidance(self) -> str:
        """Load annotation instructions."""
        return self._load("annotation_guidance.md")
