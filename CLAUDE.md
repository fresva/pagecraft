# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the app
uv run uvicorn pagecraft.main:app --host 0.0.0.0 --port 8000

# Run all tests
uv run pytest

# Run only fast unit tests
uv run pytest tests/unit

# Run a single test file
uv run pytest tests/unit/test_agenda.py

# Lint
uv run ruff check src tests

# Format
uv run ruff format src tests
```

Tests run in demo mode by default — `conftest.py` clears Azure env vars, so no credentials are needed.

Copy `.env.example` to `.env` and fill in `AZURE_OPENAI_*` vars to use the real LLM. Without credentials the app falls back to the scripted demo handler in `demo.py`.

## Architecture

PageCraft is a FastAPI app that runs an interview bot which co-builds a structured web page with the interviewee in real time. The browser (htmx + WebSocket) sees the page assemble live as the LLM calls MCP tools.

```
Browser (htmx) ←──WebSocket──→ FastAPI ←──→ Azure OpenAI
                                  │
                              MCPBridge
                                  │
                            MCP Server (in-process)
                                  │
                              SQLite
```

### Key architectural facts

**MCP server is in-process.** `MCPBridge` wraps `FastMCP.call_tool()` directly — there is no subprocess or network hop. Tool modules register themselves on `mcp_server/server.py`'s module-level `mcp` instance via `@mcp.tool()` at import time. If `components.yaml` declares a tool that hasn't been imported, the app fails fast on startup (`_verify_tool_registration` in `main.py`).

**System prompt caching.** The static system prompt (`prompts/system.md`) is injected as the first message every turn so it stays byte-identical (prompt-cacheable on Azure). Per-turn dynamic state (agenda + current focus) is injected as a second `system` message at the tail. Page content is NOT re-sent every turn — it lives in the conversation as the bot's own tool calls and `system`-role participant-edit notes.

**WebSocket message protocol.** The client sends JSON `{type, ...}` messages; the server handles four types: `chat` (user text → LLM pipeline), `edit_request` (open inline edit form), `component_edit` (apply field edits → re-render component), `component_action` (agree/revise status toggle). Outbound OOB-swap HTML is sent as `{type, html}` JSON.

**Component lifecycle.** Components have status `draft` → `agreed` (toggled by the user). Pages have status `in_interview` → `published`. Publishing is reversible.

**LLM tool loop.** `orchestrator/engine.py:handle_user_message` runs a loop capped at `MAX_TOOL_ROUNDS = 5`. Each round: call LLM → if tool calls, execute each via `MCPBridge`, save rendered HTML+JSON to DB, push fragment to browser via WebSocket, then feed tool results back to LLM.

### Module map

| Path | Responsibility |
|------|---------------|
| `src/pagecraft/main.py` | App factory, lifespan (DB init, MCP bridge, LLM client) |
| `src/pagecraft/config.py` | Pydantic settings from env vars (`AZURE_OPENAI_*`, `PAGECRAFT_*`) |
| `src/pagecraft/database.py` | SQLite schema (pages, components, conversation_messages) + idempotent migrations |
| `src/pagecraft/registry.py` | Loads `components.yaml` into `ComponentDef` dataclasses |
| `src/pagecraft/components.yaml` | Single source of truth for all 10 components: type, label, MCP tool name, Jinja2 template, page order, interview order |
| `src/pagecraft/orchestrator/engine.py` | Core LLM ↔ MCP tool loop |
| `src/pagecraft/orchestrator/agenda.py` | Tracks interview progress (pending/active/draft/agreed per component) |
| `src/pagecraft/orchestrator/mcp_bridge.py` | Bridges orchestrator ↔ MCP; converts MCP schemas to OpenAI function-calling format |
| `src/pagecraft/orchestrator/llm_client.py` | Azure OpenAI async client |
| `src/pagecraft/orchestrator/prompt_loader.py` | Reads `prompts/system.md` and `prompts/opening.md` |
| `src/pagecraft/mcp_server/server.py` | `FastMCP` instance; tool modules are imported here to trigger registration |
| `src/pagecraft/mcp_server/tools/*.py` | One file per component; each exports a `@mcp.tool()` function that renders HTML and returns `{html, data_json, component_type}` as a JSON string |
| `src/pagecraft/mcp_server/renderer.py` | Jinja2 env for MCP tools (separate instance from the web app's templates) |
| `src/pagecraft/routes/interview.py` | `GET /interview/{page_id}` — chat UI; `GET /` — create page + redirect |
| `src/pagecraft/routes/preview.py` | `GET /preview/{uri_token}` — full preview; `POST .../publish`; `GET /case/{id}` — public read-only view |
| `src/pagecraft/routes/websocket.py` | `WS /ws/{page_id}` — message dispatch + OOB-swap helper functions |
| `src/pagecraft/services/page_service.py` | DB operations for pages and components |
| `src/pagecraft/services/edit_form.py` | Builds inline HTML edit form from component `data_json` |
| `src/pagecraft/demo.py` | Scripted demo handler (no LLM); simulates a Klimatkalkylen interview |

## Adding a new component

1. Add an entry to `src/pagecraft/components.yaml` with a unique `type`, `tool`, `template`, `page_order`, and `interview_order`.
2. Create `src/pagecraft/mcp_server/tools/<type>.py` with a `@mcp.tool()` function that takes field args and returns `json.dumps({html, data_json, component_type})`.
3. Create `src/pagecraft/templates/components/<type>.html`.
4. Import the new module in `src/pagecraft/mcp_server/server.py`.

The startup tool-registration check (`_verify_tool_registration`) will fail immediately if step 4 is missing.

## Language split

Code, documentation, and `prompts/system.md` are in **English** so non-Swedish developers can tune behaviour. The Swedish directive lives in the `## Language` section of `prompts/system.md` — that is the single lever to change the bot's output language.

Everything the end user sees is in **Swedish**: Jinja2 templates, button labels, `prompts/opening.md`, `demo.py`, component labels in `components.yaml`, and all inline strings in `routes/websocket.py` and `orchestrator/engine.py`.
