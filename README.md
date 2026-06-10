# PageCraft

An interview bot that builds a structured web page **collaboratively and in real time** with the person being interviewed — instead of post-processing their answers into a page after the fact.

PageCraft was built as a research prototype for [UTTC (Urban Twin Transition Centre)](https://uttc.se) to capture sustainability case studies from Swedish municipalities. The interviewee is a practitioner at a Swedish *kommun* — typically someone who has led or worked closely on the case being described; the output is a public-facing case study page in the style of UTTC's existing [manually-produced case library](https://uttc.se/anvandningsfall/).

## What's interesting about it

Most "interview-to-content" pipelines treat the interviewee as a **subject** whose words get summarised by a human (or, increasingly, an LLM) afterwards. PageCraft moves them into the role of **co-author**:

- They see the page emerge as they talk.
- They catch misrepresentations the moment they appear, not in a correction cycle weeks later.
- The output has higher legitimacy because they signed off on each piece as it was written.

The point is not to mimic or replace a researcher's interpretive analysis. It is to give a municipality a way to **assess one of its own cases and write it up well enough to share**, so good practice can diffuse across public-sector domains. The practitioner runs the whole loop themselves: interview, review the assembled page, publish.

The bot uses [MCP (Model Context Protocol)](https://modelcontextprotocol.io) tool calls to write into a fixed component schema (hero, KPIs, situation/challenge/solution, implementation story, personas, etc.). It doesn't decide *what* a page can look like — the template is fixed in advance — but it decides *when* in the conversation each component is filled in, and lets the conversation flow naturally rather than walking through a rigid form.

## Status: research prototype

The end-to-end pipeline works — including with Azure OpenAI as the live conversation model — but PageCraft has not yet been used in a real interview with a municipal practitioner. Treat it as a working sketch of an architecture, not a piloted system.

### What works today

- The full chat ↔ LLM ↔ MCP-tools ↔ live-preview loop runs against Azure OpenAI.
- A scripted demo mode (see [Demo mode](#demo-mode)) drives the same pipeline without an LLM.
- All ten page components render, persist to SQLite, and stream incrementally to the browser via WebSocket.
- The practitioner approves or revises each component inline as it appears, then opens a whole-page preview and publishes it themselves. Publishing is reversible — they can return to the conversation and keep editing.

### Planned work and open questions

These are the rough edges I expect to work on in the coming months. They are not in priority order.

**Pushing published pages out.**
Publishing currently just flips a page to `published` and exposes it at a read-only `/case/{id}` URL inside the app. The next step for diffusion is to push that rendered page to an existing web server (over SFTP or similar) so finished cases live alongside UTTC's existing case library rather than only inside PageCraft.

**Docker deployment.**
A `docker-compose.yml` is in the repo but has not actually been exercised yet. Getting the system to run cleanly in containers — and potentially splitting the orchestrator, the MCP server, and the web UI into separate containers that talk to each other — is on the list.

**A real pilot.**
The end-to-end loop works, but PageCraft has not yet been run in a live interview with a municipal practitioner. That is the test that matters.

## How it works

```
┌────────────┐     WebSocket      ┌──────────────┐
│  Browser   │ ◄────────────────► │  FastAPI app │
│  (htmx)    │   (live page +     │              │
└────────────┘    chat updates)   │  ┌─────────┐ │     ┌──────────┐
                                  │  │Orchestr.│ │ ◄──►│  Azure   │
                                  │  └────┬────┘ │     │  OpenAI  │
                                  │       │ MCP  │     └──────────┘
                                  │  ┌────▼────┐ │
                                  │  │   MCP   │ │
                                  │  │  server │ │     ┌──────────┐
                                  │  │ (tools) │ │ ──► │  SQLite  │
                                  │  └─────────┘ │     └──────────┘
                                  └──────────────┘
```

- **FastAPI** serves the chat UI and the live page preview side-by-side.
- **htmx** (with its WebSocket extension) handles incremental DOM updates — when the bot calls a tool, the relevant HTML fragment is pushed to the browser without a page reload.
- The **orchestrator** sends each user message to Azure OpenAI along with the current agenda state and the available MCP tools, then dispatches tool calls back into the **MCP server**.
- The **MCP server** owns the component schema (`src/pagecraft/components.yaml`) and the Jinja2 templates for each component. Tool calls render HTML, write JSON to SQLite, and broadcast the fragment over the WebSocket.

The architecture and sequence diagrams in [`doc/`](doc/) show this in more detail.

## The 10 components

The fixed page schema (`src/pagecraft/components.yaml`) defines 10 components. They appear on the page in one order, but the bot covers them in the conversation in a different order — leading with the substantive *situation / challenge / solution* and saving the synthesis components (hero, metadata) for the end when there's enough material to write them.

| # | Component | Conversation order |
|---|---|---|
| 1 | Hero (intro) | 8 — synthesis |
| 2 | Metadata | 9 — synthesis |
| 3 | Situation / Challenge / Solution | 1 — start here |
| 4 | KPIs | 3 |
| 5 | Impact | 4 |
| 6 | Implementation story | 2 |
| 7 | Resources | 5 |
| 8 | Getting started | 6 |
| 9 | Personas | 7 |
| 10 | Contact | 10 — last |

The system prompt (in Swedish, see [`prompts/system.md`](prompts/system.md)) tells the bot to follow the natural thread of the conversation rather than march through this list.

## Running it

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install deps
uv sync

# 2. Copy env example and fill in Azure OpenAI credentials
cp .env.example .env
$EDITOR .env

# 3. Run
uv run uvicorn pagecraft.main:app --host 0.0.0.0 --port 8000

# Or with Docker
docker-compose up --build
```

Then open `http://localhost:8000/interview/1` (or any page id — pages are created on first visit).

### Demo mode

If `AZURE_OPENAI_API_KEY` is missing, the app falls back to a **scripted demo handler** ([`src/pagecraft/demo.py`](src/pagecraft/demo.py)) that simulates the bot using a fixed Swedish conversation about *Klimatkalkylen* — useful for testing the tool → DB → WebSocket pipeline without burning tokens.

## Project layout

```
src/pagecraft/
├── main.py             FastAPI app factory + lifespan
├── config.py           Pydantic settings (env vars)
├── database.py         SQLite schema + connection
├── components.yaml     Component registry (the page schema)
├── registry.py         Loads components.yaml
├── demo.py             No-LLM scripted fallback
├── orchestrator/       Conversation engine, LLM client, MCP bridge, agenda
├── mcp_server/         MCP server + per-component tool implementations
├── routes/             Interview, preview/publish, and WebSocket routes
├── services/           Page persistence + component edit form
├── templates/          Jinja2 templates (base, fragments, per-component)
└── static/             htmx, CSS, JS

prompts/
├── system.md           Main system prompt (Swedish)
└── opening.md          Scripted opening message

doc/
├── Master - ...md      The UTTC case template this project implements
├── sequence_diagram.*  How a turn flows through the system
└── tech_stack.*        Component diagram

tests/
├── unit/               Component registry, agenda, renderer, tools, prompt loader
├── integration/        WebSocket flow, MCP client/server, component lifecycle
└── e2e/                Full scripted interview
```

## Tests

```bash
uv run pytest                  # all
uv run pytest tests/unit       # fast
uv run pytest tests/e2e        # full interview simulation
```

## A note on language

There are two languages in play, and it helps to keep them apart.

- **Instruction language** — what the developer reads and edits. The code, documentation, and the system prompt (`prompts/system.md`) are in **English**, so a non-Swedish-speaking developer can tune the bot's behaviour. The prompt instructs the model, in English, to produce Swedish.
- **Content language** — what the end user sees. The bot's **output** (the page components), the UI chrome (templates, button labels, the agenda, status text in `routes/websocket.py` and `engine.py`), `prompts/opening.md`, the component labels in `components.yaml`, and the demo sequence in `demo.py` are all in **Swedish**, because the audience is Swedish municipalities and the published case feeds UTTC's Swedish case library.

So the system prompt being English does not make the bot reply in English. The Swedish-output directive lives in the prompt's `## Language` section. To experiment with another conversation or output language during development, that section is the single lever to change.

### If we ever support multiple languages in the UI

Letting the *user* pick a language is a much larger job than translating the prompt, and it is **not** built. It would mean a full i18n pass: extracting every hardcoded Swedish UI string (today they're scattered through Jinja templates and inline f-strings in `websocket.py`, `engine.py`, and `edit_form.py`) into a message catalog keyed by locale; threading the chosen locale through the HTTP and WebSocket render paths, which currently have no concept of it; storing the locale per page (a schema change) so the UI, the bot's output, and the published page stay consistent; and reconciling the catalog (static chrome) with the prompt directive (generated content), which is the part ordinary i18n doesn't cover. It also raises a product question: should a published case ever be non-Swedish, given the Swedish-diffusion goal? Defer until there's a concrete need.

## License

[MIT](LICENSE) — © 2026 Fredrik Svahn

## Acknowledgements

Built in collaboration with [UTTC (Urban Twin Transition Centre)](https://uttc.se), as part of research on AI-assisted knowledge capture from public-sector sustainability practitioners.
