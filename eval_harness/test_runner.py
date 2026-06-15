"""Eval harness entry point.

Run with:  uv run pytest eval_harness/ -v --tb=short

Each test drives one persona through a complete PageCraft session, scores the result
with the LLM judge (requires ANTHROPIC_API_KEY), and appends an entry to eval_results.txt.
"""
from __future__ import annotations

import uuid
from pathlib import Path
import pytest

from eval_harness.driver import ConversationDriver
from eval_harness.judge.llm import LLMJudge
from eval_harness.output import TxtReportWriter
from eval_harness.personas import PERSONAS, PersonaDef


@pytest.mark.parametrize("persona", PERSONAS, ids=lambda p: p.id)
def test_persona_interview(
    persona: PersonaDef,
    tmp_path: Path,
    report_writer: TxtReportWriter,
) -> None:
    """Drive a full interview session for one persona and record scores."""
    driver = ConversationDriver(persona, tmp_path / "eval.db")
    log = driver.run()

    judge = LLMJudge()
    verdict = judge.score(log)

    eval_id = str(uuid.uuid4())
    report_writer.write_row(log, verdict, eval_id)

    assert log.termination_reason != "error", (
        f"Persona '{persona.id}' session raised an exception: {log.error_detail}"
    )
    assert verdict.overall_score >= 1.0, (
        f"Persona '{persona.id}' overall_score={verdict.overall_score} is below minimum"
    )
