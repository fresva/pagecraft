"""Interview agenda tracker driven by components.yaml.

Tracks which sections have been rendered and agreed.
"""
from enum import Enum

from pagecraft.registry import ComponentDef


class SectionStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DRAFT = "draft"
    AGREED = "agreed"


class AgendaItem:
    def __init__(self, component_type: str, label: str):
        self.component_type = component_type
        self.label = label
        self.status = SectionStatus.PENDING


class InterviewAgenda:
    def __init__(self, registry: list[ComponentDef]):
        sorted_reg = sorted(registry, key=lambda c: c.interview_order)
        self.items = [AgendaItem(c.type, c.label) for c in sorted_reg]

    def current_section(self) -> AgendaItem | None:
        """Return the first non-agreed section, or None if all done."""
        for item in self.items:
            if item.status != SectionStatus.AGREED:
                return item
        return None

    def update_from_db(self, component_statuses: dict[str, str]) -> None:
        """Sync agenda state from DB component statuses."""
        for item in self.items:
            db_status = component_statuses.get(item.component_type)
            if db_status == "agreed":
                item.status = SectionStatus.AGREED
            elif db_status == "draft":
                item.status = SectionStatus.DRAFT
            # else stays PENDING

        # Mark the first non-agreed, non-draft item as ACTIVE
        for item in self.items:
            if item.status == SectionStatus.PENDING:
                item.status = SectionStatus.ACTIVE
                break

    def to_prompt_fragment(self) -> str:
        """Generate agenda summary for injection into the LLM system prompt."""
        icons = {
            SectionStatus.PENDING: "[ ]",
            SectionStatus.ACTIVE: "[>]",
            SectionStatus.DRAFT: "[~]",
            SectionStatus.AGREED: "[x]",
        }
        lines = []
        for item in self.items:
            lines.append(f"{icons[item.status]} {item.label}")
        return "\n".join(lines)

    def is_complete(self) -> bool:
        return all(item.status == SectionStatus.AGREED for item in self.items)
