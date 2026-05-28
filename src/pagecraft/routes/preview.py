from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from pagecraft.services.page_service import (
    get_page,
    get_page_by_token,
    get_page_components,
)

router = APIRouter()


@router.get("/preview/{uri_token}", response_class=HTMLResponse)
async def preview_page(request: Request, uri_token: str):
    templates = request.app.state.templates
    db = request.app.state.db

    page = await get_page_by_token(db, uri_token)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    registry = request.app.state.component_registry
    components = await get_page_components(db, page.id)
    components_html = {c.component_type: c.html for c in components}

    return templates.TemplateResponse(
        request,
        "preview.html",
        {
            "page": page,
            "components_html": components_html,
            "labels": {c.type: c.label for c in registry},
        },
    )


@router.get("/case/{page_id}", response_class=HTMLResponse)
async def case_page(request: Request, page_id: int):
    """Public, read-only view of a published page — no chat, agenda, or controls.

    Only renders filled components, in page order; unfilled ones are omitted so
    the public never sees placeholders. 404 unless the page is published."""
    templates = request.app.state.templates
    db = request.app.state.db
    registry = request.app.state.component_registry

    page = await get_page(db, page_id)
    if not page or page.status != "published":
        raise HTTPException(status_code=404, detail="Page not published")

    components = await get_page_components(db, page_id)
    by_type = {c.component_type: c.html for c in components}
    ordered_html = [by_type[c.type] for c in registry if c.type in by_type]

    return templates.TemplateResponse(
        request,
        "case.html",
        {"page": page, "components_html": ordered_html},
    )
