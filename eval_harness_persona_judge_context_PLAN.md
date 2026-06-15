# Plan: Surface the built page to personas and the judge (shared digest)

> Revised after a code review of `eval_harness/` and `src/pagecraft/`. Changes from the
> original ultraplan draft are marked **[REV]**. The five corrections folded in:
> (1) digest from the component's *inner* content, not the wrapped frame;
> (2) `field_editor` explicitly de-scoped — the driver has no field-edit path;
> (3) digest injected into the latest turn only, not persisted every turn;
> (4) judge keeps its structured `components` map *and* gains the digest;
> (5) HTML-strip consolidation must preserve `html.unescape` (and there are ~2 copies, not 3).

## Context

In `eval_harness/`, simulated personas chat with PageCraft and an LLM judge scores each
session. Today the **persona never sees the page it is helping build** — its only view of
PageCraft is the bot's chat replies (`driver.py:_drive_session` appends only `bot_text` to the
persona `history`). So personas behave like they're talking to a plain chatbot: a `reviser`
can't react to the actual draft text, etc. The fix is **one shared mechanism** that turns the
captured page components into a readable snapshot, injected into **both** the persona context
(during the session) and the judge context (at scoring time). This task also folds in
readability / DRY, PEP 8 / typing consistency, and structured file-handling cleanups in the
same modules.

**[REV] Correction to the original framing:** the judge is *not* "merely the chat transcript"
today — `LLMJudge._build_payload` already sends a `components` map
`{type: {status, data: data_json}}` (`llm.py:86-89`). The improvement for the judge is to *add*
a readable digest alongside that structured map and tell `judge.txt` to evaluate against the
produced page — **not** to replace the structured data.

---

## 1. Current structure (confirmed by reading the code)

**Persona definition** — `eval_harness/personas.py`
- `PersonaDef` dataclass: `id`, `description`, `system_prompt`, `max_turns`. System prompt
  loaded from `prompts/persona_<id>.txt` via `_load_prompt`. 7 personas (cooperative, laconic,
  verbose, agenda_jumper, reviser, adversarial, field_editor); prompts are Swedish (correct per
  the language split).

**Session loop** — `eval_harness/driver.py` → `ConversationDriver._drive_session`
- Maintains a Claude `history` seeded with one user message ("Begin: introduce yourself…").
- Each turn: `_generate_persona_response(history)` calls Anthropic Haiku with the persona's
  Swedish system prompt → sends text over the WebSocket → drains frames.
- Component frames are parsed by `_parse_component_frame` to read `(type, id, status)` for
  auto-agreeing. Live state is kept in `log.components` (`ComponentState` with `html` + `status`;
  `data_json` stays `None` mid-session) and updated again after agree via `_sync_component_states`.
- **The gap:** the only thing fed back to the persona is `bot_text` (chat reply text, via
  `_extract_bot_text`) appended as a `user` message. The assembled page is never shown to the
  persona.
- **[REV] The driver sends only `chat` and `component_action` (agree).** It never sends
  `component_edit` or `edit_request` — the field-editing protocol is not exercised at all.

**Judge input** — `eval_harness/judge/llm.py` → `LLMJudge._build_payload`
- Sends `system_prompt` (PageCraft `prompts/system.md`) **plus** a `components` map
  `{type: {status, data: data_json}}`, where `data_json` is hydrated from SQLite after the
  session (`driver._hydrate_components` / `_fetch_db_components`). The judge **already** receives
  component data. The improvement is to add a consistent readable digest and update `judge.txt`.
- `_resolve_citation` validates a cited turn against `log.turns`. **The digest must not enter
  `log.turns`**, so citation resolution stays correct and `_resolve_citation` is unchanged.

**Representation availability (decisive fact):** the WS `component` frame is
`{"type": "component", "html": html}` only (verified `routes/websocket.py:77`) — **no
`data_json`**. Mid-session the driver only has rendered HTML; `data_json` exists only
post-session via DB hydration. Registry Swedish labels + page order are available via
`pagecraft.registry.load_component_registry()` (`ComponentDef.label`, `.page_order`).

**[REV] Critical detail about the stored HTML:** `log.components[t].html` holds the *entire
wrapped frame* the server emits (`websocket.py:67-77`): a status-bar `<div>` containing the
status badge label (`status.capitalize()` → **"Draft"/"Agreed"**, English) and Swedish button
labels (**"Godkänn", "Ändra", "Ändra fält"**), followed by the real `{html_content}`. A naive
strip of `state.html` would put `"Draft Godkänn Ändra fält …"` into every digest block. The
digest builder **must extract the inner content** (everything after the status-bar `</div>`),
not strip the whole frame.

### Discrepancies flagged (base the plan on the code, not the docs)
- `EVAL_HARNESS.md` describes modules that **do not exist**: `judge/heuristic.py`, `sampler.py`,
  `scenarios/default.yaml`, `output.py:CSVWriter`, `generate_diagram.py`, the architecture
  `.png`, and `_make_judge`. Reality: LLM judge only, single `TxtReportWriter`, Python persona
  prompts. `models.py:EvalRun` is defined but unused.
- `EVAL_HARNESS.md` claims "no real LLM required / demo mode" for the whole harness, but
  `driver.py` **requires** an Anthropic key — personas are generated by Claude Haiku. Only
  PageCraft itself runs in demo mode (Azure vars cleared).
- The interview order quoted in `EVAL_HARNESS.md` (`hero → situation → kpis …`) contradicts
  `components.yaml` `interview_order` (situation=1, …, hero=8).
- `driver.run` sets `AZURE_OPENAI_*` env vars but only pops `PAGECRAFT_DB_PATH` in `finally`
  (leaked env). `conftest.py` already clears Azure vars via `monkeypatch` (autouse
  `_ensure_demo_mode`), so the `driver` assignments are redundant during tests.

---

## 2. Recommended component representation: **readable digest**

Build a **status-aware, page-ordered, Swedish-labelled text digest** from the captured
components. Source per context:
- **Persona (mid-session):** derive each component's body from its rendered **inner** HTML —
  **[REV]** strip the status-bar wrapper first, then tag-strip the remaining content. This is
  what the interviewee sees on screen, is available every turn, and is inherently Swedish (no
  English `data_json` keys or English "Draft/Agreed" labels leak to the persona).
- **Judge (post-session):** the same builder, but it prefers `data_json` (now hydrated) to emit
  clean `fält: värde` lines, falling back to inner-HTML text.

One function, two inputs. **[REV] Note the two contexts produce slightly different text** (HTML
vs `data_json`); this is intentional ("shared mechanism," not byte-identical output).

**Rejected:** (a) **raw/whole-frame HTML** — markup + button-label noise, token bloat;
(b) **pure `data_json`** — unavailable mid-session, so it cannot serve the persona, which is
the primary gap.

---

## 3. Shared mechanism design

### New module — `eval_harness/component_digest.py` (English code)
- `strip_html_to_text(html: str | None) -> str` — the single canonical tag-strip + whitespace
  collapse + **`html.unescape`**. **[REV] Replaces the duplicates** — the genuine duplicate is
  `driver.py:_extract_bot_text`'s inline regex (which currently does **not** unescape);
  `output.py:_strip_html` already does this and `output.py:_chat_text` wraps it. Consolidating
  must **preserve `html.unescape`** so transcripts don't change.
- **[REV]** `_component_body_html(html: str | None) -> str` — strip the leading
  `component-status-bar` `<div>…</div>` (badge + action buttons) and return only the inner
  `{html_content}`. Anchor on the status-bar div so button labels never reach the digest.
- `component_to_text(state: ComponentState, label: str) -> str` — one block:
  `### {label} [{status}]` then, if `state.data_json`, non-empty `fält: värde` lines (skip
  `""`/`None`/empty lists), else `strip_html_to_text(_component_body_html(state.html))`.
- `build_page_digest(components: dict[str, ComponentState]) -> str` — order via
  `load_component_registry()` (page order + Swedish `label`), concatenate non-empty blocks,
  return `""` when nothing is built yet. (Registry loaded once at module level.)

`models.py:ComponentState` already carries `html`, `status`, `data_json` — **no new dataclass
fields needed.** Delete the unused `EvalRun` while here.

### Persona side — `driver.py`
**[REV] Inject the digest into the latest turn only — do not persist it in `history`.**
In `_drive_session`, after frames + auto-agree are processed (so `log.components` is the live
page), build `digest = build_page_digest(log.components)`. Append the persona-facing `user`
message as `bot_text` **plus** the digest with a Swedish delimiter, but keep the **persisted**
history entry to `bot_text` alone (or strip the prior turn's digest before appending the next),
so the full page snapshot is not duplicated across every turn of a 25-turn run:

```
{bot_text}

[Sidan som byggs upp hittills:
{digest}]
```

`_extract_bot_text` is reduced to a join over chat frames using the shared `strip_html_to_text`.

### Judge side — `judge/llm.py`
**[REV] Add, do not replace.** In `_build_payload`, add
`session["page_digest"] = build_page_digest(log.components)` **alongside** the existing
structured `components` map and `render_order`. The structured `data_json` is more useful than
prose for field-level fidelity scoring; the digest is a readable complement. `_resolve_citation`,
`score`, streaming, and JSON parsing are unchanged.

### Prompt-text changes (Swedish vs English kept separate)
- `eval_harness/prompts/judge.txt` (English): tell the judge the payload now contains
  `session.page_digest` (the actual page produced) in addition to the structured `components`
  map, and to score data fidelity / completeness / order against it.
- `eval_harness/prompts/persona_*.txt` (Swedish, persona-facing): add one line so behaviour
  stays coherent now that the page is visible. Most relevant for `reviser` ("reagera på utkastet
  du ser"). Others get a light, generic mention.
- **[REV] `field_editor` is explicitly de-scoped for this change.** Its defining behavior —
  editing fields directly in the preview — maps to the `component_edit` / `edit_request`
  protocol, which the driver does **not** send. The digest lets it *reference* fields in chat,
  but the field-edit action remains unsupported. Wiring a `component_edit` path is a separate,
  out-of-scope task; note this in `EVAL_HARNESS.md` rather than implying the digest fixes it.

### Readability / PEP 8 / file-handling cleanups (same PR)
- **DRY:** collapse the HTML-stripping copies into `strip_html_to_text` (preserve `unescape`).
- **Typing consistency:** standardize on `X | None` (Py 3.11). `driver.py`/`models.py` use
  `typing.Optional`; `output.py` already uses `str | None` — align on the latter, drop
  `Optional` imports.
- **Structured file handling:** make `output.py:TxtReportWriter` a context manager
  (`__enter__`/`__exit__`) and have the `report_writer` fixture in `conftest.py` use `with`, so
  the handle is always released even if a test errors. Centralize `open(..., encoding="utf-8")`.
- **State hygiene:** in `driver.run`, pop `AZURE_OPENAI_*` in `finally` (or drop the redundant
  assignments, since `conftest.py` sets them via `monkeypatch`); avoid leaking process env.
- **Doc sync:** rewrite `EVAL_HARNESS.md` to match reality (LLM judge only, txt report, Python
  personas, Anthropic key required, corrected interview order), document the new digest flow,
  and **[REV]** note the `field_editor` / `component_edit` limitation.

---

## 4. Phased, sequenced implementation

**Phase 0 — Confirm (no code).** Re-confirm `log.components` is current each turn and frames
carry no `data_json` (done). Gate for everything else.

**Phase 1 — Shared representation.** Add `eval_harness/component_digest.py`
(`strip_html_to_text`, `_component_body_html`, `component_to_text`, `build_page_digest`); reuse
`pagecraft.registry.load_component_registry`. *No callers yet.* Depends on Phase 0.

**Phase 2 — Persona integration.** In `driver.py`, build the digest each turn and inject it into
the latest persona `user` message only (Swedish delimiter, not persisted); rewrite
`_extract_bot_text` to use the shared stripper. Depends on Phase 1.

**Phase 3 — Judge integration.** In `judge/llm.py:_build_payload`, add `session.page_digest`
alongside the existing structured `components` map. Depends on Phase 1.

**Phase 4 — Prompt text.** Update `prompts/judge.txt` (English) and `prompts/persona_*.txt`
(Swedish, excluding the `field_editor` action claim). Depends on Phases 2-3.

**Phase 5 — Cleanups + docs.** DRY/typing/file-handling/env items; `TxtReportWriter` context
manager + `conftest.py` `with`; remove unused `EvalRun`; rewrite `EVAL_HARNESS.md`. Land after
Phases 2-4 (same modules).

---

## 5. Risks
- **Token growth.** The digest is injected each persona turn and into the judge payload. **[REV]
  Mitigated** by digesting fields/inner-text (not whole-frame HTML), skipping empty fields, and
  **injecting into the latest turn only** rather than persisting it across the whole history.
- **Persona coherence.** Seeing the page could make personas drift (e.g. endlessly revise).
  Mitigation: clearly labelled Swedish "Sidan hittills" context, minimal prompt nudges, existing
  `max_turns` caps.
- **[REV] Baseline shift.** Editing 7 persona prompts + `judge.txt` + adding context means
  existing scores are not comparable across this change. Expected outcome, not a bug — capture
  fresh baselines after merge.
- **Tests/fixtures.** `conftest.py:report_writer` must move to a `with`-based lifecycle if
  `TxtReportWriter` becomes a context manager; `test_runner.py` assertions unaffected. Anthropic
  key still required.

## Verification
- `uv run ruff check eval_harness src` (line-length 100) — must stay clean.
- `uv run ruff format --check eval_harness`.
- `ANTHROPIC_API_KEY=… uv run pytest eval_harness/ -v -k "reviser" --tb=short` then the full
  7-persona run; confirm `termination_reason == completed` and `overall_score >= 1.0`.
- Open `eval_results/eval_results.txt`: transcripts intact (no behavior change from the strip
  consolidation); the `reviser` persona now references real component content; **[REV] the digest
  contains no "Draft/Godkänn/Ändra fält" wrapper noise**; the judge justification references the
  produced page.
