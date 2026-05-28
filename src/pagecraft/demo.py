"""Demo handler: simulates bot responses using MCP tools.

Uses the MCP bridge to call tools with sample data, validating
the full tool -> DB -> WS pipeline. Used when no LLM is configured.
"""
import asyncio

import aiosqlite
from fastapi import WebSocket

from pagecraft.orchestrator.mcp_bridge import MCPBridge
from pagecraft.registry import ComponentDef
from pagecraft.services.page_service import save_component, get_page_components
from pagecraft.routes.websocket import send_chat_html, send_component_html, send_agenda_html


# Demo data and conversation sequence — follows interview order
DEMO_SEQUENCE = [
    {
        "keywords": ["problem", "utmaning", "nuläge", "bakgrund", "projekt", "börja", "start", "hej"],
        "component": "situation",
        "tool": "write_situation",
        "tool_args": {
            "current_situation": "Planeringsbeslut påverkar utsläpp från förändrad markanvändning, byggande och transporter under många decennier framöver.",
            "challenge": "Många kommuner saknar verktyg för att kvantifiera klimatpåverkan i tidiga planeringsskeden.",
            "solution": "Klimatkalkylen beräknar utsläpp från relevanta sektorer och kan integreras direkt i planeringsprocessen.",
        },
        "bot_reply": "Tack! Jag har skapat en sammanfattning av nuläge, utmaning och lösning. Stämmer det?",
    },
    {
        "keywords": ["erfarenhet", "implementer", "process", "tidslinje"],
        "component": "implementation",
        "tool": "write_implementation",
        "tool_args": {
            "heading": "Erfarenheter från implementering",
            "body_text": "Analysen visade på flera möjliga strategier för hållbar utveckling. Genom att integrera Klimatkalkylen i planeringsprocessen kunde kommunen jämföra olika scenarier och fatta mer informerade beslut. Pilotprojektet genomfördes under sex månader med stöd från regionala och nationella aktörer.",
        },
        "bot_reply": "Här är implementeringsberättelsen. Vill du ändra eller lägga till något?",
    },
    {
        "keywords": ["siffr", "resultat", "procent", "minska", "nyckeltal", "kpi"],
        "component": "kpis",
        "tool": "write_kpis",
        "tool_args": {
            "items": [
                {"label": "CO2-besparing", "value": ">50%", "description": "Reduktion av nettoutsläpp genom kombinerade åtgärder"},
                {"label": "Lönsamhet", "value": "Hög", "description": "Flera åtgärder har positiv kostnads-nyttobalans"},
                {"label": "Investering", "value": "2,5 MSEK", "description": "Total investering inklusive licens och utbildning"},
            ],
        },
        "bot_reply": "Jag har sammanställt nyckeltalen. Stämmer siffrorna?",
    },
    {
        "keywords": ["effekt", "impact", "co2", "klimat", "nytta"],
        "component": "impact",
        "tool": "write_impact",
        "tool_args": {
            "items": [
                {"label": "CO2e-minskningspotential", "value": ">50%", "description": "Kombinerade åtgärder kan minska nettoutsläppen med mer än hälften."},
                {"label": "Klimat för pengarna", "value": "Hög", "description": "Flera åtgärder har positiv kostnads-nyttobalans."},
                {"label": "Spridningspotential", "value": "290 kommuner", "description": "Kan användas av alla Sveriges kommuner."},
            ],
        },
        "bot_reply": "Här är effektbedömningen. Stämmer siffrorna?",
    },
    {
        "keywords": ["resurs", "budget", "personal", "partner"],
        "component": "resources",
        "tool": "write_resources",
        "tool_args": {
            "heading": "Resurser",
            "body_text": "Projektet krävde en tvärfunktionell grupp med kompetens inom samhällsplanering, klimatberäkning och IT. Licenskostnaden för Klimatkalkylen var begränsad, men utbildning och processanpassning stod för huvuddelen av investeringen. Stöd från Viable Cities och SKR var avgörande.",
        },
        "bot_reply": "Här är en sammanfattning av resurserna. Saknas något?",
    },
    {
        "keywords": ["kom igång", "steg", "börja använda", "getting started"],
        "component": "getting_started",
        "tool": "write_getting_started",
        "tool_args": {
            "steps": [
                {"title": "Licensiering och dataimport", "description": "Skaffa licens och importera kommunens grunddata."},
                {"title": "Pilotprojekt", "description": "Genomför pilotberäkningar på ett pågående planeringsprojekt."},
                {"title": "Åtgärdsanalys", "description": "Analysera åtgärdsalternativ och integrera i processen."},
            ],
        },
        "bot_reply": "Jag har skapat en tre-stegsguide. Stämmer processen?",
    },
    {
        "keywords": ["intressent", "målgrupp", "persona", "vem", "roll"],
        "component": "personas",
        "tool": "write_personas",
        "tool_args": {
            "personas": [
                {"role": "Kommunplanerare", "benefit": "Får kvantitativt underlag för klimatsmarta planeringsbeslut.", "quote": "Nu kan vi visa politikerna exakt vilken skillnad olika val gör."},
                {"role": "Miljöstrateg", "benefit": "Kan koppla planering till kommunens klimatmål."},
                {"role": "Politiker", "benefit": "Får beslutsunderlag med långsiktiga klimatkonsekvenser."},
            ],
        },
        "bot_reply": "Jag har sammanställt intressenterna. Saknas någon?",
    },
    {
        "keywords": ["titel", "introduktion", "sammanfattning", "hero"],
        "component": "hero",
        "tool": "write_hero",
        "tool_args": {
            "title": "Klimatkalkylen",
            "description": "Klimatkalkylen är ett verktyg som hjälper kommuner att beräkna och visualisera klimatpåverkan från samhällsplanering. Genom att använda verktyget i tidiga planeringsskeden kan kommuner fatta mer informerade beslut.",
        },
        "bot_reply": "Jag har skapat en introduktionssektion. Stämmer det?",
    },
    {
        "keywords": ["metadata", "kommun", "sektor", "tema"],
        "component": "metadata",
        "tool": "write_metadata",
        "tool_args": {
            "municipality": "Huddinge kommun",
            "sector": "Samhällsplanering",
            "twin_transition": "Grön + Digital",
            "themes": ["Klimatberäkning", "Samhällsplanering", "Hållbart byggande"],
            "technical_solution": ["Klimatkalkylen", "GIS-integration"],
        },
        "bot_reply": "Metadata är ifylld. Vill du ändra något?",
    },
    {
        "keywords": ["kontakt", "mejl", "email", "telefon"],
        "component": "contact",
        "tool": "write_contact",
        "tool_args": {
            "name": "Anna Exempel",
            "title": "Projektledare",
            "organization": "Huddinge kommun",
            "email": "anna.exempel@example.com",
        },
        "bot_reply": "Kontaktinformationen är tillagd. Vill du ändra något?",
    },
]


def _find_matching_demo(text: str, already_rendered: set[str]) -> dict | None:
    """Find the first demo entry matching the user text."""
    text_lower = text.lower()
    for entry in DEMO_SEQUENCE:
        if entry["component"] in already_rendered:
            continue
        if any(kw in text_lower for kw in entry["keywords"]):
            return entry
    # Fallback: next unrendered
    for entry in DEMO_SEQUENCE:
        if entry["component"] not in already_rendered:
            return entry
    return None


async def demo_handler(
    ws: WebSocket,
    page_id: int,
    user_text: str,
    db: aiosqlite.Connection,
    registry: list[ComponentDef],
) -> None:
    """Handle a user message in demo mode by calling MCP tools."""
    existing = await get_page_components(db, page_id)
    already_rendered = {c.component_type for c in existing}

    match = _find_matching_demo(user_text, already_rendered)
    if match is None:
        await send_chat_html(ws, "assistant", "Alla sektioner är redan skapade! Du kan granska och godkänna dem till höger.")
        return

    # Small delay for natural feel
    await asyncio.sleep(0.5)

    # Call MCP tool via bridge
    bridge: MCPBridge = ws.app.state.mcp_bridge
    result = await bridge.call_tool(match["tool"], match["tool_args"])

    # Save to DB
    comp_def = next(c for c in registry if c.type == match["component"])
    component = await save_component(
        db,
        page_id=page_id,
        component_type=match["component"],
        display_order=comp_def.page_order,
        html=result["html"],
        data_json=result["data_json"],
    )

    # Push to preview
    await send_component_html(ws, match["component"], result["html"], "draft", component.id)

    # Bot reply
    await send_chat_html(ws, "assistant", match["bot_reply"])

    # Update agenda
    all_components = await get_page_components(db, page_id)
    statuses = {c.component_type: c.status for c in all_components}
    await send_agenda_html(ws, registry, statuses)
