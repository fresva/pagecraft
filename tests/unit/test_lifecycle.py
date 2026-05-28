"""Tests for page lifecycle status and the idempotent schema migration."""
import aiosqlite

from pagecraft.database import _column_names, _migrate
from pagecraft.services.page_service import (
    create_page,
    get_page,
    update_page_status,
)

# A pre-curation-workflow schema: pages default 'active', annotations missing
# the decision/curator_note/resolved_by columns.
OLD_SCHEMA = """
CREATE TABLE pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uri_token TEXT UNIQUE NOT NULL,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    field TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def test_create_page_starts_in_interview(db):
    page = await create_page(db, title="Test")
    assert page.status == "in_interview"
    fetched = await get_page(db, page.id)
    assert fetched.status == "in_interview"


async def test_update_page_status(db):
    page = await create_page(db, title="Test")
    await update_page_status(db, page.id, "awaiting_review")
    fetched = await get_page(db, page.id)
    assert fetched.status == "awaiting_review"


async def test_migration_adds_columns_and_migrates_status():
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript(OLD_SCHEMA)
    await conn.execute(
        "INSERT INTO pages (uri_token, title, status) VALUES ('tok', 'x', 'active')"
    )
    await conn.commit()

    await _migrate(conn)

    cols = await _column_names(conn, "annotations")
    assert {"decision", "curator_note", "resolved_by"} <= cols
    cursor = await conn.execute("SELECT status FROM pages WHERE uri_token = 'tok'")
    row = await cursor.fetchone()
    assert row["status"] == "in_interview"

    # Idempotent: running again must not raise.
    await _migrate(conn)
    await conn.close()
