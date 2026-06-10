import aiosqlite
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uri_token TEXT UNIQUE NOT NULL,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'in_interview',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    component_type TEXT NOT NULL,
    display_order INTEGER NOT NULL,
    html TEXT NOT NULL,
    data_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(page_id, component_type)
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_call_id TEXT,
    tool_name TEXT,
    tool_arguments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pages_uri_token ON pages(uri_token);
CREATE INDEX IF NOT EXISTS idx_components_page_id ON components(page_id);
CREATE INDEX IF NOT EXISTS idx_messages_page_id ON conversation_messages(page_id);
"""


async def _migrate(db: aiosqlite.Connection) -> None:
    """Idempotent migrations to bring older databases onto the current,
    two-state lifecycle. Safe to run on every startup.

    The page lifecycle is now just 'in_interview' -> 'published'. The legacy
    researcher-review states and the annotation/curation workflow have been
    removed, so we collapse old statuses and drop the annotations table.
    """
    await db.execute(
        "UPDATE pages SET status = 'in_interview' "
        "WHERE status IN ('active', 'awaiting_review', 'in_review')"
    )
    await db.execute(
        "UPDATE components SET status = 'agreed' WHERE status = 'reviewer_approved'"
    )
    await db.execute("DROP TABLE IF EXISTS annotations")
    await db.commit()


async def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()
        await _migrate(db)


async def get_db(db_path: str) -> aiosqlite.Connection:
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db
