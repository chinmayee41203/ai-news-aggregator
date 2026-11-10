"""Database engine and sessions.

ENVIRONMENT picks the database:
- local (default): DATABASE_URL — the Docker Postgres on this PC
- production:      PRODUCTION_DATABASE_URL (or DATABASE_URL if that is unset) — Neon

On GitHub Actions we set ENVIRONMENT=production and DATABASE_URL=<Neon URL>.
Locally you can keep both URLs in .env and switch with ENVIRONMENT.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

import app.config  # noqa: F401  (loads .env)

LOCAL_DEFAULT = "postgresql+psycopg://postgres:postgres@localhost:5433/ai_news_aggregator"

ENVIRONMENT = os.getenv("ENVIRONMENT", "local").strip().lower()


def _normalize(url: str) -> str:
    """Neon gives 'postgresql://…' (or 'postgres://…'); SQLAlchemy needs the
    psycopg driver named in the scheme."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def get_database_url() -> str:
    if ENVIRONMENT == "production":
        url = os.getenv("PRODUCTION_DATABASE_URL") or os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("ENVIRONMENT=production but no PRODUCTION_DATABASE_URL / DATABASE_URL is set")
    else:
        url = os.getenv("DATABASE_URL", LOCAL_DEFAULT)
    return _normalize(url.strip())


DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Neon's free tier sleeps when idle; check connections before use
    connect_args={"connect_timeout": 30},  # give a sleeping Neon database time to wake up
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def describe_database() -> str:
    """Safe-to-print description (never includes the password)."""
    url = make_url(DATABASE_URL)
    return f"{ENVIRONMENT} → {url.host}:{url.port or 5432}/{url.database}"


@contextmanager
def get_session() -> Iterator[Session]:
    """Open a session, commit on success, roll back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
