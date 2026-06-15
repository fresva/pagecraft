"""Pytest configuration for the eval harness.

Session-scoped fixtures create the output directory, run-ID, and CSV writer.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from eval_harness.output import CSVWriter

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
def csv_writer(eval_run_id: str, eval_output_dir: Path):
    """Open a session-scoped CSVWriter and close it after all tests finish."""
    writer = CSVWriter(eval_output_dir / "eval_results.csv", eval_run_id)
    yield writer
    writer.close()
