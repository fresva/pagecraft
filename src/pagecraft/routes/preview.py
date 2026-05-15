from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from pagecraft.services.page_service import get_page_by_token, get_page_components

router = APIRouter()


@router.get("/preview/{uri_token}", response_class=HTMLResponse)
async def preview_page(request: Request, uri_token: str):
    templates = request.app.state.templates
    db = request.app.state.db

    page = await get_page_by_token(db, uri_token)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    components = await get_page_components(db, page.id)
    components_html = {c.component_type: c.html for c in components}

    return templates.TemplateResponse(
        request,
        "preview.html",
        {"page": page, "components_html": components_html},
    )
