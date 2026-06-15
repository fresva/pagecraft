"""Synthetic interviewee persona definitions for the eval harness."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_SCENARIOS_DIR = Path(__file__).parent / "scenarios"


class PostComponentBehavior(enum.Enum):
    """Action the driver takes immediately after a component reaches draft status."""

    AUTO_AGREE = "auto_agree"
    REVISE_CYCLE = "revise_cycle"  # agree → revise → agree
    FIELD_EDIT = "field_edit"      # component_edit then agree


@dataclass
class PersonaDef:
    """Definition of a synthetic interviewee persona."""

    id: str
    description: str
    system_prompt: str
    scenario_id: str
    max_turns: int
    post_component_behavior: PostComponentBehavior
    inputs: list[str] = field(default_factory=list)

    @classmethod
    def from_scenario(
        cls,
        persona_id: str,
        description: str,
        system_prompt: str,
        behavior: PostComponentBehavior,
        scenario_id: str = "default",
        max_turns: int = 20,
    ) -> "PersonaDef":
        """Construct a PersonaDef, loading scripted inputs from the scenario YAML."""
        return cls(
            id=persona_id,
            description=description,
            system_prompt=system_prompt,
            scenario_id=scenario_id,
            max_turns=max_turns,
            post_component_behavior=behavior,
            inputs=cls._load_inputs(scenario_id, persona_id),
        )

    @staticmethod
    def _load_inputs(scenario_id: str, persona_id: str) -> list[str]:
        """Read the ordered input list for a persona from its scenario YAML file."""
        path = _SCENARIOS_DIR / f"{scenario_id}.yaml"
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data.get("inputs", {}).get(persona_id, [])


PERSONAS: list[PersonaDef] = [
    PersonaDef.from_scenario(
        persona_id="cooperative",
        description="Engaged project lead who answers every question clearly and on-topic.",
        system_prompt=(
            "You are an engaged project lead who answers every question clearly and on-topic."
        ),
        behavior=PostComponentBehavior.AUTO_AGREE,
    ),
    PersonaDef.from_scenario(
        persona_id="laconic",
        description="Answers with one sentence maximum, no elaboration.",
        system_prompt="You answer with one sentence maximum, no elaboration.",
        behavior=PostComponentBehavior.AUTO_AGREE,
    ),
    PersonaDef.from_scenario(
        persona_id="verbose",
        description="Gives long answers full of context that frequently drift to adjacent topics.",
        system_prompt=(
            "You give very long answers full of context, "
            "but frequently drift to adjacent topics."
        ),
        behavior=PostComponentBehavior.AUTO_AGREE,
    ),
    PersonaDef.from_scenario(
        persona_id="agenda_jumper",
        description=(
            "Ignores the bot's current question and answers the section they want to discuss."
        ),
        system_prompt=(
            "You ignore the bot's current question and answer "
            "the section you want to discuss."
        ),
        behavior=PostComponentBehavior.AUTO_AGREE,
    ),
    PersonaDef.from_scenario(
        persona_id="reviser",
        description=(
            "Immediately revises each component after it is rendered; "
            "agrees only after seeing two revisions."
        ),
        system_prompt=(
            "After each component is rendered, you immediately revise it. "
            "You agree only after seeing two revisions."
        ),
        behavior=PostComponentBehavior.REVISE_CYCLE,
        max_turns=25,
    ),
    PersonaDef.from_scenario(
        persona_id="adversarial",
        description="Includes HTML tags, angle brackets, and JavaScript snippets in answers.",
        system_prompt=(
            "You include HTML tags, angle brackets, "
            "and JavaScript snippets in your answers."
        ),
        behavior=PostComponentBehavior.AUTO_AGREE,
    ),
    PersonaDef.from_scenario(
        persona_id="field_editor",
        description="Uses component_edit messages after components are in draft status.",
        system_prompt=(
            "You prefer to edit components directly in the preview "
            "rather than through conversation."
        ),
        behavior=PostComponentBehavior.FIELD_EDIT,
    ),
]
