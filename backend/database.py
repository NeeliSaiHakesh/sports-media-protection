"""
database.py — SQLite setup using aiosqlite
"""
import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "sports_media.db")

CREATE_ASSETS = """
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    hash TEXT NOT NULL,
    embedding TEXT DEFAULT NULL,
    source_url TEXT DEFAULT '',
    platform TEXT DEFAULT 'Unknown',
    is_reference INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_SCANS = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    similarity REAL DEFAULT 0.0,
    ai_similarity REAL DEFAULT 0.0,
    hash_similarity REAL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'Original',
    risk_score REAL DEFAULT 0.0,
    confidence REAL DEFAULT 0.0,
    matches_json TEXT DEFAULT '[]',
    top_match_source TEXT DEFAULT '',
    num_matches INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id)
)
"""


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(CREATE_ASSETS)
        await db.execute(CREATE_SCANS)
        # Migrate existing DB — add new columns if they don't exist
        for col, definition in [
            ("embedding",       "TEXT DEFAULT NULL"),
            ("ai_similarity",   "REAL DEFAULT 0.0"),
            ("hash_similarity", "REAL DEFAULT 0.0"),
        ]:
            try:
                if col in ("ai_similarity", "hash_similarity"):
                    await db.execute(f"ALTER TABLE scans ADD COLUMN {col} {definition}")
                else:
                    await db.execute(f"ALTER TABLE assets ADD COLUMN {col} {definition}")
            except Exception:
                pass  # Column already exists — ignore
        await db.commit()
