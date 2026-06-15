"""LLM-based judge: scores interview transcripts against the PageCraft system prompt."""
from __future__ import annotations

import json
from pathlib import Path

import anthropic

from eval_harness.models import ConversationLog, JudgeVerdict

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_SYSTEM_MD = Path(__file__).parent.parent.parent / "prompts" / "system.md"


class LLMJudge:
    """Uses Claude to holistically score a ConversationLog against the bot's system prompt."""

    def __init__(self) -> None:
        """Initialise the Anthropic client and load prompt files."""
        self._client = anthropic.Anthropic()
        self._judge_system = (_PROMPTS_DIR / "judge.txt").read_text(encoding="utf-8").strip()
        self._pagecraft_system = _SYSTEM_MD.read_text(encoding="utf-8").strip()

    def score(self, log: ConversationLog) -> JudgeVerdict:
        """Score a session log with a single streaming Claude call; return a JudgeVerdict."""
        payload = self._build_payload(log)

        with self._client.messages.stream(
            model="claude-opus-4-8",
            max_tokens=1024,
            system=self._judge_system,
            messages=[{"role": "user", "content": payload}],
        ) as stream:
            message = stream.get_final_message()

        result = self._parse_result(message.content[0].text.strip())
        turn, direction, quote = self._resolve_citation(log, result)
        return JudgeVerdict(
            overall_score=round(float(result["score"]), 2),
            judge_reasoning=result.get("reasoning", ""),
            citation_turn=turn,
            citation_direction=direction,
            citation_quote=quote,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_citation(
        log: ConversationLog, result: dict
    ) -> tuple[int | None, str | None, str | None]:
        """Validate the judge's cited turn against the real log.

        The judge only sees text-bearing turns (see ``_build_payload``), so a
        citation may not line up with ``log.turns``. Returns the verified
        (turn, direction, quote) if the cited turn exists and the quote is a
        verbatim substring of its text; otherwise (None, None, None).
        """
        raw_turn = result.get("turn_ref")
        direction = result.get("direction")
        quote = result.get("quote")
        if raw_turn is None or not quote:
            return (None, None, None)
        try:
            turn_no = int(raw_turn)
        except (TypeError, ValueError):
            return (None, None, None)
        for turn in log.turns:
            if turn.turn != turn_no or not turn.text:
                continue
            if direction and turn.direction != direction:
                continue
            if quote in turn.text:
                return (turn.turn, turn.direction, quote)
        return (None, None, None)

    def _build_payload(self, log: ConversationLog) -> str:
        """Serialise log + system prompt as JSON for the judge."""
        turns = [
            {"direction": turn.direction, "turn": turn.turn, "text": turn.text}
            for turn in log.turns
            if turn.text
        ]
        components = {
            comp_type: {"status": state.status, "data": state.data_json}
            for comp_type, state in log.components.items()
        }
        return json.dumps(
            {
                "system_prompt": self._pagecraft_system,
                "session": {
                    "persona_id": log.persona_id,
                    "termination_reason": log.termination_reason,
                    "turn_count": log.turn_count,
                    "render_order": log.render_order,
                    "turns": turns,
                    "components": components,
                },
            },
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _parse_result(raw: str) -> dict:
        """Parse the model's JSON response, stripping markdown fences if present."""
        text = raw
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0]
        return json.loads(text.strip())
