"""Persistence and path helpers for component annotations.

Annotations are produced by the post-processing pass (see orchestrator/annotator)
and consumed by the researcher review UI. Each annotation targets a field of a
component's data_json via a dotted path (e.g. "current_situation" or
"items.0.value").
"""
from datetime import datetime

import aiosqlite

from pagecraft.models.page import Annotation


async def create_annotation(
    db: aiosqlite.Connection,
    component_id: int,
    field: str,
    message: str,
    severity: str,
) -> int:
    cursor = await db.execute(
        "INSERT INTO annotations (component_id, field, message, severity) "
        "VALUES (?, ?, ?, ?)",
        (component_id, field, message, severity),
    )
    await db.commit()
    return cursor.lastrowid


async def get_annotations_for_component(
    db: aiosqlite.Connection, component_id: int
) -> list[Annotation]:
    cursor = await db.execute(
        "SELECT * FROM annotations WHERE component_id = ? ORDER BY id",
        (component_id,),
    )
    rows = await cursor.fetchall()
    return [Annotation(**dict(row)) for row in rows]


async def get_annotations_for_page(
    db: aiosqlite.Connection, page_id: int
) -> list[Annotation]:
    cursor = await db.execute(
        "SELECT a.* FROM annotations a "
        "JOIN components c ON a.component_id = c.id "
        "WHERE c.page_id = ? ORDER BY a.id",
        (page_id,),
    )
    rows = await cursor.fetchall()
    return [Annotation(**dict(row)) for row in rows]


async def clear_annotations_for_page(db: aiosqlite.Connection, page_id: int) -> None:
    """Remove all annotations for a page so the pass can be re-run idempotently."""
    await db.execute(
        "DELETE FROM annotations WHERE component_id IN "
        "(SELECT id FROM components WHERE page_id = ?)",
        (page_id,),
    )
    await db.commit()


async def set_annotation_decision(
    db: aiosqlite.Connection,
    annotation_id: int,
    decision: str,
    curator_note: str | None = None,
    resolved_by: str | None = None,
) -> None:
    resolved = 1 if decision != "pending" else 0
    await db.execute(
        "UPDATE annotations SET decision = ?, curator_note = ?, resolved_by = ?, "
        "resolved = ?, resolved_at = ? WHERE id = ?",
        (
            decision,
            curator_note,
            resolved_by,
            resolved,
            datetime.now().isoformat() if resolved else None,
            annotation_id,
        ),
    )
    await db.commit()


def flatten_paths(data: dict) -> dict[str, str]:
    """Flatten a component's data_json into {dotted_path: string_value}.

    Mirrors the structures the components use: flat strings, lists of dicts
    (e.g. items.0.value) and lists of strings (e.g. themes.0).
    """
    out: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, str):
            out[key] = value
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    for subkey, subval in item.items():
                        if isinstance(subval, str):
                            out[f"{key}.{i}.{subkey}"] = subval
                elif isinstance(item, str):
                    out[f"{key}.{i}"] = item
    return out


def value_at_path(data: dict, path: str) -> str | None:
    """Return the string value at a dotted path, or None if it doesn't resolve."""
    return flatten_paths(data).get(path)
