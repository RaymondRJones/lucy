"""Database engine and session lifecycle."""

from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def create_db_and_tables() -> None:
    """Creates any missing tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Yields a database session for one request."""
    with Session(engine) as session:
        yield session
