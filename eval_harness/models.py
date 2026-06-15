"""Shared data-transfer objects for the eval harness."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TurnRecord:
    """A single WebSocket frame exchanged during an interview session."""

    turn: int
    direction: str  # "sent" | "received"
    text: Optional[str] = None
    ws_type: Optional[str] = None
    html: Optional[str] = None


@dataclass
class ComponentState:
    """Snapshot of one rendered page component at end-of-session."""

    component_type: str
    component_id: int
    html: str
    status: str  # "draft" | "agreed"
    data_json: Optional[dict] = None


@dataclass
class ConversationLog:
    """Complete record of a single synthetic interview session."""

    persona_id: str
    turns: list[TurnRecord] = field(default_factory=list)
    components: dict[str, ComponentState] = field(default_factory=dict)
    render_order: list[str] = field(default_factory=list)
    turn_count: int = 0
    termination_reason: str = "error"  # completed|max_turns|error
    error_detail: str = ""


@dataclass
class JudgeVerdict:
    """Score produced by the LLM judge for one interview session."""

    overall_score: float
    judge_reasoning: str
    judge_type: str = "llm"
    # Grounding for the reasoning: the exact turn the judge cited. All three are
    # None when the judge gave no citation or it failed to resolve against the log.
    citation_turn: Optional[int] = None
    citation_direction: Optional[str] = None
    citation_quote: Optional[str] = None


@dataclass
class EvalRun:
    """Driver output and judge verdict for one complete eval run."""

    eval_id: str
    log: ConversationLog
    verdict: JudgeVerdict
