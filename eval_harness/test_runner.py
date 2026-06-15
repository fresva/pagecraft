"""Eval harness entry point.

Run with:  uv run pytest eval_harness/ -v --tb=short

Each test drives one persona through a complete PageCraft session in demo mode,
scores the result with either the heuristic judge (default) or the LLM judge
(when ANTHROPIC_API_KEY is present in the environment), and appends a row to
eval_results.csv.  After all tests complete, conftest.pytest_sessionfinish runs
the sampler.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
import pytest

from eval_harness.driver import ConversationDriver
from eval_harness.judge.heuristic import HeuristicJudge
from eval_harness.models import EvalRun
from eval_harness.output import CSVWriter
from eval_harness.personas import PERSONAS, PersonaDef


def _make_judge() -> HeuristicJudge:
    """Return LLMJudge when ANTHROPIC_API_KEY is set, otherwise HeuristicJudge."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        from eval_harness.judge.llm import LLMJudge

        return LLMJudge()
    return HeuristicJudge()


@pytest.mark.parametrize("persona", PERSONAS, ids=lambda p: p.id)
def test_persona_interview(
    persona: PersonaDef,
    tmp_path: Path,
    session_runs: list[EvalRun],
    csv_writer: CSVWriter,
) -> None:
    """Drive a full interview session for one persona and record scores."""
    driver = ConversationDriver(persona, tmp_path / "eval.db")
    log = driver.run()

    judge = _make_judge()
    verdict = judge.score(log)
    demo_mode = verdict.judge_type == "heuristic"

    eval_id = str(uuid.uuid4())
    csv_writer.write_row(log, verdict, eval_id, demo_mode=demo_mode)
    session_runs.append(EvalRun(eval_id=eval_id, log=log, verdict=verdict))

    assert log.termination_reason != "error", (
        f"Persona '{persona.id}' session raised an exception: {log.error_detail}"
    )
    assert verdict.c1_completeness is not None, "C1 score was not produced"
    assert verdict.c1_completeness >= 3.0, (
        f"Persona '{persona.id}' C1={verdict.c1_completeness} below demo-mode minimum of 3.0"
    )
    assert verdict.overall_score >= 1.0, (
        f"Persona '{persona.id}' overall_score={verdict.overall_score} is below minimum"
    )
