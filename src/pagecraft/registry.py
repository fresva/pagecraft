from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ComponentDef:
    type: str
    label: str
    tool: str
    template: str
    page_order: int
    interview_order: int


def load_component_registry(yaml_path: Path | None = None) -> list[ComponentDef]:
    """Load component definitions sorted by page_order (layout order)."""
    if yaml_path is None:
        yaml_path = Path(__file__).parent / "components.yaml"
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return [
        ComponentDef(**comp)
        for comp in sorted(data["components"], key=lambda c: c["page_order"])
    ]


def interview_ordered(registry: list[ComponentDef]) -> list[ComponentDef]:
    """Return registry sorted by interview_order (conversation sequence)."""
    return sorted(registry, key=lambda c: c.interview_order)
