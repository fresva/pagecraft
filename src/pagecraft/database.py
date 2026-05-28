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

CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0,
    resolved_at TIMESTAMP,
    decision TEXT NOT NULL DEFAULT 'pending',
    curator_note TEXT,
    resolved_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
CREATE INDEX IF NOT EXISTS idx_annotations_component_id ON annotations(component_id);
CREATE INDEX IF NOT EXISTS idx_annotations_unresolved ON annotations(resolved) WHERE resolved = 0;
CREATE INDEX IF NOT EXISTS idx_messages_page_id ON conversation_messages(page_id);
"""


async def _column_names(db: aiosqlite.Connection, table: str) -> set[str]:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    return {row[1] for row in rows}


async def _migrate(db: aiosqlite.Connection) -> None:
    """Apply idempotent schema migrations for databases created before
    the curation-workflow columns existed. Safe to run on every startup."""
    # Page lifecycle: the old single state 'active' becomes 'in_interview'.
    await db.execute("UPDATE pages SET status = 'in_interview' WHERE status = 'active'")

    # Annotation curation columns (added incrementally on existing tables).
    ann_cols = await _column_names(db, "annotations")
    if "decision" not in ann_cols:
        await db.execute(
            "ALTER TABLE annotations ADD COLUMN decision TEXT NOT NULL DEFAULT 'pending'"
        )
    if "curator_note" not in ann_cols:
        await db.execute("ALTER TABLE annotations ADD COLUMN curator_note TEXT")
    if "resolved_by" not in ann_cols:
        await db.execute("ALTER TABLE annotations ADD COLUMN resolved_by TEXT")
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
