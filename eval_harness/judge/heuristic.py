"""Phase 1 heuristic judge: scores C1, C2, and C3 without an LLM."""
from __future__ import annotations

from pagecraft.registry import load_component_registry

from eval_harness.models import ConversationLog, JudgeVerdict


class HeuristicJudge:
    """Rule-based judge that scores C1 (completeness), C2 (data fidelity), C3 (agenda order)."""

    # Required top-level keys per component type (derived from MCP tool signatures).
    _REQUIRED_FIELDS: dict[str, list[str]] = {
        "hero": ["title", "description"],
        "situation": ["current_situation", "challenge", "solution"],
        "kpis": ["items"],
        "impact": ["items"],
        "implementation": ["heading", "body_text"],
        "resources": ["heading", "body_text"],
        "getting_started": ["steps"],
        "personas": ["personas"],
        "metadata": ["municipality", "sector", "twin_transition", "themes", "technical_solution"],
        "contact": ["name", "title", "organization"],
    }

    _EMPTY_MARKERS: frozenset = frozenset({"", "N/A", "n/a", "...", "…"})

    # Phase-1 weights (C4 absent → redistributed to C1/C2/C3).
    _W1, _W2, _W3 = 0.40, 0.35, 0.25

    def score(self, log: ConversationLog) -> JudgeVerdict:
        """Score the session and return a JudgeVerdict with C1, C2, C3 populated."""
        c1 = self._score_c1(log)
        c2 = self._score_c2(log)
        c3 = self._score_c3(log)
        overall = round(c1 * self._W1 + c2 * self._W2 + c3 * self._W3, 2)

        return JudgeVerdict(
            c1_completeness=c1,
            c2_data_fidelity=c2,
            c3_agenda_progression=c3,
            c4_graceful_recovery=None,
            overall_score=overall,
            judge_type="heuristic",
            judge_reasoning="",
        )

    # ------------------------------------------------------------------
    # Scoring functions
    # ------------------------------------------------------------------

    @staticmethod
    def _score_c1(log: ConversationLog) -> float:
        """C1 — Component Completeness: count agreed components on a 1–5 scale."""
        agreed = sum(1 for c in log.components.values() if c.status == "agreed")
        if agreed >= 10:
            return 5.0
        if agreed >= 8:
            return 4.0
        if agreed >= 6:
            return 3.0
        if agreed >= 3:
            return 2.0
        return 1.0

    def _score_c2(self, log: ConversationLog) -> float:
        """C2 — Data Fidelity: fraction of required fields that are non-empty."""
        total = 0
        empty = 0

        for comp_type, state in log.components.items():
            required = self._REQUIRED_FIELDS.get(comp_type)
            if not required:
                continue
            data = state.data_json or {}
            for field_name in required:
                total += 1
                value = data.get(field_name)
                if value is None:
                    empty += 1
                elif isinstance(value, str) and value in self._EMPTY_MARKERS:
                    empty += 1
                elif isinstance(value, list) and len(value) == 0:
                    empty += 1

        if total == 0:
            return 1.0

        empty_ratio = empty / total
        if empty_ratio == 0:
            return 5.0
        if empty_ratio <= 0.05:
            return 4.0
        if empty_ratio <= 0.20:
            return 3.0
        if empty_ratio <= 0.40:
            return 2.0
        return 1.0

    @staticmethod
    def _score_c3(log: ConversationLog) -> float:
        """C3 — Agenda Progression: count adjacent pairs rendered out of interview_order."""
        if len(log.render_order) <= 1:
            return 5.0

        registry = load_component_registry()
        order_map = {component.type: component.interview_order for component in registry}

        violations = sum(
            1
            for i in range(1, len(log.render_order))
            if order_map.get(log.render_order[i], 0) < order_map.get(log.render_order[i - 1], 0)
        )

        if violations == 0:
            return 5.0
        if violations == 1:
            return 4.0
        if violations <= 3:
            return 3.0
        if violations <= 5:
            return 2.0
        return 1.0
