You are working in the PageCraft repository in PLAN MODE. Your task is to produce an implementation **plan** — not code. Do not edit, create, or delete any files. When the plan is ready, present it through the exit-plan flow for my approval and stop.

## Context

PageCraft is a FastAPI interview chatbot that co-builds a structured web page with the interviewee in real time. During the conversation the LLM calls MCP tools that render "components" (10 component types defined in `src/pagecraft/components.yaml`). Each rendered component has both rendered HTML and a `data_json` structure. The output of an interaction is a structured web page assembled from these components. PageCraft itself runs on Azure OpenAI; this plan is for Claude Code and must stay provider-agnostic.

There is an eval harness under `eval_harness/`. It drives simulated "personas" that chat with PageCraft and an LLM judge that scores each session. The relevant files include at least: `eval_harness/EVAL_HARNESS.md`, `eval_harness/conftest.py`, `eval_harness/test_runner.py`, `eval_harness/models.py`, `eval_harness/output.py`, `eval_harness/judge/llm.py`, and `eval_harness/prompts/judge.txt`.

## Problem to solve

The personas currently interact with PageCraft as if it were a plain chatbot. They do not take the page-being-built — the components and their content — into account. As a result the personas behave in ways that conflict with the real interaction and lack the context needed to understand and react to what PageCraft produces. The LLM judge has the same gap: it should evaluate against the actual page components produced, not merely the chat transcript.

The fix must be a **single coordinated design**: one shared mechanism for surfacing the built page components, used for **both** the persona context (during the simulated interaction) and the judge context (at scoring time). Design these together as one change, not as two independent workstreams.

## What the plan must do

1. **Investigate the current structure first.** Read the actual files in `eval_harness/` (start with the files listed above, and follow imports to any others such as the persona definitions, driver, and scenario files). Describe, grounded in the real code:
   - How personas are defined and how their context/inputs are fed to PageCraft during a simulated session.
   - How a simulated conversation runs end to end (the driver/session loop and how component state is captured).
   - How the LLM judge currently receives its inputs (what is and is not already included in its payload).

2. **Flag discrepancies.** The documentation and code may disagree. For example, verify whether the harness uses the judge, output writer, and persona/scenario mechanisms that `EVAL_HARNESS.md` describes, and check what the judge payload already contains versus what the docs claim. Call out every place where reality differs from this prompt's description or from `EVAL_HARNESS.md`, and base the plan on the real code.

3. **Evaluate component representation options.** Decide how the built components should be represented when surfaced to the persona and the judge. Evaluate at least these options and recommend one with rationale: (a) rendered HTML, (b) `data_json`, (c) a summarized human-readable digest derived from the components. Lean toward `data_json` or a readable digest, since the persona reacts to content rather than markup — but justify the final recommendation against the actual data available in the harness.

4. **Design the shared mechanism.** Specify how the page components built/added during the interaction are surfaced and injected:
   - Into the **persona context** during the simulated interaction, so the persona can see and react to the page as it is assembled.
   - Into the **judge context** at scoring time, so it evaluates against the real produced output.
   Describe how to **adjust** the existing structures and then **replace** the current behavior with the new one — including which functions, dataclasses, payload builders, and prompt files change, and what the new data flow looks like.

5. **Recommend phasing/sequencing.** Break the work into ordered phases (for example: investigation and confirmation, the shared representation/mechanism, persona-side integration, judge-side integration, prompt/text updates, verification). State dependencies between phases.

## Constraints

- PLAN MODE only. Investigate the existing code; write no code. Present the plan via the exit-plan flow and wait for approval.
- Ground every claim in the actual files in `eval_harness/`. Do not assume behavior that you have not confirmed by reading the code.
- Respect the project's language split: code, documentation, and the system prompt are in English; everything the end user (and the simulated persona) sees is in Swedish. If component content is surfaced to the persona, keep persona-facing content in Swedish; keep code and internal structures in English.
- Identify the specific files and symbols each phase touches, and call out any prompt-text changes (for example to `eval_harness/prompts/judge.txt`) separately from code changes.
- Note any risks: payload size when injecting component content, keeping the persona's behavior coherent, and any test or fixture that must be updated.

## Output

Present, through the exit-plan flow:
- A short summary of the current harness structure as confirmed by the code, with discrepancies flagged.
- The recommended component representation and why.
- The shared mechanism design for persona and judge, with the specific files/symbols affected and the new data flow.
- The phased, sequenced implementation steps with dependencies.
