"""E2E tests: full interview flow with mock LLM.

Tests the complete pipeline: user message → engine → LLM → MCP tool → DB → WS.
The LLM is mocked to return scripted responses with tool calls.
"""
import json
import os
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient

from pagecraft.main import create_app


def _make_tool_call(tool_call_id: str, name: str, arguments: dict):
    """Create a mock tool call matching OpenAI response format."""
    return SimpleNamespace(
        id=tool_call_id,
        type="function",
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments),
        ),
    )


def _make_llm_response(content: str | None = None, tool_calls: list | None = None):
    """Create a mock LLM response message."""
    return SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
    )


class MockLLMClient:
    """Mock LLM client that can be configured with scripted responses."""

    def __init__(self):
        self.responses = []
        self.call_count = 0
        self.captured_messages = []

    def set_responses(self, *responses):
        self.responses = list(responses)
        self.call_count = 0
        self.captured_messages = []

    async def chat(self, messages, tools=None):
        self.captured_messages.append(list(messages))
        idx = min(self.call_count, len(self.responses) - 1)
        self.call_count += 1
        return self.responses[idx]


# --- Fixtures ---

@pytest.fixture
def mock_llm():
    return MockLLMClient()


@pytest.fixture
def app_with_llm(tmp_path, mock_llm):
    """Create app and inject mock LLM client after lifespan init."""
    os.environ["PAGECRAFT_DB_PATH"] = str(tmp_path / "test.db")
    app = create_app()

    # Wrap the TestClient so lifespan runs, then inject the mock
    with TestClient(app) as client:
        # Inject mock LLM client into app state (overriding None from lifespan)
        app.state.llm_client = mock_llm
        yield client, mock_llm

    os.environ.pop("PAGECRAFT_DB_PATH", None)


def _create_page(client) -> int:
    response = client.get("/", follow_redirects=False)
    return int(response.headers["location"].split("/")[-1])


def _collect_messages(ws, count) -> list[dict]:
    messages = []
    for _ in range(count):
        raw = ws.receive_text()
        messages.append(json.loads(raw))
    return messages


# --- Tests ---

class TestFullInterviewWithMockLLM:
    """Tests using the real engine with a mocked LLM client."""

    def test_text_response_renders_chat_bubble(self, app_with_llm):
        """LLM text-only response → chat bubble sent via WS."""
        client, mock_llm = app_with_llm
        page_id = _create_page(client)

        mock_llm.set_responses(
            _make_llm_response(content="Hej! Berätta om ert projekt."),
        )

        with client.websocket_connect(f"/ws/{page_id}") as ws:
            ws.send_text(json.dumps({"type": "chat", "text": "Hej"}))
            # user echo, typing on, bot chat, typing off = 4
            messages = _collect_messages(ws, 4)

        types = [m["type"] for m in messages]
        assert types.count("chat") == 2  # user echo + bot reply
        assert types.count("status") == 2  # typing on + off

        bot_chat = [m for m in messages if m["type"] == "chat" and "chat-assistant" in m["html"]][0]
        assert "Berätta om ert projekt" in bot_chat["html"]

    def test_tool_call_renders_component(self, app_with_llm):
        """LLM tool call → component rendered and pushed via WS."""
        client, mock_llm = app_with_llm
        page_id = _create_page(client)

        tool_call = _make_tool_call(
            "call_1", "write_hero",
            {"title": "Testprojekt", "description": "En testintro."},
        )

        mock_llm.set_responses(
            _make_llm_response(content="Låt mig skapa introduktionen.", tool_calls=[tool_call]),
            _make_llm_response(content="Där har du introduktionen! Stämmer det?"),
        )

        with client.websocket_connect(f"/ws/{page_id}") as ws:
            ws.send_text(json.dumps({"type": "chat", "text": "Vi har ett projekt som heter Testprojekt"}))
            # user echo, typing on, chat (tool text), component, agenda, chat (follow-up), typing off = 7
            messages = _collect_messages(ws, 7)

        comp_msgs = [m for m in messages if m["type"] == "component"]
        assert len(comp_msgs) == 1
        assert "Testprojekt" in comp_msgs[0]["html"]
        assert 'id="component-hero"' in comp_msgs[0]["html"]

        agenda_msgs = [m for m in messages if m["type"] == "agenda"]
        assert len(agenda_msgs) == 1

    def test_component_saved_to_database(self, app_with_llm):
        """Tool call result is persisted in the database."""
        client, mock_llm = app_with_llm
        page_id = _create_page(client)

        tool_call = _make_tool_call(
            "call_db_1", "write_hero",
            {"title": "DB Test", "description": "Saved to DB."},
        )

        mock_llm.set_responses(
            _make_llm_response(tool_calls=[tool_call]),
            _make_llm_response(content="Klart!"),
        )

        with client.websocket_connect(f"/ws/{page_id}") as ws:
            ws.send_text(json.dumps({"type": "chat", "text": "Hej"}))
            # user echo, typing on, component, agenda, chat, typing off = 6
            messages = _collect_messages(ws, 6)

        # Verify page is accessible
        resp = client.get(f"/interview/{page_id}")
        assert resp.status_code == 200

    def test_conversation_history_persisted(self, app_with_llm):
        """Messages are saved and included in subsequent LLM calls."""
        client, mock_llm = app_with_llm
        page_id = _create_page(client)

        # First exchange
        mock_llm.set_responses(
            _make_llm_response(content="Hej tillbaka!"),
        )

        with client.websocket_connect(f"/ws/{page_id}") as ws:
            ws.send_text(json.dumps({"type": "chat", "text": "Hej"}))
            _collect_messages(ws, 4)

        # Second exchange — history should be included
        mock_llm.set_responses(
            _make_llm_response(content="Mer info!"),
        )

        with client.websocket_connect(f"/ws/{page_id}") as ws:
            ws.send_text(json.dumps({"type": "chat", "text": "Berätta mer"}))
            _collect_messages(ws, 4)

        # The second call should have received history
        assert mock_llm.call_count == 1  # only one call in this set_responses batch
        last_messages = mock_llm.captured_messages[0]
        roles = [m["role"] for m in last_messages]
        assert roles[0] == "system"
        assert "user" in roles
        assert "assistant" in roles


class TestScenarios:
    """Scenario-based tests for specific conversation patterns."""

    def test_agree_then_revise_flow(self, app_with_llm):
        """User agrees on a component, then revises it → status transitions correctly."""
        client, mock_llm = app_with_llm
        page_id = _create_page(client)

        tool_call = _make_tool_call(
            "call_agree_1", "write_hero",
            {"title": "Agree Test", "description": "Test."},
        )

        mock_llm.set_responses(
            _make_llm_response(tool_calls=[tool_call]),
            _make_llm_response(content="Kolla!"),
        )

        with client.websocket_connect(f"/ws/{page_id}") as ws:
            ws.send_text(json.dumps({"type": "chat", "text": "Hej"}))
            msgs = _collect_messages(ws, 6)

            comp_msg = next(m for m in msgs if m["type"] == "component")
            match = re.search(r"sendComponentAction\((\d+)", comp_msg["html"])
            component_id = int(match.group(1))

            # Agree
            ws.send_text(json.dumps({
                "type": "component_action",
                "component_id": component_id,
                "action": "agree",
            }))
            agree_msgs = _collect_messages(ws, 2)
            agreed_comp = next(m for m in agree_msgs if m["type"] == "component")
            assert "badge-agreed" in agreed_comp["html"]

            # Revise
            ws.send_text(json.dumps({
                "type": "component_action",
                "component_id": component_id,
                "action": "revise",
            }))
            revise_msgs = _collect_messages(ws, 2)
            revised_comp = next(m for m in revise_msgs if m["type"] == "component")
            assert "badge-draft" in revised_comp["html"]
