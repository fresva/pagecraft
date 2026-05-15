import json
import secrets
from datetime import datetime

import aiosqlite

from pagecraft.models.page import Annotation, Component, Page


def _generate_uri_token() -> str:
    return secrets.token_urlsafe(6)  # ~8 chars


async def create_page(db: aiosqlite.Connection, title: str | None = None) -> Page:
    uri_token = _generate_uri_token()
    cursor = await db.execute(
        "INSERT INTO pages (uri_token, title) VALUES (?, ?)",
        (uri_token, title),
    )
    await db.commit()
    return Page(id=cursor.lastrowid, uri_token=uri_token, title=title)


async def get_page(db: aiosqlite.Connection, page_id: int) -> Page | None:
    cursor = await db.execute("SELECT * FROM pages WHERE id = ?", (page_id,))
    row = await cursor.fetchone()
    if not row:
        return None
    return Page(**dict(row))


async def get_page_by_token(db: aiosqlite.Connection, uri_token: str) -> Page | None:
    cursor = await db.execute("SELECT * FROM pages WHERE uri_token = ?", (uri_token,))
    row = await cursor.fetchone()
    if not row:
        return None
    return Page(**dict(row))


async def save_component(
    db: aiosqlite.Connection,
    page_id: int,
    component_type: str,
    display_order: int,
    html: str,
    data_json: dict | str,
) -> Component:
    if isinstance(data_json, dict):
        data_json = json.dumps(data_json, ensure_ascii=False)

    # Try update first
    cursor = await db.execute(
        "SELECT id, version FROM components WHERE page_id = ? AND component_type = ?",
        (page_id, component_type),
    )
    existing = await cursor.fetchone()

    if existing:
        new_version = existing["version"] + 1
        await db.execute(
            """UPDATE components
               SET html = ?, data_json = ?, display_order = ?,
                   version = ?, status = 'draft', updated_at = ?
               WHERE id = ?""",
            (html, data_json, display_order, new_version, datetime.now().isoformat(), existing["id"]),
        )
        await db.commit()
        return Component(
            id=existing["id"],
            page_id=page_id,
            component_type=component_type,
            display_order=display_order,
            html=html,
            data_json=data_json,
            status="draft",
            version=new_version,
        )
    else:
        cursor = await db.execute(
            """INSERT INTO components (page_id, component_type, display_order, html, data_json)
               VALUES (?, ?, ?, ?, ?)""",
            (page_id, component_type, display_order, html, data_json),
        )
        await db.commit()
        return Component(
            id=cursor.lastrowid,
            page_id=page_id,
            component_type=component_type,
            display_order=display_order,
            html=html,
            data_json=data_json,
        )


async def get_page_components(db: aiosqlite.Connection, page_id: int) -> list[Component]:
    cursor = await db.execute(
        "SELECT * FROM components WHERE page_id = ? ORDER BY display_order",
        (page_id,),
    )
    rows = await cursor.fetchall()
    return [Component(**dict(row)) for row in rows]


async def update_component_status(
    db: aiosqlite.Connection, component_id: int, status: str
) -> None:
    await db.execute(
        "UPDATE components SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now().isoformat(), component_id),
    )
    await db.commit()
