"""Integration tests for WebSocket message flow."""
import json
import os
import re

import pytest
from starlette.testclient import TestClient

from pagecraft.main import create_app

# The demo handler sends messages in a known order:
# chat(user echo), status(typing on), component, chat(bot reply), agenda, status(typing off)
DEMO_MSG_COUNT = 6
# Agree/revise sends: component, agenda
ACTION_MSG_COUNT = 2


@pytest.fixture
def app(tmp_path):
    os.environ["PAGECRAFT_DB_PATH"] = str(tmp_path / "test.db")
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def _create_page_and_get_id(client) -> int:
    response = client.get("/", follow_redirects=False)
    return int(response.headers["location"].split("/")[-1])


def _collect_messages(ws, count) -> list[dict]:
    """Collect exactly `count` messages from the WebSocket."""
    messages = []
    for _ in range(count):
        raw = ws.receive_text()
        messages.append(json.loads(raw))
    return messages


def test_websocket_chat_roundtrip(client):
    """User sends a chat message, receives echo + bot response."""
    page_id = _create_page_and_get_id(client)

    with client.websocket_connect(f"/ws/{page_id}") as ws:
        ws.send_text(json.dumps({"type": "chat", "text": "Hej, vi har ett projekt"}))
        messages = _collect_messages(ws, DEMO_MSG_COUNT)

    types = [m["type"] for m in messages]
    assert "chat" in types
    assert "component" in types
    assert "agenda" in types
    assert "status" in types


def test_websocket_component_has_oob_swap(client):
    """Component messages contain OOB swap attributes."""
    page_id = _create_page_and_get_id(client)

    with client.websocket_connect(f"/ws/{page_id}") as ws:
        ws.send_text(json.dumps({"type": "chat", "text": "Berätta om vårt projekt"}))
        messages = _collect_messages(ws, DEMO_MSG_COUNT)

    comp_msgs = [m for m in messages if m["type"] == "component"]
    assert len(comp_msgs) == 1
    html = comp_msgs[0]["html"]
    assert 'hx-swap-oob="true"' in html
    assert 'id="component-' in html
    assert "badge-draft" in html


def test_websocket_user_echo_has_correct_class(client):
    """User messages are echoed with chat-user class."""
    page_id = _create_page_and_get_id(client)

    with client.websocket_connect(f"/ws/{page_id}") as ws:
        ws.send_text(json.dumps({"type": "chat", "text": "Test message"}))
        messages = _collect_messages(ws, DEMO_MSG_COUNT)

    chat_msgs = [m for m in messages if m["type"] == "chat"]
    user_echo = chat_msgs[0]
    assert "chat-user" in user_echo["html"]
    assert "Test message" in user_echo["html"]


def test_websocket_typing_indicator(client):
    """Typing indicator is sent before and cleared after bot response."""
    page_id = _create_page_and_get_id(client)

    with client.websocket_connect(f"/ws/{page_id}") as ws:
        ws.send_text(json.dumps({"type": "chat", "text": "Hej"}))
        messages = _collect_messages(ws, DEMO_MSG_COUNT)

    status_msgs = [m for m in messages if m["type"] == "status"]
    assert len(status_msgs) == 2
    # First = typing on (has "active" class)
    assert 'class="typing-indicator active"' in status_msgs[0]["html"]
    # Second = typing off (no "active")
    assert 'class="typing-indicator"' in status_msgs[1]["html"]


def test_websocket_agree_action(client):
    """Agree action updates component status to agreed."""
    page_id = _create_page_and_get_id(client)

    with client.websocket_connect(f"/ws/{page_id}") as ws:
        # Trigger component render
        ws.send_text(json.dumps({"type": "chat", "text": "Hej"}))
        messages = _collect_messages(ws, DEMO_MSG_COUNT)

        comp_msg = next(m for m in messages if m["type"] == "component")
        match = re.search(r"sendComponentAction\((\d+)", comp_msg["html"])
        component_id = int(match.group(1))

        # Send agree
        ws.send_text(json.dumps({
            "type": "component_action",
            "component_id": component_id,
            "action": "agree",
        }))
        agree_msgs = _collect_messages(ws, ACTION_MSG_COUNT)

    agree_types = [m["type"] for m in agree_msgs]
    assert "component" in agree_types
    assert "agenda" in agree_types
    agreed_comp = next(m for m in agree_msgs if m["type"] == "component")
    assert "badge-agreed" in agreed_comp["html"]


def test_websocket_revise_after_agree(client):
    """Revise returns a component to draft status."""
    page_id = _create_page_and_get_id(client)

    with client.websocket_connect(f"/ws/{page_id}") as ws:
        # Trigger + agree
        ws.send_text(json.dumps({"type": "chat", "text": "Hej"}))
        messages = _collect_messages(ws, DEMO_MSG_COUNT)
        comp_msg = next(m for m in messages if m["type"] == "component")
        match = re.search(r"sendComponentAction\((\d+)", comp_msg["html"])
        component_id = int(match.group(1))

        ws.send_text(json.dumps({
            "type": "component_action", "component_id": component_id, "action": "agree",
        }))
        _collect_messages(ws, ACTION_MSG_COUNT)

        # Now revise
        ws.send_text(json.dumps({
            "type": "component_action", "component_id": component_id, "action": "revise",
        }))
        revise_msgs = _collect_messages(ws, ACTION_MSG_COUNT)

    revise_comp = next(m for m in revise_msgs if m["type"] == "component")
    assert "badge-draft" in revise_comp["html"]


def test_websocket_edit_component(client):
    """Edit flow: request the form, submit a field change, get an updated draft."""
    page_id = _create_page_and_get_id(client)

    with client.websocket_connect(f"/ws/{page_id}") as ws:
        # "Hej" triggers the situation component in demo mode
        ws.send_text(json.dumps({"type": "chat", "text": "Hej"}))
        messages = _collect_messages(ws, DEMO_MSG_COUNT)
        comp_msg = next(m for m in messages if m["type"] == "component")
        component_id = int(re.search(r"requestEdit\((\d+)\)", comp_msg["html"]).group(1))

        # Request the edit form
        ws.send_text(json.dumps({"type": "edit_request", "component_id": component_id}))
        form_msg = json.loads(ws.receive_text())
        assert form_msg["type"] == "edit_form"
        assert 'id="edit-form"' in form_msg["html"]
        assert 'name="current_situation"' in form_msg["html"]

        # Submit an edited value
        ws.send_text(json.dumps({
            "type": "component_edit",
            "component_id": component_id,
            "fields": {"current_situation": "Helt nytt nuläge"},
        }))
        edit_msgs = _collect_messages(ws, 2)  # component + agenda

    comp = next(m for m in edit_msgs if m["type"] == "component")
    assert "Helt nytt nuläge" in comp["html"]
    assert "badge-draft" in comp["html"]


def test_websocket_end_interview(client):
    """Ending the interview closes the chat and moves the page to review."""
    page_id = _create_page_and_get_id(client)

    with client.websocket_connect(f"/ws/{page_id}") as ws:
        ws.send_text(json.dumps({"type": "end_interview"}))
        # handler sends: chat (ack) + control (closed form)
        msgs = _collect_messages(ws, 2)

    types = [m["type"] for m in msgs]
    assert "chat" in types
    assert "control" in types
    closed = next(m for m in msgs if m["type"] == "control")
    assert "chat-closed" in closed["html"]


def test_websocket_multiple_components(client):
    """Sequential messages render different components."""
    page_id = _create_page_and_get_id(client)
    component_types = set()

    with client.websocket_connect(f"/ws/{page_id}") as ws:
        for text in ["Hej, projekt", "Vi har bra siffror"]:
            ws.send_text(json.dumps({"type": "chat", "text": text}))
            messages = _collect_messages(ws, DEMO_MSG_COUNT)
            for m in messages:
                if m["type"] == "component":
                    match = re.search(r'id="component-(\w+)"', m["html"])
                    if match:
                        component_types.add(match.group(1))

    assert len(component_types) == 2, f"Should render 2 different components, got: {component_types}"
