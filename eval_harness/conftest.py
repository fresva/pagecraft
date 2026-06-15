"""Pytest configuration for the eval harness.

Session-scoped fixtures create the output directory, run-ID, and CSV writer.
A module-level dict bridges the session_runs fixture to the pytest_sessionfinish
hook, which runs the sampler after all session fixtures have been torn down
(i.e. after the CSV file is closed).
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from eval_harness.models import EvalRun
from eval_harness.output import CSVWriter
from eval_harness.sampler import ReviewSampler

_OUTPUT_DIR = Path(__file__).parent.parent / "eval_results"

# Shared between the session_runs fixture and pytest_sessionfinish.
_session_state: dict = {}


@pytest.fixture(autouse=True)
def _ensure_demo_mode(monkeypatch) -> None:
    """Clear Azure credentials so every test runs in demo mode."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")


@pytest.fixture(scope="session")
def eval_run_id() -> str:
    """Return a UUID shared across all tests in this pytest session."""
    return str(uuid.uuid4())


@pytest.fixture(scope="session")
def eval_output_dir() -> Path:
    """Return the output directory, creating it if necessary."""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return _OUTPUT_DIR


@pytest.fixture(scope="session")
def csv_writer(eval_run_id: str, eval_output_dir: Path):
    """Open a session-scoped CSVWriter and close it after all tests finish."""
    writer = CSVWriter(eval_output_dir / "eval_results.csv", eval_run_id)
    yield writer
    writer.close()


@pytest.fixture(scope="session")
def session_runs(eval_output_dir: Path) -> list[EvalRun]:
    """Accumulate EvalRun objects; the sampler runs after session teardown."""
    runs: list[EvalRun] = []
    _session_state["runs"] = runs
    _session_state["output_dir"] = eval_output_dir
    yield runs


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    """Run the sampler once all session fixtures (including csv_writer) are closed."""
    runs = _session_state.get("runs")
    output_dir = _session_state.get("output_dir")
    if not runs or output_dir is None:
        return

    sampler = ReviewSampler(
        csv_path=output_dir / "eval_results.csv",
        jsonl_path=output_dir / "human_review_sample.jsonl",
    )
    sampler.run(runs)
