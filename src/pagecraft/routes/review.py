"""Researcher review UI: walk a finished page's annotations, edit components,
mark each component reviewed, and publish."""
import html
import json

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from pagecraft.models.page import Page
from pagecraft.services.annotation_service import (
    get_annotation,
    get_annotations_for_page,
    set_annotation_decision,
    value_at_path,
)
from pagecraft.services.edit_form import apply_edits, build_edit_fields
from pagecraft.services.page_service import (
    get_component,
    get_page,
    get_page_components,
    save_component,
    update_component_status,
    update_page_status,
)

router = APIRouter()

REVIEW_STATES = ("awaiting_review", "in_review")


def _labels(registry) -> dict[str, str]:
    return {c.type: c.label for c in registry}


def _readiness(components, annotations):
    total = len(components)
    reviewed = sum(1 for c in components if c.status == "reviewer_approved")
    unresolved = sum(1 for a in annotations if a.decision == "pending")
    ready = total > 0 and reviewed == total and unresolved == 0
    return reviewed, total, unresolved, ready


def _component_data(component) -> dict:
    try:
        return json.loads(component.data_json)
    except (TypeError, json.JSONDecodeError):
        return {}


@router.get("/review", response_class=HTMLResponse)
async def review_index(request: Request):
    db = request.app.state.db
    templates = request.app.state.templates
    cursor = await db.execute(
        "SELECT * FROM pages WHERE status IN ('awaiting_review', 'in_review') "
        "ORDER BY updated_at DESC"
    )
    rows = await cursor.fetchall()
    pages = [Page(**dict(row)) for row in rows]
    return templates.TemplateResponse(request, "review_index.html", {"pages": pages})


@router.get("/review/{page_id}", response_class=HTMLResponse)
async def review_page(request: Request, page_id: int):
    db = request.app.state.db
    templates = request.app.state.templates
    registry = request.app.state.component_registry

    page = await get_page(db, page_id)
    if not page or page.status not in REVIEW_STATES:
        raise HTTPException(status_code=404, detail="Page not in review")

    # Opening an awaiting_review page starts the review.
    if page.status == "awaiting_review":
        await update_page_status(db, page_id, "in_review")
        page.status = "in_review"

    labels = _labels(registry)
    components = await get_page_components(db, page_id)
    annotations = await get_annotations_for_page(db, page_id)

    data_by_cid = {c.id: _component_data(c) for c in components}
    label_by_cid = {c.id: labels.get(c.component_type, c.component_type) for c in components}
    ann_items = [
        {
            "ann": a,
            "value": value_at_path(data_by_cid.get(a.component_id, {}), a.field),
            "label": label_by_cid.get(a.component_id, ""),
        }
        for a in annotations
    ]
    reviewed, total, unresolved, ready = _readiness(components, annotations)

    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "page": page,
            "page_id": page_id,
            "components": components,
            "labels": labels,
            "annotations": ann_items,
            "reviewed_count": reviewed,
            "total_count": total,
            "unresolved_count": unresolved,
            "ready": ready,
            "published": False,
        },
    )


@router.post("/review/{page_id}/annotation/{annotation_id}", response_class=HTMLResponse)
async def review_annotation_decision(
    request: Request,
    page_id: int,
    annotation_id: int,
    decision: str = Form(...),
    curator_note: str = Form(""),
):
    db = request.app.state.db
    templates = request.app.state.templates
    registry = request.app.state.component_registry

    await set_annotation_decision(
        db, annotation_id, decision, curator_note=curator_note or None, resolved_by="forskare"
    )
    ann = await get_annotation(db, annotation_id)
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")

    component = await get_component(db, ann.component_id)
    labels = _labels(registry)
    value = value_at_path(_component_data(component), ann.field) if component else None
    label = labels.get(component.component_type, "") if component else ""
    return templates.TemplateResponse(
        request,
        "partials/annotation_card.html",
        {"ann": ann, "value": value, "comp_label": label, "page_id": page_id},
    )


@router.post("/review/{page_id}/component/{component_id}/review", response_class=HTMLResponse)
async def review_component_toggle(
    request: Request, page_id: int, component_id: int, reviewed: str = Form(...)
):
    db = request.app.state.db
    templates = request.app.state.templates
    registry = request.app.state.component_registry

    new_status = "reviewer_approved" if reviewed == "true" else "agreed"
    await update_component_status(db, component_id, new_status)
    component = await get_component(db, component_id)
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")
    label = _labels(registry).get(component.component_type, component.component_type)
    return templates.TemplateResponse(
        request,
        "partials/review_component.html",
        {"c": component, "label": label, "page_id": page_id},
    )


@router.get("/review/{page_id}/component/{component_id}/edit-form", response_class=HTMLResponse)
async def review_edit_form(request: Request, page_id: int, component_id: int):
    db = request.app.state.db
    registry = request.app.state.component_registry

    component = await get_component(db, component_id)
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")
    label = _labels(registry).get(component.component_type, component.component_type)
    fields = build_edit_fields(_component_data(component))
    form_html = (
        f'<form hx-post="/review/{page_id}/component/{component_id}/edit" '
        f'hx-target="#review-comp-{component_id}" hx-swap="outerHTML">'
        f'<h3>Redigera: {html.escape(label)}</h3>'
        f'{fields}'
        f'<div class="edit-actions">'
        f'<button type="submit" class="btn-save-edit" '
        f'onclick="document.getElementById(\'review-modal\').hidden=true">Spara</button>'
        f'<button type="button" class="btn-cancel-edit" '
        f'onclick="document.getElementById(\'review-modal\').hidden=true">Avbryt</button>'
        f'</div></form>'
    )
    return HTMLResponse(form_html)


@router.post("/review/{page_id}/component/{component_id}/edit", response_class=HTMLResponse)
async def review_edit(request: Request, page_id: int, component_id: int):
    db = request.app.state.db
    templates = request.app.state.templates
    registry = request.app.state.component_registry
    bridge = request.app.state.mcp_bridge

    component = await get_component(db, component_id)
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")
    comp_def = next((c for c in registry if c.type == component.component_type), None)
    if not comp_def:
        raise HTTPException(status_code=404, detail="Unknown component type")

    form = await request.form()
    fields = {key: str(val) for key, val in form.items()}
    edited = apply_edits(_component_data(component), fields)
    result = await bridge.call_tool(comp_def.tool, edited)
    await save_component(
        db, page_id=page_id, component_type=component.component_type,
        display_order=comp_def.page_order, html=result["html"], data_json=result["data_json"],
    )
    # A researcher edit invalidates any prior approval — needs re-review.
    await update_component_status(db, component_id, "agreed")
    component = await get_component(db, component_id)
    label = _labels(registry).get(component.component_type, component.component_type)
    return templates.TemplateResponse(
        request,
        "partials/review_component.html",
        {"c": component, "label": label, "page_id": page_id},
    )


@router.post("/review/{page_id}/publish", response_class=HTMLResponse)
async def review_publish(request: Request, page_id: int):
    db = request.app.state.db
    templates = request.app.state.templates

    components = await get_page_components(db, page_id)
    annotations = await get_annotations_for_page(db, page_id)
    reviewed, total, unresolved, ready = _readiness(components, annotations)

    if not ready:
        return templates.TemplateResponse(
            request,
            "partials/publish_bar.html",
            {
                "page_id": page_id,
                "reviewed_count": reviewed,
                "total_count": total,
                "unresolved_count": unresolved,
                "ready": ready,
                "published": False,
                "error": "Alla komponenter måste vara granskade och alla annoteringar hanterade.",
            },
        )

    await update_page_status(db, page_id, "published")
    return templates.TemplateResponse(
        request,
        "partials/publish_bar.html",
        {"page_id": page_id, "published": True},
    )
