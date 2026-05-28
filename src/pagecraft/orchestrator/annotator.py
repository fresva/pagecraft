"""Post-processing annotation pass.

After an interview ends, this runs once per filled component: it sends the
component's content plus the interview transcript to the LLM and asks for
annotations (things a researcher should review before publishing). In demo mode
(no LLM) it emits a small set of canned annotations so the review UI is testable.

Note: each component call currently includes the full transcript. That is fine
as a once-per-interview pass for a single case study; slicing the transcript per
component is a possible future optimisation.
"""
import json
import logging
import re

import aiosqlite

from pagecraft.orchestrator.llm_client import LLMClient
from pagecraft.orchestrator.prompt_loader import PromptLoader
from pagecraft.registry import ComponentDef
from pagecraft.services.annotation_service import (
    clear_annotations_for_page,
    create_annotation,
    flatten_paths,
)
from pagecraft.services.page_service import get_page_components

logger = logging.getLogger(__name__)

_VALID_SEVERITIES = {"verify", "assumption", "missing"}

# Demo-mode annotations, keyed by component type. Only applied to fields that
# actually exist in the component, so the review UI has realistic content to show
# without calling the LLM.
_CANNED: dict[str, list[dict]] = {
    "situation": [
        {"field": "challenge", "severity": "assumption",
         "message": "Antagande — bekräfta att detta var den centrala utmaningen."},
    ],
    "kpis": [
        {"field": "items.0.value", "severity": "verify",
         "message": "Dubbelkolla denna siffra mot källan."},
    ],
    "impact": [
        {"field": "items.0.value", "severity": "verify",
         "message": "Verifiera effektsiffran mot underlaget."},
    ],
    "contact": [
        {"field": "email", "severity": "missing",
         "message": "Kontrollera att e-postadressen stämmer före publicering."},
    ],
}


def _format_fields_with_paths(data: dict) -> str:
    return "\n".join(f"{path}: {value}" for path, value in flatten_paths(data).items())


def _parse_annotations(text: str | None, data: dict) -> list[dict]:
    """Extract a clean annotation list from the LLM's JSON response."""
    if not text:
        return []
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning("Could not parse annotation JSON: %r", text[:200])
        return []

    valid_fields = set(flatten_paths(data).keys())
    out = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        field = item.get("field", "")
        message = (item.get("message") or "").strip()
        severity = item.get("severity", "verify")
        if severity not in _VALID_SEVERITIES:
            severity = "verify"
        # Keep only annotations that target a real field and carry a message.
        if message and field in valid_fields:
            out.append({"field": field, "severity": severity, "message": message})
    return out


def _canned_annotations(component_type: str, data: dict) -> list[dict]:
    valid_fields = set(flatten_paths(data).keys())
    return [a for a in _CANNED.get(component_type, []) if a["field"] in valid_fields]


async def _build_transcript(db: aiosqlite.Connection, page_id: int) -> str:
    cursor = await db.execute(
        "SELECT role, content FROM conversation_messages "
        "WHERE page_id = ? AND role IN ('user', 'assistant') "
        "AND content IS NOT NULL AND content != '' ORDER BY id",
        (page_id,),
    )
    rows = await cursor.fetchall()
    lines = []
    for row in rows:
        speaker = "Intervjuare" if row["role"] == "assistant" else "Deltagare"
        lines.append(f"{speaker}: {row['content']}")
    return "\n".join(lines)


async def _annotate_via_llm(
    llm_client: LLMClient,
    guidance: str,
    label: str,
    component_type: str,
    data: dict,
    transcript: str,
) -> list[dict]:
    user = (
        f"Transkript av intervjun:\n{transcript}\n\n"
        f"Komponent: {label} ({component_type})\n"
        f"Innehåll (fält: värde):\n{_format_fields_with_paths(data)}\n\n"
        f"Granska komponenten mot transkriptet och returnera annoteringar som JSON-lista."
    )
    messages = [
        {"role": "system", "content": guidance},
        {"role": "user", "content": user},
    ]
    response = await llm_client.chat(messages)
    return _parse_annotations(response.content, data)


async def generate_annotations_for_page(
    db: aiosqlite.Connection,
    page_id: int,
    registry: list[ComponentDef],
    llm_client: LLMClient | None,
    prompt_loader: PromptLoader,
) -> int:
    """Generate and persist annotations for every filled component. Returns count."""
    components = await get_page_components(db, page_id)
    await clear_annotations_for_page(db, page_id)

    labels = {c.type: c.label for c in registry}
    guidance = prompt_loader.annotation_guidance()
    transcript = await _build_transcript(db, page_id) if llm_client else ""

    total = 0
    for comp in components:
        try:
            data = json.loads(comp.data_json)
        except (TypeError, json.JSONDecodeError):
            continue

        if llm_client:
            annotations = await _annotate_via_llm(
                llm_client, guidance, labels.get(comp.component_type, comp.component_type),
                comp.component_type, data, transcript,
            )
        else:
            annotations = _canned_annotations(comp.component_type, data)

        for ann in annotations:
            await create_annotation(db, comp.id, ann["field"], ann["message"], ann["severity"])
            total += 1

    logger.info("Generated %d annotations for page %s", total, page_id)
    return total


async def run_annotation_pass_safe(
    db: aiosqlite.Connection,
    page_id: int,
    registry: list[ComponentDef],
    llm_client: LLMClient | None,
    prompt_loader: PromptLoader,
) -> None:
    """Background-task wrapper: never lets an exception escape the event loop."""
    try:
        await generate_annotations_for_page(db, page_id, registry, llm_client, prompt_loader)
    except Exception:
        logger.exception("Annotation pass failed for page %s", page_id)
