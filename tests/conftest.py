import asyncio
import os
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio
from jinja2 import ChainableUndefined, Environment, FileSystemLoader

from pagecraft.database import SCHEMA
from pagecraft.registry import load_component_registry


@pytest.fixture(autouse=True)
def _clear_azure_env(monkeypatch):
    """Ensure tests run in demo mode unless explicitly configured otherwise.

    Sets Azure vars to empty strings so that even if .env has real creds,
    the env var override takes precedence in pydantic-settings.
    """
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")


@pytest.fixture(scope="session")
def component_registry():
    return load_component_registry()


@pytest.fixture(scope="session")
def jinja_env():
    templates_dir = Path(__file__).parent.parent / "src" / "pagecraft" / "templates"
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        undefined=ChainableUndefined,
    )
    return env


@pytest_asyncio.fixture
async def db():
    """In-memory SQLite database with schema applied."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.executescript(SCHEMA)
    await conn.commit()
    yield conn
    await conn.close()
