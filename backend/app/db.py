"""Database engine and session setup.

PostgreSQL is the target (set DATABASE_URL). Tests use SQLite in-memory, so the
models avoid PostgreSQL-only types and SQLite gets foreign-key enforcement on.
"""

import os

from sqlalchemy import create_engine, event
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
