"""Core conversation engine: LLM <-> MCP tool loop.

Handles user messages by:
1. Building the prompt with agenda state
2. Calling the LLM with tool definitions
3. Processing tool calls (render components, save to DB, push via WS)
4. Continuing the conversation if the LLM wants another turn
"""
import json
import logging

import aiosqlite
from fastapi import WebSocket

from pagecraft.orchestrator.agenda import InterviewAgenda
from pagecraft.orchestrator.llm_client import LLMClient
from pagecraft.orchestrator.mcp_bridge import MCPBridge
from pagecraft.orchestrator.prompt_loader import PromptLoader
from pagecraft.registry import ComponentDef
from pagecraft.routes.websocket import send_agenda_html, send_chat_html, send_component_html
from pagecraft.services.page_service import get_page_components, save_component

logger = logging.getLogger(__name__)

# Maximum tool-call loop iterations to prevent infinite loops
MAX_TOOL_ROUNDS = 5


_STATUS_LABELS = {"draft": "utkast", "agreed": "godkänd"}


def _format_component_data(data: dict) -> str:
    """Render a component's data_json as compact readable lines for the LLM."""
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, str):
            if value.strip():
                lines.append(f"- {key}: {value}")
        elif isinstance(value, list):
            for i, item in enumerate(value, start=1):
                if isinstance(item, dict):
                    parts = "; ".join(
                        f"{k}: {v}" for k, v in item.items()
                        if isinstance(v, str) and v.strip()
                    )
                    if parts:
                        lines.append(f"- [{i}] {parts}")
                elif isinstance(item, str) and item.strip():
                    lines.append(f"- {key}[{i}]: {item}")
    return "\n".join(lines)


def _build_status_block(
    registry: list[ComponentDef],
    agenda: InterviewAgenda,
    components: list,
) -> str:
    """Build the per-turn status message: agenda + true current page content.

    Rebuilt from the DB each turn so it always reflects reality, including
    manual edits the interviewee made directly in the preview.
    """
    labels = {c.type: c.label for c in registry}
    current = agenda.current_section()
    parts = [
        "AKTUELL STATUS (sann, aktuell version av sidan — inklusive manuella "
        "redigeringar; lita på detta framför dina egna tidigare minnesbilder)",
        "",
        "Agenda:",
        agenda.to_prompt_fragment(),
        "",
        f"Nuvarande fokus: {current.label if current else 'Alla sektioner klara'}",
    ]

    content_blocks = []
    for comp in components:
        try:
            data = json.loads(comp.data_json)
        except (TypeError, json.JSONDecodeError):
            continue
        body = _format_component_data(data)
        if not body:
            continue
        label = labels.get(comp.component_type, comp.component_type)
        status_sv = _STATUS_LABELS.get(comp.status, comp.status)
        content_blocks.append(f"\n## {label} ({status_sv})\n{body}")

    if content_blocks:
        parts.append("\nSidans nuvarande innehåll:")
        parts.extend(content_blocks)
    else:
        parts.append("\nSidan är ännu tom — inga komponenter ifyllda.")

    return "\n".join(parts)


async def _load_conversation_history(db: aiosqlite.Connection, page_id: int) -> list[dict]:
    """Load conversation history from DB in OpenAI message format."""
    cursor = await db.execute(
        "SELECT role, content, tool_call_id, tool_name, tool_arguments "
        "FROM conversation_messages WHERE page_id = ? ORDER BY id",
        (page_id,),
    )
    rows = await cursor.fetchall()
    messages = []
    for row in rows:
        role = row["role"]
        if role == "tool":
            messages.append({
                "role": "tool",
                "content": row["content"],
                "tool_call_id": row["tool_call_id"],
            })
        elif role == "assistant" and row["tool_name"]:
            # Reconstruct assistant message with tool_calls
            # Check if we already have a pending assistant message
            if messages and messages[-1].get("role") == "assistant" and messages[-1].get("tool_calls"):
                messages[-1]["tool_calls"].append({
                    "id": row["tool_call_id"],
                    "type": "function",
                    "function": {
                        "name": row["tool_name"],
                        "arguments": row["tool_arguments"],
                    },
                })
            else:
                messages.append({
                    "role": "assistant",
                    "content": row["content"] or None,
                    "tool_calls": [{
                        "id": row["tool_call_id"],
                        "type": "function",
                        "function": {
                            "name": row["tool_name"],
                            "arguments": row["tool_arguments"],
                        },
                    }],
                })
        else:
            messages.append({"role": role, "content": row["content"]})
    return messages


async def _save_message(
    db: aiosqlite.Connection,
    page_id: int,
    role: str,
    content: str,
    tool_call_id: str | None = None,
    tool_name: str | None = None,
    tool_arguments: str | None = None,
) -> None:
    """Save a message to conversation history."""
    await db.execute(
        "INSERT INTO conversation_messages (page_id, role, content, tool_call_id, tool_name, tool_arguments) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (page_id, role, content, tool_call_id, tool_name, tool_arguments),
    )
    await db.commit()


async def handle_user_message(
    ws: WebSocket,
    page_id: int,
    user_text: str,
    db: aiosqlite.Connection,
    registry: list[ComponentDef],
    llm_client: LLMClient,
    mcp_bridge: MCPBridge,
    prompt_loader: PromptLoader,
) -> None:
    """Process a user message through the full LLM → MCP pipeline."""

    # Save user message
    await _save_message(db, page_id, "user", user_text)

    # Build agenda state
    existing_components = await get_page_components(db, page_id)
    component_statuses = {c.component_type: c.status for c in existing_components}
    agenda = InterviewAgenda(registry)
    agenda.update_from_db(component_statuses)

    # Static system prompt (byte-identical between turns → prompt-cacheable).
    # Annotation guidance is no longer appended here — annotations are generated
    # as a post-processing pass after the interview, not inline by the bot.
    system_content = prompt_loader.system_prompt()

    # Dynamic status: agenda + true current page content, rebuilt from the DB
    # each turn (reflects manual edits). Placed at the tail so the static prefix
    # stays cacheable.
    status_msg = {
        "role": "system",
        "content": _build_status_block(registry, agenda, existing_components),
    }

    history = await _load_conversation_history(db, page_id)
    system_msg = {"role": "system", "content": system_content}
    if history:
        messages = [system_msg] + history[:-1] + [status_msg] + history[-1:]
    else:
        messages = [system_msg, status_msg]

    # Get tool definitions
    mcp_tools = await mcp_bridge.list_tools()
    openai_tools = mcp_bridge.tools_to_openai_functions(mcp_tools)

    # LLM conversation loop (may involve multiple tool calls)
    for round_num in range(MAX_TOOL_ROUNDS):
        try:
            response = await llm_client.chat(messages, tools=openai_tools)
        except Exception as e:
            logger.exception(f"LLM call failed in round {round_num}")
            await send_chat_html(
                ws, "assistant",
                f"Ett fel uppstod vid anrop till AI-tjänsten: {e}",
            )
            return

        # Handle text response
        if response.content:
            await send_chat_html(ws, "assistant", response.content)
            await _save_message(db, page_id, "assistant", response.content)

        # Handle tool calls
        if not response.tool_calls:
            break  # No more tool calls, conversation turn complete

        # Save the assistant message with tool calls (to DB)
        for tc in response.tool_calls:
            await _save_message(
                db, page_id, "assistant",
                content=response.content or "",
                tool_call_id=tc.id,
                tool_name=tc.function.name,
                tool_arguments=tc.function.arguments,
            )

        # Append the assistant message (with tool_calls) to the in-memory
        # conversation BEFORE the tool results. OpenAI requires tool messages
        # to immediately follow the assistant message that called them.
        messages.append({
            "role": "assistant",
            "content": response.content or None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in response.tool_calls
            ],
        })

        # Execute each tool call
        for tc in response.tool_calls:
            tool_name = tc.function.name
            try:
                arguments = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in tool arguments: {tc.function.arguments}")
                tool_result = {"error": "Invalid arguments"}
                await _save_message(db, page_id, "tool", json.dumps(tool_result), tool_call_id=tc.id)
                messages.append({"role": "tool", "content": json.dumps(tool_result), "tool_call_id": tc.id})
                continue

            # Call the MCP tool
            try:
                result = await mcp_bridge.call_tool(tool_name, arguments)
            except Exception as e:
                logger.error(f"Tool {tool_name} failed: {e}")
                tool_result = {"error": str(e)}
                await _save_message(db, page_id, "tool", json.dumps(tool_result), tool_call_id=tc.id)
                messages.append({"role": "tool", "content": json.dumps(tool_result), "tool_call_id": tc.id})
                continue

            # Save component to DB
            comp_type = result["component_type"]
            comp_def = next((c for c in registry if c.type == comp_type), None)
            if comp_def:
                component = await save_component(
                    db,
                    page_id=page_id,
                    component_type=comp_type,
                    display_order=comp_def.page_order,
                    html=result["html"],
                    data_json=result["data_json"],
                )

                # Push to preview
                await send_component_html(ws, comp_type, result["html"], "draft", component.id)

            # Update agenda and push
            all_comps = await get_page_components(db, page_id)
            statuses = {c.component_type: c.status for c in all_comps}
            await send_agenda_html(ws, registry, statuses)

            # Feed tool result back to LLM
            tool_result_str = json.dumps({
                "component_type": comp_type,
                "status": "rendered",
                "annotations": result.get("annotations", []),
            })
            await _save_message(db, page_id, "tool", tool_result_str, tool_call_id=tc.id)
            messages.append({"role": "tool", "content": tool_result_str, "tool_call_id": tc.id})
