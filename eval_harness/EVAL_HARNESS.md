# PageCraft — Eval Harness

A fully automated evaluation framework that drives synthetic interview sessions
through PageCraft, scores the results, and produces CSV / JSONL reports for
human review.

![Architecture](eval_harness_architecture.png)

---

## Purpose

The harness answers one question:

> *Does the PageCraft interview bot reliably complete structured interviews,
> capture accurate data, follow the prescribed component order, and recover
> gracefully from non-standard user behaviour?*

It does this by running 7 synthetic personas end-to-end against the live app
(in demo mode, with no real LLM required), then scoring each session on up to
4 criteria using either a rule-based heuristic judge or a Claude LLM judge.

---

## Architecture overview

The harness is organised into five layers (see diagram above):

| Layer | What it does |
|---|---|
| **1 · Input** | Defines personas and their scripted inputs |
| **2 · Driver** | Operates a live PageCraft session via WebSocket |
| **3 · App** | PageCraft running in-process (FastAPI + demo handler + SQLite) |
| **4 · Judge** | Scores the session transcript on C1–C4 criteria |
| **5 · Output** | Writes CSV rows, samples runs for human review, exports JSONL |

---

## Layer 1 — Input

### Personas (`personas.py`)

Seven synthetic users, each testing a different behavioural pattern:

| ID | Behaviour | Post-component action |
|---|---|---|
| `happy_path` | Cooperative, full answers | Agree immediately |
| `terse` | Single-word / minimal answers | Agree immediately |
| `verbose` | Detailed, multi-sentence answers | Agree immediately |
| `auto_agree` | Rapid agreement on every component | Agree immediately |
| `revise_cycle` | Agrees then revises then re-agrees | Agree → Revise → Agree |
| `field_editor` | Uses inline field-edit forms | Edit fields → Agree |
| `mixed` | Mix of all behaviours | Varies per component |

Each persona carries:
- `inputs: list[str]` — ordered chat messages to send
- `max_turns: int` — safety cap on conversation length
- `post_component_behavior` — what to do each time a component is rendered
- `scenario_id` — which YAML scenario to use (currently always `default`)

### Scenario (`scenarios/default.yaml`)

The default scenario is based on **Klimatkalkylen** (a Swedish climate
calculation tool). It provides realistic domain content for the bot's
component data — municipality, KPIs, contact details, etc.

---

## Layer 2 — Driver (`driver.py`)

`ConversationDriver` connects to PageCraft via Starlette's `TestClient`, which
runs the full FastAPI app **in-process** — no server process is started. It
communicates through a real WebSocket connection.

### Session loop

```
while agreed_count < 10 and turns < max_turns and inputs remain:
    send chat message over WebSocket
    drain frames until typing indicator goes inactive
    for each new draft component:
        apply post_component_behavior (agree / revise / field_edit)
```

### `ConversationLog`

The driver produces a `ConversationLog` dataclass that captures:

- `turns` — every sent/received WebSocket frame (text messages and WS metadata)
- `components` — final state of each rendered component (`draft` or `agreed`,
  plus `data_json` hydrated from SQLite after the session closes)
- `render_order` — the sequence in which components were first rendered
- `termination_reason` — `completed` | `max_turns` | `input_exhausted` | `error`
- `turn_count` — total number of chat turns sent

---

## Layer 3 — App (`pagecraft/`)

The PageCraft application runs **entirely in-process** with two forced
overrides:

- `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` are cleared — the app
  falls back to the scripted **demo handler** (`demo.py`)
- `PAGECRAFT_DB_PATH` is redirected to a pytest `tmp_path` so tests are
  isolated and leave no shared state

The demo handler simulates the full LLM + MCP tool-call loop using a
pre-scripted sequence of tool calls keyed to the Klimatkalkylen scenario.
This means the harness runs fast and needs no credentials.

---

## Layer 4 — Judge

The judge is selected automatically based on the environment:

```
ANTHROPIC_API_KEY set?
  yes → LLMJudge   (Claude, C1–C4, Phase-2 weights)
  no  → HeuristicJudge   (rule-based, C1–C3, Phase-1 weights)
```

### Scoring criteria

All criteria use a **1–5 scale** (decimals allowed).

#### C1 — Component Completeness
How many of the 10 components reached `agreed` status?

| Score | Agreed components |
|---|---|
| 5 | 10 (all) |
| 4 | 8–9 |
| 3 | 6–7 |
| 2 | 3–5 |
| 1 | 0–2 |

#### C2 — Data Fidelity
What fraction of required component fields contain real, non-placeholder
content? Penalises `""`, `"N/A"`, `"…"`, empty lists, and `null`.

| Score | Populated fields |
|---|---|
| 5 | 100 % |
| 4 | >95 % |
| 3 | 80–95 % |
| 2 | 60–79 % |
| 1 | <60 % |

#### C3 — Agenda Progression
Did the bot follow the prescribed interview order
(`hero → situation → kpis → impact → implementation → resources →
getting_started → personas → metadata → contact`)?
Each out-of-order consecutive pair counts as one violation.

| Score | Violations |
|---|---|
| 5 | 0 |
| 4 | 1 |
| 3 | 2–3 |
| 2 | 4–5 |
| 1 | >5 |

#### C4 — Graceful Recovery *(LLM judge only)*
How well did the bot handle revisions, field edits, corrections, and
unexpected inputs?

| Score | Behaviour |
|---|---|
| 5 | All non-standard inputs handled cleanly |
| 4 | Minor confusion in one instance, self-corrected |
| 3 | Some awkward exchanges, interview still completed |
| 2 | Notable repeated misunderstandings |
| 1 | Bot got stuck; failed to recover |

### Weights

| Mode | Formula |
|---|---|
| Heuristic (Phase 1) | `C1×0.40 + C2×0.35 + C3×0.25` |
| LLM (Phase 2) | `C1×0.35 + C2×0.30 + C3×0.20 + C4×0.15` |

### HeuristicJudge

`judge/heuristic.py` — pure Python, no API calls. Derives all scores from
the `ConversationLog` dataclass. Used in CI and when no Anthropic key is
present. C4 is always `None`.

### LLMJudge

`judge/llm.py` — calls `claude-opus-4-8` with a static 2 100-character
`JUDGE_SYSTEM_PROMPT` that defines all four criteria and their rubrics.
The log is serialised to compact JSON (turns + component states) and sent
as the user message. The model responds with a single JSON object:

```json
{"c1": 4.5, "c2": 4.0, "c3": 5.0, "c4": 3.5, "reasoning": "..."}
```

The call uses the SDK's streaming interface so long transcripts don't hit
request timeouts.

---

## Layer 5 — Output

### `eval_results/eval_results.txt`

`TxtReportWriter` (`output.py`) writes one human-readable entry per persona per
run to a single plain-text report. The file opens with a banner carrying the
shared run ID, then appends one entry as each persona finishes.

Each entry has four parts:

| Part | Contents |
|---|---|
| **Summary** | Persona, eval ID, UTC timestamp, and a one-line session stat (turns, components agreed, completion %, termination reason). |
| **Rating** | The judge's `overall_score` out of 5 and the judge type. |
| **Justification** | The judge's free-text reasoning, word-wrapped. |
| **Conversation reference** | The single grounded citation (turn, direction, verbatim quote) the judge cited, or `[citation unavailable]`. |
| **Transcript** | The full raw persona ↔ bot exchange (see below). |

### Transcript rendering

The transcript replays `ConversationLog.turns` in order as a readable dialogue:

- **`PERSONA >`** blocks — the synthetic interviewee's chat messages.
- **`BOT     >`** blocks — the bot's chat replies, with HTML stripped to plain text.
- **`- component <type> -> <status>`** markers — inline events each time a
  component is rendered or its status changes (`draft` / `agreed`).

Every line is tagged with its turn number and word-wrapped to the report width.
WebSocket bookkeeping frames (typing indicators, agenda refreshes) are omitted
so the transcript shows only the meaningful exchange.

Example:

```
Transcript:
  [turn  1] PERSONA >
    Hej! Jag heter Anna och jobbar med Klimatkalkylen, ett verktyg som hjälper
    kommuner att beräkna sina utsläpp.
  [turn  1] BOT     >
    Vad roligt! Berätta mer.
  [turn  1]   - component hero -> draft
  [turn  1]   - component hero -> agreed
  [turn  2] PERSONA >
    Det stämmer.
```

---

## Running the harness

### Demo mode (no credentials needed)

```bash
uv run pytest eval_harness/ -v --tb=short
```

Runs all 7 personas with the heuristic judge. Takes ~40 s.

### LLM judge mode

```bash
ANTHROPIC_API_KEY=sk-ant-... uv run pytest eval_harness/ -v --tb=short
```

Same 7 personas, scored by Claude on C1–C4. Slower (one API call per
persona) and incurs API cost.

### Single persona

```bash
uv run pytest eval_harness/ -v -k happy_path
```

### Output location

Results are written to `eval_results/` in the project root (created
automatically on first run).

---

## Module map

```
eval_harness/
  conftest.py              pytest fixtures: CSV writer, session accumulator,
                           demo-mode env override, post-session sampler hook
  test_runner.py           parametrised test; judge selector (_make_judge)
  driver.py                ConversationDriver: WS session loop + DB hydration
  models.py                TurnRecord, ComponentState, ConversationLog,
                           JudgeVerdict, EvalRun
  personas.py              PERSONAS list + PersonaDef + PostComponentBehavior
  output.py                CSVWriter
  sampler.py               ReviewSampler: weighted sampling + JSONL export
  judge/
    heuristic.py           HeuristicJudge (C1/C2/C3, no API)
    llm.py                 LLMJudge (C1–C4, Claude claude-opus-4-8)
  scenarios/
    default.yaml           Klimatkalkylen scenario content
  generate_diagram.py      generates eval_harness_architecture.png
  eval_harness_architecture.png
```

---

## Adding a new persona

1. Add a `PersonaDef` entry to the `PERSONAS` list in `personas.py`.
2. Give it a unique `id`, a list of `inputs`, and a
   `post_component_behavior`.
3. Set `max_turns` high enough that all 10 components can be reached.
4. Run `uv run pytest eval_harness/ -v -k <your_id>` to verify it
   terminates with `completed`.
