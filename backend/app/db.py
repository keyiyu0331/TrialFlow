"""Database engine and session setup.

PostgreSQL is the target (set DATABASE_URL). Tests use SQLite in-memory, so the
models avoid PostgreSQL-only types and SQLite gets foreign-key enforcement on.
"""

import os

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://localhost/trialflow")


class Base(DeclarativeBase):
    pass


@event.listens_for(Engine, "connect")
def _sqlite_enable_foreign_keys(dbapi_connection, connection_record):
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def make_engine(url: str = DATABASE_URL, **kwargs):
    return create_engine(url, **kwargs)


SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)

_engine = None


def get_engine():
    """The app-wide engine, created on first use from DATABASE_URL."""
    global _engine
    if _engine is None:
        kwargs = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
        _engine = make_engine(DATABASE_URL, **kwargs)
    return _engine


def get_session():
    """FastAPI dependency: one session per request."""
    with SessionLocal(bind=get_engine()) as session:
        yield session


def init_db(engine: Engine) -> None:
    """Create missing tables, and add columns that newer code expects to an older database.

    ``create_all`` never alters an existing table, so a database built before a column existed
    would fail with "no such column". Each addition here is non-destructive and safe to re-run.
    """
    Base.metadata.create_all(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("trials")}
    if "intervention_types" not in columns:
        # Registry trials are backfilled by the next scripts/import_registry.py run.
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE trials ADD COLUMN intervention_types JSON NOT NULL DEFAULT '[]'"))
