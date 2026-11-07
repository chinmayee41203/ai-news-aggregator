"""Create missing tables and add missing columns (safe to run repeatedly).

`create_all` only creates whole tables — it never adds a column to a table
that already exists. Columns added after Phase 2 are listed in MIGRATIONS and
applied with ADD COLUMN IF NOT EXISTS, so old databases catch up automatically.

Run:  uv run python -m app.database.create_tables
"""

from sqlalchemy import text

from app.database.connection import engine
from app.database.models import Base

MIGRATIONS = [
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS section_label VARCHAR(16)",
    "ALTER TABLE digests ADD COLUMN IF NOT EXISTS about_india BOOLEAN NOT NULL DEFAULT FALSE",
]


def create_tables() -> None:
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for sql in MIGRATIONS:
            conn.execute(text(sql))


if __name__ == "__main__":
    create_tables()
    print("Tables ready:", ", ".join(Base.metadata.tables))
