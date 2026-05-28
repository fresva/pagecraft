import asyncio
import html
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from pagecraft.orchestrator.annotator import run_annotation_pass_safe
from pagecraft.registry import ComponentDef, interview_ordered
from pagecraft.services.edit_form import apply_edits, build_edit_form_html
from pagecraft.services.page_service import (
    get_component,
    get_page_components,
    save_component,
    update_component_status,
    update_page_status,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Active WebSocket connections keyed by page_id
_connections: dict[int, list[WebSocket]] = {}


async def send_chat_html(ws: WebSocket, role: str, text: str) -> None:
    """Send a chat bubble via OOB swap."""
    role_label = "PageCraft" if role == "assistant" else "Du"
    css_class = f"chat-{role}"
    safe_text = html.escape(text or "")
    chat_html = (
        f'<div id="chat-messages" hx-swap-oob="beforeend">'
        f'<div class="chat-bubble {css_class}">'
        f'<div class="chat-role">{role_label}</div>'
        f'<div class="chat-text">{safe_text}</div>'
        f'</div></div>'
    )
    await ws.send_json({"type": "chat", "html": chat_html})


async def send_component_html(
    ws: WebSocket, component_type: str, html_content: str, status: str = "draft",
    component_id: int | None = None,
) -> None:
    """Send a component update via OOB swap."""
    # Wrap in component wrapper with status bar
    status_label = status.capitalize()
    badge_class = f"badge-{status}"

    buttons = []
    if status == "draft":
        buttons.append(
            f'<button class="btn-agree" onclick="sendComponentAction({component_id}, \'agree\')">'
            f'Godkänn</button>'
        )
    elif status == "agreed":
        buttons.append(
            f'<button class="btn-revise" onclick="sendComponentAction({component_id}, \'revise\')">'
            f'Ändra</button>'
        )
    if component_id is not None:
        buttons.append(
            f'<button class="btn-edit" onclick="requestEdit({component_id})">Ändra fält</button>'
        )
    action_btn = "".join(buttons)

    html = (
        f'<div id="component-{component_type}" hx-swap-oob="true"'
        f' class="component-wrapper component-status-{status}">'
        f'<div class="component-status-bar">'
        f'<span class="status-badge {badge_class}">{status_label}</span>'
        f'{action_btn}'
        f'</div>'
        f'{html_content}'
        f'</div>'
    )
    await ws.send_json({"type": "component", "html": html})


async def send_interview_closed(ws: WebSocket) -> None:
    """Replace the chat input form with a closed-state notice via OOB swap."""
    closed_html = (
        '<form id="chat-form" hx-swap-oob="true" class="chat-input-form chat-closed">'
        '<span class="chat-closed-text">Intervjun är avslutad.</span>'
        '</form>'
    )
    await ws.send_json({"type": "control", "html": closed_html})


async def send_typing_indicator(ws: WebSocket, active: bool, text: str = "Boten tänker...") -> None:
    if active:
        html = (
            f'<div id="typing-indicator" hx-swap-oob="true" class="typing-indicator active">'
            f'<span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>'
            f'<span class="typing-text">{text}</span>'
            f'</div>'
        )
    else:
        html = '<div id="typing-indicator" hx-swap-oob="true" class="typing-indicator"></div>'
    await ws.send_json({"type": "status", "html": html})


async def send_agenda_html(ws: WebSocket, registry: list[ComponentDef], component_statuses: dict[str, str]) -> None:
    """Send updated agenda panel via OOB swap."""
    items_html = ""
    for comp in interview_ordered(registry):
        status = component_statuses.get(comp.type, "pending")
        if status == "agreed":
            icon = "&#9745;"
            css = "agenda-agreed"
        elif status == "draft":
            icon = "&#9744;"
            css = "agenda-active"
        else:
            icon = "&#9744;"
            css = "agenda-pending"
        items_html += (
            f'<li class="agenda-item {css}">'
            f'<span class="agenda-icon">{icon}</span> {comp.label}'
            f'</li>'
        )

    html = (
        f'<div id="agenda-panel" hx-swap-oob="true" class="agenda">'
        f'<h3>Agenda</h3>'
        f'<ul class="agenda-list">{items_html}</ul>'
        f'</div>'
    )
    await ws.send_json({"type": "agenda", "html": html})


@router.websocket("/ws/{page_id}")
async def websocket_endpoint(websocket: WebSocket, page_id: int):
    await websocket.accept()

    # Track connection
    if page_id not in _connections:
        _connections[page_id] = []
    _connections[page_id].append(websocket)

    db = websocket.app.state.db
    registry = websocket.app.state.component_registry
    demo_handler_fn = websocket.app.state.demo_handler
    llm_client = getattr(websocket.app.state, "llm_client", None)
    mcp_bridge = getattr(websocket.app.state, "mcp_bridge", None)
    prompt_loader = getattr(websocket.app.state, "prompt_loader", None)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                msg = {"type": "chat", "text": raw}

            msg_type = msg.get("type", "chat")

            if msg_type == "chat":
                text = msg.get("text", "").strip()
                if not text:
                    continue

                # Echo user message
                await send_chat_html(websocket, "user", text)

                # Show typing indicator
                await send_typing_indicator(websocket, True)

                # Use real engine if LLM is configured, otherwise demo mode
                if llm_client and mcp_bridge and prompt_loader:
                    from pagecraft.orchestrator.engine import handle_user_message
                    await handle_user_message(
                        websocket, page_id, text, db, registry,
                        llm_client, mcp_bridge, prompt_loader,
                    )
                else:
                    await demo_handler_fn(websocket, page_id, text, db, registry)

                # Clear typing indicator
                await send_typing_indicator(websocket, False)

            elif msg_type == "end_interview":
                # Move the page into the review queue, close the chat UI, and kick
                # off the annotation pass in the background so the interviewee
                # isn't kept waiting while the LLM annotates each component.
                await update_page_status(db, page_id, "awaiting_review")
                await send_chat_html(
                    websocket, "assistant",
                    "Tack! Intervjun är avslutad. Sidan lämnas nu vidare för "
                    "granskning av en forskare innan publicering.",
                )
                await send_interview_closed(websocket)
                asyncio.create_task(
                    run_annotation_pass_safe(db, page_id, registry, llm_client, prompt_loader)
                )

            elif msg_type == "edit_request":
                component_id = msg.get("component_id")
                component = await get_component(db, component_id) if component_id else None
                if component:
                    comp_def = next((c for c in registry if c.type == component.component_type), None)
                    label = comp_def.label if comp_def else component.component_type
                    try:
                        data = json.loads(component.data_json)
                    except (TypeError, json.JSONDecodeError):
                        data = {}
                    form_html = build_edit_form_html(component_id, label, data)
                    await websocket.send_json({"type": "edit_form", "html": form_html})

            elif msg_type == "component_edit":
                component_id = msg.get("component_id")
                fields = msg.get("fields") or {}
                component = await get_component(db, component_id) if component_id else None
                comp_def = (
                    next((c for c in registry if c.type == component.component_type), None)
                    if component else None
                )
                if component and comp_def and mcp_bridge:
                    try:
                        data = json.loads(component.data_json)
                    except (TypeError, json.JSONDecodeError):
                        data = {}
                    edited = apply_edits(data, fields)
                    result = await mcp_bridge.call_tool(comp_def.tool, edited)
                    saved = await save_component(
                        db, page_id=page_id, component_type=component.component_type,
                        display_order=comp_def.page_order, html=result["html"],
                        data_json=result["data_json"],
                    )
                    await send_component_html(
                        websocket, component.component_type, result["html"], "draft", saved.id,
                    )
                    # The bot picks up this edit automatically: the engine rebuilds
                    # its per-turn status block from the DB, which now reflects the
                    # new content. No separate edit note needed.
                    comps = await get_page_components(db, page_id)
                    statuses = {c.component_type: c.status for c in comps}
                    await send_agenda_html(websocket, registry, statuses)

            elif msg_type == "component_action":
                component_id = msg.get("component_id")
                action = msg.get("action")
                if component_id and action in ("agree", "revise"):
                    new_status = "agreed" if action == "agree" else "draft"
                    await update_component_status(db, component_id, new_status)

                    # Re-fetch and push the updated component
                    components = await get_page_components(db, page_id)
                    statuses = {}
                    for comp in components:
                        statuses[comp.component_type] = comp.status
                        if comp.id == component_id:
                            await send_component_html(
                                websocket, comp.component_type, comp.html,
                                comp.status, comp.id,
                            )

                    await send_agenda_html(websocket, registry, statuses)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for page {page_id}")
    finally:
        if page_id in _connections:
            _connections[page_id].remove(websocket)
            if not _connections[page_id]:
                del _connections[page_id]
