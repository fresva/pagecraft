"""Plain-text report writer for eval harness runs."""
from __future__ import annotations

import html as html_lib
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from eval_harness.models import ConversationLog, JudgeVerdict, TurnRecord

_COMPONENT_TYPE_RE = re.compile(r'id="component-(\w+)"')
_CHAT_TEXT_RE = re.compile(r'<div class="chat-text">(.*?)</div>', re.DOTALL)
_WRAP_WIDTH = 88


class TxtReportWriter:
    """Writes one human-readable entry per eval run to a .txt report file."""

    def __init__(self, path: Path, run_id: str) -> None:
        """Open *path* for writing and emit the report header."""
        self._run_id = run_id
        self._file = open(path, "w", encoding="utf-8")
        self._file.write(self._header())
        self._file.flush()

    def write_row(
        self,
        log: ConversationLog,
        verdict: JudgeVerdict,
        eval_id: str,
    ) -> None:
        """Append one result entry and flush immediately."""
        self._file.write(self._build_entry(log, verdict, eval_id))
        self._file.flush()

    def close(self) -> None:
        """Flush and close the underlying file handle."""
        if not self._file.closed:
            self._file.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _header(self) -> str:
        """Build the report banner written once at the top of the file."""
        bar = "=" * _WRAP_WIDTH
        return f"{bar}\nPageCraft Eval Report\nRun ID: {self._run_id}\n{bar}\n\n"

    def _build_entry(
        self,
        log: ConversationLog,
        verdict: JudgeVerdict,
        eval_id: str,
    ) -> str:
        """Assemble one report entry: summary, verdict, and the full transcript."""
        agreed_count = sum(1 for c in log.components.values() if c.status == "agreed")
        lines: list[str] = []
        rule = "-" * _WRAP_WIDTH
        lines.append(rule)
        lines.append(f"Persona:     {log.persona_id}")
        lines.append(f"Eval ID:     {eval_id}")
        lines.append(f"Timestamp:   {datetime.now(timezone.utc).isoformat()}")
        lines.append(
            f"Session:     {log.turn_count} turns | "
            f"{agreed_count}/{len(log.components)} components agreed | "
            f"completion {agreed_count / 10:.0%} | "
            f"termination {log.termination_reason}"
        )
        if log.error_detail:
            lines.append(f"Error:       {log.error_detail}")
        lines.append(rule)
        lines.append(f"Rating: {verdict.overall_score} / 5  (judge: {verdict.judge_type})")
        lines.append("")
        lines.append("Justification:")
        lines.extend(self._wrap(verdict.judge_reasoning or "(none provided)", indent="  "))
        lines.append("")
        lines.append("Conversation reference:")
        if verdict.citation_turn is not None and verdict.citation_quote:
            lines.append(f"  turn {verdict.citation_turn}, {verdict.citation_direction}:")
            lines.append(f'    "{verdict.citation_quote}"')
        else:
            lines.append("  [citation unavailable]")
        lines.append("")
        lines.append("Transcript:")
        lines.extend(self._build_transcript(log.turns))
        lines.append("")
        lines.append("")
        return "\n".join(lines)

    def _build_transcript(self, turns: list[TurnRecord]) -> list[str]:
        """Render the raw persona ↔ bot exchange as a readable, turn-numbered dialogue.

        Persona messages and bot replies are shown as labelled speech blocks;
        component renders/updates appear as inline event markers. WebSocket
        bookkeeping frames (typing indicators, agenda refreshes) are omitted.
        """
        if not turns:
            return ["  [no turns recorded]"]

        lines: list[str] = []
        for turn in turns:
            if turn.direction == "sent" and turn.text:
                lines.append(f"  [turn {turn.turn:>2}] PERSONA >")
                lines.extend(self._wrap(turn.text, indent="    "))
            elif turn.direction == "received":
                if turn.ws_type == "chat":
                    # The server echoes the participant's own message back as a
                    # 'chat-user' bubble; skip it so the persona isn't duplicated.
                    # Only 'chat-assistant' bubbles are genuine bot replies.
                    if turn.html and "chat-user" in turn.html:
                        continue
                    text = self._chat_text(turn.html)
                    if text:
                        lines.append(f"  [turn {turn.turn:>2}] BOT     >")
                        lines.extend(self._wrap(text, indent="    "))
                elif turn.ws_type == "component":
                    event = self._component_event(turn.html)
                    if event:
                        lines.append(f"  [turn {turn.turn:>2}]   - {event}")
        return lines or ["  [no dialogue recorded]"]

    @staticmethod
    def _component_event(html: str | None) -> str | None:
        """Summarise a component frame as e.g. 'component hero -> agreed'."""
        if not html:
            return None
        match = _COMPONENT_TYPE_RE.search(html)
        if not match:
            return None
        status = "agreed" if "badge-agreed" in html else "draft"
        return f"component {match.group(1)} -> {status}"

    @classmethod
    def _chat_text(cls, html: str | None) -> str:
        """Extract the message body from a chat bubble, dropping the role label.

        Falls back to stripping all tags if the expected ``chat-text`` div is
        absent. HTML entities (the participant's text is escaped server-side)
        are decoded so the transcript reads naturally.
        """
        if not html:
            return ""
        match = _CHAT_TEXT_RE.search(html)
        body = match.group(1) if match else html
        return cls._strip_html(body)

    @staticmethod
    def _strip_html(html: str | None) -> str:
        """Collapse an HTML fragment to plain, single-spaced, entity-decoded text."""
        if not html:
            return ""
        raw = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", html_lib.unescape(raw)).strip()

    @staticmethod
    def _wrap(text: str, indent: str) -> list[str]:
        """Word-wrap *text* to the report width with a hanging *indent*."""
        wrapped = textwrap.fill(
            text,
            width=_WRAP_WIDTH,
            initial_indent=indent,
            subsequent_indent=indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
        return wrapped.split("\n") if wrapped else [indent.rstrip()]
