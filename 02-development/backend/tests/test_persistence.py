"""What only a real database can be asked to prove.

The rest of the suite runs against both stores and checks behaviour. These
tests check durability: that the data is still there once the process that
wrote it is gone.
"""

from datetime import date, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import CardRow, create_all, create_db_engine, create_session_factory
from app.domain import LaneId
from app.main import create_app
from tests.conftest import sqlite_repository


def test_data_survives_a_new_repository_over_the_same_file(tmp_path: Path) -> None:
    db = tmp_path / "laneway.db"

    first = TestClient(create_app(repository=sqlite_repository(db)))
    created = first.post(
        "/api/cards",
        json={
            "title": "Outlives the process",
            "labels": ["backend", "database"],
            "due_date": "2026-10-01",
            "lane": "doing",
        },
    ).json()

    # A second app over the same file stands in for a server restart.
    second = TestClient(create_app(repository=sqlite_repository(db)))
    fetched = second.get(f"/api/cards/{created['id']}").json()

    assert fetched == created


def test_board_survives_a_restart_with_order_intact(tmp_path: Path) -> None:
    db = tmp_path / "laneway.db"
    first = TestClient(create_app(repository=sqlite_repository(db)))

    for title in ("A", "B", "C"):
        first.post("/api/cards", json={"title": title})
    moved = first.get("/api/board").json()["lanes"][0]["cards"][0]
    first.post(f"/api/cards/{moved['id']}/move", json={"lane": "todo", "position": 2})

    second = TestClient(create_app(repository=sqlite_repository(db)))
    lanes = {lane["id"]: lane for lane in second.get("/api/board").json()["lanes"]}

    assert [c["title"] for c in lanes["todo"]["cards"]] == ["B", "C", "A"]
    assert [c["position"] for c in lanes["todo"]["cards"]] == [0, 1, 2]


def test_columns_hold_the_expected_types(tmp_path: Path) -> None:
    """Guards the mapping itself: labels as a JSON list, dates as dates."""
    db = tmp_path / "laneway.db"
    client = TestClient(create_app(repository=sqlite_repository(db)))
    created = client.post(
        "/api/cards",
        json={
            "title": "Typed",
            "labels": ["one", "two"],
            "due_date": "2026-10-01",
            "lane": "done",
        },
    ).json()

    engine = create_db_engine(f"sqlite:///{db}")
    create_all(engine)
    with create_session_factory(engine)() as session:
        row = session.get(CardRow, created["id"])

    assert row is not None
    assert row.labels == ["one", "two"]
    assert row.due_date == date(2026, 10, 1)
    assert row.lane == LaneId.DONE.value
    assert row.position == 0


def test_timestamps_come_back_as_utc(tmp_path: Path) -> None:
    """SQLite drops the offset on write; the mapper must put UTC back."""
    repository = sqlite_repository(tmp_path / "laneway.db")
    client = TestClient(create_app(repository=repository))
    created = client.post("/api/cards", json={"title": "Timed"}).json()

    card = repository.get(created["id"])

    assert card.created_at.tzinfo is not None
    assert card.created_at.utcoffset() == timezone.utc.utcoffset(None)


def test_deleting_the_last_card_leaves_an_empty_board(tmp_path: Path) -> None:
    db = tmp_path / "laneway.db"
    client = TestClient(create_app(repository=sqlite_repository(db)))
    created = client.post("/api/cards", json={"title": "Only one"}).json()

    client.delete(f"/api/cards/{created['id']}")

    reopened = TestClient(create_app(repository=sqlite_repository(db)))
    board = reopened.get("/api/board").json()
    assert all(lane["cards"] == [] for lane in board["lanes"])
