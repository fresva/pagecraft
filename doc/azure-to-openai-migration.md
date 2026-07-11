# Migration: Azure OpenAI → OpenAI

This document records the change from **Azure OpenAI** to **standard OpenAI** so it
can be reversed later. To revert, undo each edit below (restore the "Before" text).

Date: 2026-06-22

## Summary

The app previously used `AsyncAzureOpenAI` with `AZURE_OPENAI_*` settings (endpoint,
api key, deployment, api version). It now uses `AsyncOpenAI` with `OPENAI_*` settings
(api key, model, optional base url). The demo-mode fallback now triggers when
`OPENAI_API_KEY` is empty (previously: when endpoint *and* key were empty).

## Files changed

### 1. `src/pagecraft/config.py`

Settings fields.

**Before:**
```python
    # Azure OpenAI — env vars: AZURE_OPENAI_*
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-12-01-preview"
```

**After:**
```python
    # OpenAI — env vars: OPENAI_*
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    # Optional override for the API base URL (e.g. a proxy or compatible endpoint).
    # Leave empty to use OpenAI's default.
    openai_base_url: str = ""
```

### 2. `src/pagecraft/orchestrator/llm_client.py`

Client construction and the `model` kwarg.

**Before:**
```python
"""Azure OpenAI client wrapper with function calling support."""
...
from openai import AsyncAzureOpenAI
...
    def __init__(self, settings: Settings):
        self._client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            timeout=60.0,
        )
        self._deployment = settings.azure_openai_deployment
...
        kwargs = {
            "model": self._deployment,
            "messages": messages,
        }
```

**After:**
```python
"""OpenAI client wrapper with function calling support."""
...
from openai import AsyncOpenAI
...
    def __init__(self, settings: Settings):
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            timeout=60.0,
        )
        self._model = settings.openai_model
...
        kwargs = {
            "model": self._model,
            "messages": messages,
        }
```

### 3. `src/pagecraft/main.py`

LLM-vs-demo gate in `lifespan`.

**Before:**
```python
    # Set up LLM client if Azure credentials are configured
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        from pagecraft.orchestrator.llm_client import LLMClient
        app.state.llm_client = LLMClient(settings)
        logger.info("LLM client configured — using real conversation engine")
    else:
        app.state.llm_client = None
        logger.info("No Azure credentials — using demo mode")
```

**After:**
```python
    # Set up LLM client if an OpenAI API key is configured
    if settings.openai_api_key:
        from pagecraft.orchestrator.llm_client import LLMClient
        app.state.llm_client = LLMClient(settings)
        logger.info("LLM client configured — using real conversation engine")
    else:
        app.state.llm_client = None
        logger.info("No OpenAI credentials — using demo mode")
```

### 4. `tests/conftest.py`

Autouse fixture that forces demo mode in tests.

**Before:**
```python
@pytest.fixture(autouse=True)
def _clear_azure_env(monkeypatch):
    """Ensure tests run in demo mode unless explicitly configured otherwise.

    Sets Azure vars to empty strings so that even if .env has real creds,
    the env var override takes precedence in pydantic-settings.
    """
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")
```

**After:**
```python
@pytest.fixture(autouse=True)
def _clear_openai_env(monkeypatch):
    """Ensure tests run in demo mode unless explicitly configured otherwise.

    Sets the OpenAI key to an empty string so that even if .env has real creds,
    the env var override takes precedence in pydantic-settings.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "")
```

### 5. `.env` and `.env.example`

**Before:**
```
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

**After:**
```
# OpenAI
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4o
# Optional: override the API base URL (proxy or OpenAI-compatible endpoint)
# OPENAI_BASE_URL=
```

### 6. Documentation (text-only references)

Azure mentions were replaced with OpenAI in:

- `CLAUDE.md` — demo-mode note, `.env.example` instructions, architecture diagram
  (`←──→ Azure OpenAI`), prompt-caching note ("prompt-cacheable on Azure"), and the
  module-map rows for `config.py` (`AZURE_OPENAI_*` → `OPENAI_*`) and
  `llm_client.py` (`Azure OpenAI async client` → `OpenAI async client`).
- `README.md` — status/limitations text, the ASCII architecture box, the setup
  step comment, and the demo-mode trigger (`AZURE_OPENAI_API_KEY` → `OPENAI_API_KEY`).
- `doc/tech_stack.mmd` — `AsyncAzureOpenAI` → `AsyncOpenAI`; node
  `Azure OpenAI<br/>gpt-5.2-chat` → `OpenAI<br/>gpt-4o`.
- `doc/sequence_diagram.mmd` — participant `Azure OpenAI` → `OpenAI`.

## How to revert

1. Restore the "Before" blocks in files 1–5 above.
2. Revert the documentation strings in file 6.
3. Put Azure credentials back in `.env` and run `uv run pytest` to confirm
   (tests pass in demo mode regardless, since the fixture clears the key).
