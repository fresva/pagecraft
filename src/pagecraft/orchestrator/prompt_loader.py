"""Loads prompt files from the prompts/ directory at startup.

Prompts are Markdown files with {{PLACEHOLDER}} tokens that get replaced
with dynamic content (agenda state, current section, etc.). File contents
are read once at construction time; restart the app to pick up edits.
"""

import re
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

    def system_prompt(self) -> str:
        """Return the static system prompt.

        Dynamic state (agenda + current page content) is no longer injected here
        — the engine adds it as a separate status message each turn so this prompt
        stays byte-identical between turns and remains prompt-cacheable.
        """
        return self._load("system.md")

    def opening_messages(self, info_url: str = "") -> list[str]:
        """Return the scripted opening as one chat message per part.

        opening.md is split on a line containing only `---`. Each part becomes
        its own chat bubble so the greeting and the first question arrive
        separately instead of as one block of text.

        If info_url is empty, any line referencing the {{INFO_URL}} placeholder
        is dropped so no unresolved token reaches the interviewee.
        """
        content = self._load("opening.md")
        if info_url:
            content = content.replace("{{INFO_URL}}", info_url)
        else:
            content = "\n".join(line for line in content.splitlines() if "{{INFO_URL}}" not in line)
        parts = re.split(r"^---$", content, flags=re.MULTILINE)
        return [stripped for part in parts if (stripped := part.strip())]
