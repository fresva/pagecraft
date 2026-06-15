"""Synthetic interviewee persona definitions for the eval harness."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass
class PersonaDef:
    """Definition of a synthetic interviewee persona."""

    id: str
    description: str
    system_prompt: str
    max_turns: int = 20


def _load_prompt(persona_id: str) -> str:
    return (_PROMPTS_DIR / f"persona_{persona_id}.txt").read_text(encoding="utf-8").strip()


PERSONAS: list[PersonaDef] = [
    PersonaDef(
        id="cooperative",
        description="Engaged project lead who answers every question clearly and on-topic.",
        system_prompt=_load_prompt("cooperative"),
    ),
    PersonaDef(
        id="laconic",
        description="Answers with one sentence maximum, no elaboration.",
        system_prompt=_load_prompt("laconic"),
    ),
    PersonaDef(
        id="verbose",
        description="Gives long answers full of context that frequently drift to adjacent topics.",
        system_prompt=_load_prompt("verbose"),
    ),
    PersonaDef(
        id="agenda_jumper",
        description="Ignores the bot's current question and answers the section they want to discuss.",
        system_prompt=_load_prompt("agenda_jumper"),
    ),
    PersonaDef(
        id="reviser",
        description="Immediately revises each component after it is rendered.",
        system_prompt=_load_prompt("reviser"),
        max_turns=25,
    ),
    PersonaDef(
        id="adversarial",
        description="Includes HTML tags, angle brackets, and JavaScript snippets in answers.",
        system_prompt=_load_prompt("adversarial"),
    ),
    PersonaDef(
        id="field_editor",
        description="Prefers editing components directly in the preview rather than through conversation.",
        system_prompt=_load_prompt("field_editor"),
    ),
]
