import os
from collections.abc import Generator

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def _connect_args(database_url: str) -> dict[str, bool]:
    return {"check_same_thread": False} if database_url.startswith("sqlite") else {}


DATABASE_URL = os.getenv("COMPONENT_DB_URL", "sqlite:///component_inventory.db")
engine = create_engine(DATABASE_URL, connect_args=_connect_args(DATABASE_URL))
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

METADATA_COLUMNS = {
    "components": {
        "secondary_category": "VARCHAR(160) NOT NULL DEFAULT ''",
        "description": "TEXT NOT NULL DEFAULT ''",
    },
    "bom_items": {
        "secondary_category": "VARCHAR(160) NOT NULL DEFAULT ''",
        "description": "TEXT NOT NULL DEFAULT ''",
    },
}


def configure_database(database_url: str) -> None:
    """Replace the process-wide database binding before the app starts."""
    global engine, SessionLocal
    engine = create_engine(database_url, connect_args=_connect_args(database_url))
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def ensure_metadata_columns(target_engine: Engine) -> None:
    if target_engine.dialect.name != "sqlite":
        return
    with target_engine.begin() as connection:
        inspector = inspect(connection)
        existing_tables = set(inspector.get_table_names())
        for table_name, columns in METADATA_COLUMNS.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {
                value["name"] for value in inspector.get_columns(table_name)
            }
            for column_name, definition in columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
                    ))


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(engine)
    ensure_metadata_columns(engine)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
