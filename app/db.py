from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

SQLITE = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if SQLITE else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


if SQLITE:
    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def begin_immediate(db) -> None:
    if SQLITE:
        db.execute(text("BEGIN IMMEDIATE"))


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(engine)


def ensure_column(table_name: str, column_name: str, column_type: str, default_sql: str) -> bool:
    """Add a column to an existing table created before the setting existed.

    Identifiers are supplied by our own code (never by a request), so this is
    safe to build as a statement.  Values are bound as SQL literals defined in
    ``configs.py``.
    """
    existing = {column["name"] for column in inspect(engine).get_columns(table_name)}
    if column_name in existing:
        return False
    with engine.begin() as connection:
        connection.execute(
            text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default_sql}")
        )
    return True
