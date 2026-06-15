"""Conversation driver: connects to PageCraft via in-process TestClient and drives a
synthetic interview session for a given persona."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

import aiosqlite
import anthropic
from starlette.testclient import TestClient

from eval_harness.models import ComponentState, ConversationLog, TurnRecord
from eval_harness.personas import PersonaDef

logger = logging.getLogger(__name__)

_MAX_FRAMES_PER_TURN = 60
_MAX_ACTION_FRAMES = 5


class ConversationDriver:
    """Drives a full interview session for one persona and returns a ConversationLog."""

    _COMPONENT_TYPE_RE = re.compile(r'id="component-(\w+)"')
    _COMPONENT_ID_RE = re.compile(r"sendComponentAction\((\d+)")

    def __init__(self, persona: PersonaDef, db_path: Path) -> None:
        """Initialise the driver with a persona definition and an isolated DB path."""
        self._persona = persona
        self._db_path = db_path
        self._anthropic = anthropic.Anthropic()

    def run(self) -> ConversationLog:
        """Execute the full session and return a populated ConversationLog."""
        log = ConversationLog(persona_id=self._persona.id)
        page_id: Optional[int] = None

        os.environ["PAGECRAFT_DB_PATH"] = str(self._db_path)
        os.environ["AZURE_OPENAI_ENDPOINT"] = ""
        os.environ["AZURE_OPENAI_API_KEY"] = ""

        try:
            from pagecraft.main import create_app  # deferred to pick up env vars

            app = create_app()
            with TestClient(app) as client:
                page_id = self._create_page(client)
                with client.websocket_connect(f"/ws/{page_id}") as ws:
                    self._drive_session(ws, log)
        except Exception as exc:
            log.termination_reason = "error"
            log.error_detail = str(exc)
            logger.exception("Persona '%s' session failed", self._persona.id)
        finally:
            os.environ.pop("PAGECRAFT_DB_PATH", None)

        if page_id is not None and log.termination_reason != "error":
            self._hydrate_components(log, page_id)

        return log

    # ------------------------------------------------------------------
    # Session driving
    # ------------------------------------------------------------------

    def _drive_session(self, ws, log: ConversationLog) -> None:
        """Main loop: generate LLM persona responses and react to components until termination."""
        turn = 0
        history: list[dict] = [
            {"role": "user", "content": "Begin: introduce yourself and your project briefly."}
        ]

        while True:
            agreed_count = sum(1 for c in log.components.values() if c.status == "agreed")
            if agreed_count >= 10:
                log.termination_reason = "completed"
                break
            if turn >= self._persona.max_turns:
                log.termination_reason = "max_turns"
                break

            text = self._generate_persona_response(history)
            turn += 1

            ws.send_text(json.dumps({"type": "chat", "text": text}))
            log.turns.append(TurnRecord(turn=turn, direction="sent", text=text))

            frames = self._drain_until_typing_done(ws, log, turn)

            new_drafts: list[tuple[str, int]] = []
            for frame in frames:
                if frame.get("type") == "component":
                    parsed = self._parse_component_frame(frame["html"])
                    if parsed:
                        comp_type, comp_id, status = parsed
                        if comp_type not in log.render_order:
                            log.render_order.append(comp_type)
                        log.components[comp_type] = ComponentState(
                            component_type=comp_type,
                            component_id=comp_id,
                            html=frame["html"],
                            status=status,
                        )
                        if status == "draft":
                            new_drafts.append((comp_type, comp_id))

            for comp_type, comp_id in new_drafts:
                self._send_action(ws, comp_id, "agree")
                action_frames = self._drain_action_frames(ws, log, turn)
                self._sync_component_states(action_frames, log)

            bot_text = self._extract_bot_text(frames)
            history.append({"role": "assistant", "content": text})
            if bot_text:
                history.append({"role": "user", "content": bot_text})

        log.turn_count = turn

    def _generate_persona_response(self, history: list[dict]) -> str:
        """Call Anthropic Haiku to generate the next persona response."""
        response = self._anthropic.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=self._persona.system_prompt,
            messages=history,
        )
        return response.content[0].text.strip()

    @staticmethod
    def _extract_bot_text(frames: list[dict]) -> str:
        """Extract plain text from bot chat frames by stripping HTML tags."""
        parts = []
        for frame in frames:
            if frame.get("type") == "chat":
                raw = re.sub(r"<[^>]+>", " ", frame.get("html", ""))
                text = re.sub(r"\s+", " ", raw).strip()
                if text:
                    parts.append(text)
        return " ".join(parts)

    def _send_action(self, ws, comp_id: int, action: str) -> None:
        """Send a component_action WebSocket message."""
        ws.send_text(
            json.dumps({"type": "component_action", "component_id": comp_id, "action": action})
        )

    # ------------------------------------------------------------------
    # Frame draining helpers
    # ------------------------------------------------------------------

    def _drain_until_typing_done(
        self, ws, log: ConversationLog, turn: int
    ) -> list[dict]:
        """Read frames until the inactive typing-indicator status frame arrives."""
        frames: list[dict] = []
        for _ in range(_MAX_FRAMES_PER_TURN):
            try:
                msg = json.loads(ws.receive_text())
                frames.append(msg)
                log.turns.append(
                    TurnRecord(
                        turn=turn,
                        direction="received",
                        ws_type=msg.get("type"),
                        html=msg.get("html"),
                    )
                )
                if self._is_typing_done(msg):
                    break
            except Exception:
                break
        return frames

    def _drain_action_frames(
        self, ws, log: ConversationLog, turn: int
    ) -> list[dict]:
        """Read frames from a component_action or component_edit response.

        The server always sends a component frame then an agenda frame; stops
        after the agenda frame or after the safety cap.
        """
        frames: list[dict] = []
        for _ in range(_MAX_ACTION_FRAMES):
            try:
                msg = json.loads(ws.receive_text())
                frames.append(msg)
                log.turns.append(
                    TurnRecord(
                        turn=turn,
                        direction="received",
                        ws_type=msg.get("type"),
                        html=msg.get("html"),
                    )
                )
                if msg.get("type") == "agenda":
                    break
            except Exception:
                break
        return frames

    @staticmethod
    def _sync_component_states(frames: list[dict], log: ConversationLog) -> None:
        """Update log.components status and html from a batch of action-response frames."""
        for frame in frames:
            if frame.get("type") != "component":
                continue
            parsed = ConversationDriver._parse_component_frame(frame["html"])
            if parsed and parsed[0] in log.components:
                comp_type, comp_id, status = parsed
                log.components[comp_type].html = frame["html"]
                log.components[comp_type].status = status
                log.components[comp_type].component_id = comp_id

    # ------------------------------------------------------------------
    # DB hydration
    # ------------------------------------------------------------------

    def _hydrate_components(self, log: ConversationLog, page_id: int) -> None:
        """Populate data_json on every ComponentState by reading the SQLite DB directly."""
        loop = asyncio.new_event_loop()
        try:
            rows = loop.run_until_complete(self._fetch_db_components(page_id))
        finally:
            loop.close()

        for row in rows:
            comp_type = row["component_type"]
            parsed_json: Optional[dict] = None
            try:
                parsed_json = json.loads(row["data_json"])
            except (json.JSONDecodeError, TypeError):
                pass

            if comp_type in log.components:
                log.components[comp_type].status = row["status"]
                log.components[comp_type].data_json = parsed_json
            else:
                log.components[comp_type] = ComponentState(
                    component_type=comp_type,
                    component_id=0,
                    html="",
                    status=row["status"],
                    data_json=parsed_json,
                )

    async def _fetch_db_components(self, page_id: int) -> list:
        """Return all component rows for a page from the SQLite database."""
        async with aiosqlite.connect(str(self._db_path)) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT component_type, data_json, status FROM components WHERE page_id = ?",
                (page_id,),
            )
            return list(await cursor.fetchall())

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    @staticmethod
    def _create_page(client: TestClient) -> int:
        """Create a new page via GET / and return the redirected page ID."""
        response = client.get("/", follow_redirects=False)
        return int(response.headers["location"].split("/")[-1])

    # ------------------------------------------------------------------
    # Pure HTML parsers
    # ------------------------------------------------------------------

    @classmethod
    def _parse_component_frame(cls, html: str) -> Optional[tuple[str, int, str]]:
        """Extract (component_type, component_id, status) from a component HTML frame."""
        type_match = cls._COMPONENT_TYPE_RE.search(html)
        id_match = cls._COMPONENT_ID_RE.search(html)
        if not type_match or not id_match:
            return None
        comp_type = type_match.group(1)
        comp_id = int(id_match.group(1))
        status = "agreed" if "badge-agreed" in html else "draft"
        return comp_type, comp_id, status

    @staticmethod
    def _is_typing_done(msg: dict) -> bool:
        """Return True when the message is an inactive typing-indicator status frame."""
        if msg.get("type") != "status":
            return False
        html = msg.get("html", "")
        return "typing-indicator" in html and "active" not in html
