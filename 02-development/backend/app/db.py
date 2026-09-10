"""Storage schema and engine wiring.

Deliberately database-agnostic: the column types here (String, Text, Date,
DateTime, JSON, Integer) are all portable, so pointing DATABASE_URL at
Postgres instead of SQLite needs no code change.
"""

from __future__ import annotations

import os
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./laneway.db"


class Base(DeclarativeBase):
    pass


class CardRow(Base):
    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # A JSON array rather than a join table: labels are free text owned by one
    # card, never queried across cards, so a second table would buy nothing.
    labels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lane: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


def create_db_engine(url: str | None = None) -> Engine:
    resolved = url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    connect_args = {}
    if make_url(resolved).get_backend_name() == "sqlite":
        # Uvicorn and TestClient hand requests to worker threads; SQLite's
        # default same-thread guard would reject those connections.
        connect_args["check_same_thread"] = False
    return create_engine(resolved, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_all(engine: Engine) -> None:
    Base.metadata.create_all(engine)
