from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.core.config import settings
from src.core.logging import logger

# SQLite needs check_same_thread=False so background tasks (thumbnail updates)
# can use the shared engine from a different thread. We also enable WAL mode
# (fix #4) so concurrent reads + the occasional background write don't hit
# "database is locked" errors.
_is_sqlite = "sqlite" in settings.DB_URL

engine = create_engine(
    settings.DB_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    echo=False,
    # Grow the connection pool a bit so background thumbnail tasks and request
    # handlers don't starve each other.
    pool_size=10 if not _is_sqlite else 5,
    max_overflow=20 if not _is_sqlite else 10,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable WAL + sane busy_timeout on every new SQLite connection."""
    if not _is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        # Wait up to 5s to acquire a write lock instead of failing immediately.
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for FastAPI routes"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables and run lightweight in-place migrations.

    SQLAlchemy's create_all only ADDS missing tables/columns — it can't drop a
    UNIQUE index or change a column. For the fixes here (cache_key no longer
    unique, created_at now indexed) we issue the small, safe ALTERs directly on
    SQLite, idempotently.
    """
    Base.metadata.create_all(bind=engine)

    if not _is_sqlite:
        return

    with engine.connect() as conn:
        from sqlalchemy import text

        # Migration: drop the legacy UNIQUE index on chart_specs.cache_key (fix #2).
        # The plain index `ix_chart_specs_cache_key` (non-unique) is recreated by
        # create_all only if missing, so we drop the unique variant explicitly.
        rows = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='chart_specs' AND sql LIKE '%UNIQUE%'"
        )).fetchall()
        for (idx_name,) in rows:
            conn.execute(text(f"DROP INDEX IF EXISTS {idx_name}"))
            logger.info(f"MIGRATION: dropped unique index {idx_name} on chart_specs")
        # Recreate a plain (non-unique) index on cache_key if absent.
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_chart_specs_cache_key ON chart_specs(cache_key)"
        ))
        # created_at indexes (Low fix) — create if missing.
        for tbl in ("chart_specs", "analyses", "workflows", "generation_runs"):
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS ix_{tbl}_created_at ON {tbl}(created_at)"
            ))
        conn.commit()
