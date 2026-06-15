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
    scenario_id: str
    turns: list[TurnRecord] = field(default_factory=list)
    components: dict[str, ComponentState] = field(default_factory=dict)
    render_order: list[str] = field(default_factory=list)
    turn_count: int = 0
    termination_reason: str = "error"  # completed|max_turns|input_exhausted|error
    error_detail: str = ""


@dataclass
class JudgeVerdict:
    """Scores produced by a judge for one interview session."""

    c1_completeness: Optional[float]
    c2_data_fidelity: Optional[float]
    c3_agenda_progression: Optional[float]
    c4_graceful_recovery: Optional[float]  # None for heuristic judge
    overall_score: float
    judge_type: str  # "heuristic" | "llm"
    judge_reasoning: str


@dataclass
class EvalRun:
    """Driver output and judge verdict for one complete eval run."""

    eval_id: str
    log: ConversationLog
    verdict: JudgeVerdict
