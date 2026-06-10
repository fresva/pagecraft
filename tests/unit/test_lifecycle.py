"""Tests for page lifecycle status and the idempotent schema migration."""
import aiosqlite

from pagecraft.database import _migrate
from pagecraft.services.page_service import (
    create_page,
    get_page,
    update_page_status,
)

# A pre-refactor schema: pages default 'active', plus a legacy annotations
# table and review-era component statuses that the migration must clean up.
OLD_SCHEMA = """
CREATE TABLE pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uri_token TEXT UNIQUE NOT NULL,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL,
    component_type TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    html TEXT NOT NULL DEFAULT '',
    data_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft'
);
CREATE TABLE annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    field TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL
);
"""


async def test_create_page_starts_in_interview(db):
    page = await create_page(db, title="Test")
    assert page.status == "in_interview"
    fetched = await get_page(db, page.id)
    assert fetched.status == "in_interview"


async def test_update_page_status(db):
    page = await create_page(db, title="Test")
    await update_page_status(db, page.id, "published")
    fetched = await get_page(db, page.id)
    assert fetched.status == "published"


async def test_migration_collapses_legacy_states_and_drops_annotations():
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript(OLD_SCHEMA)
    await conn.execute(
        "INSERT INTO pages (uri_token, title, status) VALUES ('tok', 'x', 'awaiting_review')"
    )
    await conn.execute(
        "INSERT INTO components (page_id, component_type, status) "
        "VALUES (1, 'hero', 'reviewer_approved')"
    )
    await conn.commit()

    await _migrate(conn)

    # Legacy review states collapse into the two-state model.
    cursor = await conn.execute("SELECT status FROM pages WHERE uri_token = 'tok'")
    assert (await cursor.fetchone())["status"] == "in_interview"
    cursor = await conn.execute("SELECT status FROM components WHERE component_type = 'hero'")
    assert (await cursor.fetchone())["status"] == "agreed"

    # The annotations table is gone.
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='annotations'"
    )
    assert await cursor.fetchone() is None

    # Idempotent: running again must not raise.
    await _migrate(conn)
    await conn.close()
