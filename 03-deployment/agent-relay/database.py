"""Database setup and durable Agent Relay models.

This module is the only place that knows which engine is in use.  The rest of
the application talks to the models through :mod:`storage`.

Two backends are supported and selected by ``RELAY_DATABASE_URL``:

* **SQLite** (the starter default) has no row-level locking, so writers are
  serialized with a ``BEGIN IMMEDIATE`` reservation.
* **PostgreSQL** locks individual rows instead.  Claims and lease recovery use
  ``SELECT ... FOR UPDATE SKIP LOCKED``, so concurrent API replicas each take a
  different task rather than queueing behind one writer lock.

SQLAlchemy's SQLite dialect silently drops ``FOR UPDATE SKIP LOCKED`` from
compiled statements, so the storage layer states the locking intent once and
both backends stay correct.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    select,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

LOGGER = logging.getLogger("agent_relay.database")


def _database_url() -> str:
    return os.getenv("RELAY_DATABASE_URL") or os.getenv("DATABASE_URL") or "sqlite:///./agent-relay.db"


def positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


DATABASE_URL = _database_url()
LEASE_SECONDS = positive_int("RELAY_LEASE_SECONDS", 60)
MAX_ATTEMPTS = positive_int("RELAY_MAX_ATTEMPTS", 5)
RECOVERY_INTERVAL_SECONDS = max(1, positive_int("RELAY_RECOVERY_INTERVAL_SECONDS", 5))
MAX_BODY_BYTES = positive_int("RELAY_MAX_BODY_BYTES", 256 * 1024)
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

# Under Compose and Kubernetes the API container can start before PostgreSQL
# accepts connections.  Retrying at startup is cheaper than crash-looping.
DB_CONNECT_ATTEMPTS = positive_int("RELAY_DB_CONNECT_ATTEMPTS", 30)
DB_CONNECT_INTERVAL_SECONDS = positive_int("RELAY_DB_CONNECT_INTERVAL_SECONDS", 2)

# Arbitrary but fixed: every replica takes this advisory lock before running
# create_all, so concurrent pods cannot race to create the same tables.
SCHEMA_LOCK_KEY = 8_151_972


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_db_time(value: datetime) -> datetime:
    """Store naive UTC.

    Both backends use a timezone-naive ``DateTime`` column, so the application
    normalizes to UTC on the way in and re-attaches UTC in :func:`db_time` on
    the way out.  Keeping this uniform means SQLite and PostgreSQL rows compare
    and sort identically.
    """

    return value.astimezone(timezone.utc).replace(tzinfo=None)


def db_time(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso_time(value: datetime | None) -> str | None:
    value = db_time(value)
    if value is None:
        return None
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sent_tasks: Mapped[list[Task]] = relationship(
        "Task", foreign_keys="Task.sender_id", back_populates="sender", passive_deletes=True
    )
    received_tasks: Mapped[list[Task]] = relationship(
        "Task", foreign_keys="Task.recipient_id", back_populates="recipient", passive_deletes=True
    )


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("sender_id", "idempotency_key", name="uq_task_sender_idempotency"),)

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    sender_id: Mapped[str] = mapped_column(String(100), ForeignKey("agents.id"), nullable=False, index=True)
    recipient_id: Mapped[str] = mapped_column(String(100), ForeignKey("agents.id"), nullable=False, index=True)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sender: Mapped[Agent] = relationship("Agent", foreign_keys=[sender_id], back_populates="sent_tasks")
    recipient: Mapped[Agent] = relationship("Agent", foreign_keys=[recipient_id], back_populates="received_tasks")
    attempts: Mapped[list[Attempt]] = relationship(
        "Attempt", back_populates="task", cascade="all, delete-orphan", order_by="Attempt.attempt_number"
    )


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("task_id", "attempt_number", name="uq_attempt_task_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    claim_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    terminal_action: Mapped[str | None] = mapped_column(String(10), nullable=True)
    terminal_payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    task: Mapped[Task] = relationship("Task", back_populates="attempts")


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _is_postgres(url: str) -> bool:
    return url.startswith("postgresql") or url.startswith("postgres://")


def normalize_database_url(url: str) -> str:
    """Accept the URL shapes operators actually write.

    ``postgres://`` is what many hosted providers hand out, and a bare
    ``postgresql://`` leaves the driver to SQLAlchemy's default (psycopg2,
    which is not installed).  Both are rewritten to the psycopg 3 driver this
    project depends on.
    """

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


DATABASE_URL = normalize_database_url(DATABASE_URL)
IS_POSTGRES = _is_postgres(DATABASE_URL)
IS_SQLITE = _is_sqlite(DATABASE_URL)


engine_kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
if IS_SQLITE:
    engine_kwargs.update({"connect_args": {"check_same_thread": False, "timeout": 30}})
    if DATABASE_URL in {"sqlite://", "sqlite:///:memory:"}:
        from sqlalchemy.pool import StaticPool

        engine_kwargs["poolclass"] = StaticPool
elif IS_POSTGRES:
    engine_kwargs.update(
        {
            "pool_size": positive_int("RELAY_DB_POOL_SIZE", 5),
            "max_overflow": positive_int("RELAY_DB_MAX_OVERFLOW", 10),
            # Recycle below any proxy/idle timeout so a pooled connection is
            # never handed out after the server has dropped it.
            "pool_recycle": positive_int("RELAY_DB_POOL_RECYCLE", 1800),
        }
    )

engine: Engine = create_engine(DATABASE_URL, **engine_kwargs)

if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False, autoflush=True)


def wait_for_database() -> None:
    """Block until the server answers, or give up after the configured budget.

    Only meaningful for PostgreSQL: a SQLite file is always immediately
    available, while a database container is often still initializing when the
    API container starts.
    """

    if not IS_POSTGRES:
        return
    last_error: Exception | None = None
    for attempt in range(1, DB_CONNECT_ATTEMPTS + 1):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except OperationalError as exc:
            last_error = exc
            LOGGER.warning(
                "database not reachable yet (attempt %d/%d), retrying in %ds",
                attempt,
                DB_CONNECT_ATTEMPTS,
                DB_CONNECT_INTERVAL_SECONDS,
            )
            time.sleep(DB_CONNECT_INTERVAL_SECONDS)
    raise RuntimeError(f"database at {engine.url.render_as_string(hide_password=True)} never became reachable") from last_error


def init_db() -> None:
    """Create the schema, safely even when several replicas start at once."""

    if not IS_POSTGRES:
        Base.metadata.create_all(engine)
        return

    wait_for_database()
    with engine.begin() as connection:
        # Serialize schema creation across pods.  Without this, two replicas
        # can both find a table missing and race to CREATE it; one then fails
        # with DuplicateTable and crash-loops.  The lock is transaction-scoped
        # and released on commit.
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": SCHEMA_LOCK_KEY})
        Base.metadata.create_all(connection)


@contextmanager
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def immediate_transaction() -> Generator[Session, None, None]:
    """Open one writer transaction before selecting or changing work.

    The guarantee callers rely on is that reading a task and changing it happen
    atomically, so a task never gets two active leases.  How that is achieved
    differs by backend:

    * **SQLite** has no row locks, so ``BEGIN IMMEDIATE`` reserves the single
      writer slot for the whole transaction.  Concurrent claims serialize.
    * **PostgreSQL** starts an ordinary READ COMMITTED transaction.  Atomicity
      comes from the row locks that :mod:`storage` requests with
      ``FOR UPDATE SKIP LOCKED``, which is strictly better here: two API
      replicas claiming at the same moment take *different* rows concurrently
      instead of one waiting for the other.
    """

    connection = engine.connect()
    session = Session(bind=connection, expire_on_commit=False, autoflush=True)
    try:
        if IS_SQLITE:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        yield session
        session.flush()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        session.close()
        connection.close()


def recover_expired_in_session(db: Session, now: datetime) -> int:
    """Expire active leases and requeue/fail their tasks within ``db``."""

    now_db = as_db_time(now)
    expired = list(
        db.scalars(
            select(Attempt)
            .where(Attempt.outcome == "processing", Attempt.lease_expires_at <= now_db)
            .order_by(Attempt.lease_expires_at, Attempt.id)
            # On PostgreSQL every API replica runs its own recovery loop.  Lock
            # the attempts this pass will change and skip the ones another pass
            # already holds, so the loops divide the work instead of colliding.
            # Compiled away on SQLite, where BEGIN IMMEDIATE already serializes.
            .with_for_update(skip_locked=True)
        )
    )
    count = 0
    for attempt in expired:
        # skip_locked again, rather than blocking: if another transaction holds
        # this task it is already handling it, and waiting here while holding
        # attempt locks is how deadlocks start.
        task = db.get(Task, attempt.task_id, with_for_update={"skip_locked": True})
        if task is None or attempt.outcome != "processing":
            continue
        attempt.outcome = "expired"
        attempt.finished_at = now_db
        if task.status == "processing":
            if task.attempt_count >= MAX_ATTEMPTS:
                task.status = "failed"
                task.error = "attempts_exhausted"
                task.output = None
                task.finished_at = now_db
            else:
                task.status = "queued"
                task.finished_at = None
        count += 1
    return count


def recover_expired() -> int:
    """Run one recovery pass and return the number of expired attempts."""

    with immediate_transaction() as db:
        return recover_expired_in_session(db, utcnow())


__all__ = [
    "Agent",
    "Attempt",
    "Base",
    "DATABASE_URL",
    "IS_POSTGRES",
    "IS_SQLITE",
    "normalize_database_url",
    "wait_for_database",
    "DEFAULT_PAGE_SIZE",
    "LEASE_SECONDS",
    "MAX_ATTEMPTS",
    "MAX_BODY_BYTES",
    "MAX_PAGE_SIZE",
    "RECOVERY_INTERVAL_SECONDS",
    "Task",
    "as_db_time",
    "db_session",
    "db_time",
    "engine",
    "immediate_transaction",
    "init_db",
    "iso_time",
    "recover_expired",
    "recover_expired_in_session",
    "utcnow",
]
