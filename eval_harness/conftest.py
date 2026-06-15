"""Pytest configuration for the eval harness.

Session-scoped fixtures create the output directory, run-ID, and report writer.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

from eval_harness.output import TxtReportWriter

# Load the harness's own .env (e.g. ANTHROPIC_API_KEY) before any test runs.
load_dotenv(Path(__file__).parent / ".env")

_OUTPUT_DIR = Path(__file__).parent.parent / "eval_results"


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
def report_writer(eval_run_id: str, eval_output_dir: Path):
    """Open a session-scoped TxtReportWriter and close it after all tests finish."""
    writer = TxtReportWriter(eval_output_dir / "eval_results.txt", eval_run_id)
    yield writer
    writer.close()
