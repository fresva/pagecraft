"""LLM-based judge: scores interview transcripts on C1–C4 using Claude."""
from __future__ import annotations

import json

import anthropic

from eval_harness.models import ConversationLog, JudgeVerdict

# Phase-2 criterion weights: C1×0.35 + C2×0.30 + C3×0.20 + C4×0.15
_W1, _W2, _W3, _W4 = 0.35, 0.30, 0.20, 0.15

JUDGE_SYSTEM_PROMPT = """\
You are an expert evaluator of AI interview agents. You will receive a complete
transcript of a PageCraft interview session in JSON format. The session is a
structured interview where an AI bot guides a user through providing information
for 10 web page components in this prescribed order:

  hero → situation → kpis → impact → implementation → resources →
  getting_started → personas → metadata → contact

Score the session on four criteria, each on a 1–5 scale (decimals allowed):

**C1 – Component Completeness** (1–5)
How many of the 10 components were created AND agreed upon by the user?
  5: all 10 agreed
  4: 8–9 agreed
  3: 6–7 agreed
  2: 3–5 agreed
  1: 0–2 agreed

**C2 – Data Fidelity** (1–5)
How complete and non-placeholder is the captured data? Penalise missing fields,
generic fillers ("…", "N/A", empty strings), or copied boilerplate.
  5: all fields have specific, meaningful content
  4: >95 % of required fields have real content
  3: 80–95 % of required fields have real content
  2: 60–79 % of required fields have real content
  1: <60 % of required fields have real content

**C3 – Agenda Progression** (1–5)
Did the bot follow the prescribed component order? Each out-of-order transition
between consecutive components counts as one violation.
  5: no violations
  4: exactly 1 out-of-order transition
  3: 2–3 violations
  2: 4–5 violations
  1: >5 violations or completely random order

**C4 – Graceful Recovery** (1–5)
How well did the bot handle revisions, field edits, corrections, or vague inputs?
Look for: (a) smooth re-renders after edits, (b) agree/revise cycles without
confusion, (c) resilience to off-topic user messages.
  5: all revisions handled cleanly with no confusion
  4: minor confusion in one instance but self-corrected
  3: some awkward exchanges but interview completed
  2: notable repeated misunderstandings
  1: bot got stuck, failed to recover from non-standard input

Return ONLY a JSON object — no markdown fences, no commentary before or after:
{"c1": <float>, "c2": <float>, "c3": <float>, "c4": <float>, \
"reasoning": "<one paragraph>"}
"""


class LLMJudge:
    """Uses Claude to score a ConversationLog on C1–C4."""

    def __init__(self) -> None:
        """Initialise the Anthropic client from ANTHROPIC_API_KEY in the environment."""
        self._client = anthropic.Anthropic()

    def score(self, log: ConversationLog) -> JudgeVerdict:
        """Score a session log with a single streaming Claude call; return a JudgeVerdict."""
        payload = self._build_payload(log)

        with self._client.messages.stream(
            model="claude-opus-4-8",
            max_tokens=1024,
            system=JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": payload}],
        ) as stream:
            message = stream.get_final_message()

        scores = self._parse_scores(message.content[0].text.strip())
        c1, c2, c3, c4 = scores["c1"], scores["c2"], scores["c3"], scores["c4"]
        overall = round(c1 * _W1 + c2 * _W2 + c3 * _W3 + c4 * _W4, 2)

        return JudgeVerdict(
            c1_completeness=c1,
            c2_data_fidelity=c2,
            c3_agenda_progression=c3,
            c4_graceful_recovery=c4,
            overall_score=overall,
            judge_type="llm",
            judge_reasoning=scores.get("reasoning", ""),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_payload(log: ConversationLog) -> str:
        """Serialise a ConversationLog to a compact JSON string for the judge prompt."""
        turns = [
            {"direction": turn.direction, "turn": turn.turn, "text": turn.text}
            for turn in log.turns
            if turn.text  # drop HTML-only WS frames
        ]
        components = {
            comp_type: {"status": state.status, "data": state.data_json}
            for comp_type, state in log.components.items()
        }
        return json.dumps(
            {
                "persona_id": log.persona_id,
                "termination_reason": log.termination_reason,
                "turn_count": log.turn_count,
                "render_order": log.render_order,
                "turns": turns,
                "components": components,
            },
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _parse_scores(raw: str) -> dict:
        """Parse the model's JSON response, stripping markdown fences if present."""
        text = raw
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0]
        return json.loads(text.strip())
