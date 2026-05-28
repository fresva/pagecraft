from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from pagecraft.registry import interview_ordered
from pagecraft.services.page_service import (
    add_conversation_message,
    create_page,
    get_page,
    get_page_components,
)

router = APIRouter()


@router.get("/interview/{page_id}", response_class=HTMLResponse)
async def interview_page(request: Request, page_id: int):
    templates = request.app.state.templates
    registry = request.app.state.component_registry
    db = request.app.state.db

    # Ensure page exists
    page = await get_page(db, page_id)
    if not page:
        # Auto-create for demo purposes
        page = await create_page(db, title="Demo")

    # Load existing conversation history (user + assistant text messages only)
    cursor = await db.execute(
        "SELECT role, content FROM conversation_messages "
        "WHERE page_id = ? AND role IN ('user', 'assistant') "
        "AND content IS NOT NULL AND content != '' "
        "ORDER BY id",
        (page.id,),
    )
    rows = await cursor.fetchall()
    chat_messages = [{"role": r["role"], "content": r["content"]} for r in rows]

    # On first visit, persist the scripted opening message so the bot sees it
    # in conversation history (and won't re-ask the orienting questions).
    if not chat_messages:
        loader = request.app.state.prompt_loader
        settings = request.app.state.settings
        opening = loader.opening_message(settings.info_url)
        if opening:
            await add_conversation_message(db, page.id, "assistant", opening)
            chat_messages = [{"role": "assistant", "content": opening}]

    # Load existing components for the preview panel
    components = await get_page_components(db, page.id)
    components_html = {c.component_type: c.html for c in components}
    component_statuses = {c.component_type: c.status for c in components}
    component_ids = {c.component_type: c.id for c in components}

    return templates.TemplateResponse(
        request,
        "interview.html",
        {
            "page_id": page.id,
            "uri_token": page.uri_token,
            "agenda_items": interview_ordered(registry),
            "chat_messages": chat_messages,
            "components_html": components_html,
            "component_statuses": component_statuses,
            "component_ids": component_ids,
        },
    )


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Create a new interview page and redirect to it."""
    db = request.app.state.db
    page = await create_page(db, title="Ny fallstudie")
    return RedirectResponse(url=f"/interview/{page.id}")
