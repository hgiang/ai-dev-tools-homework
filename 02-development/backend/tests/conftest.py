from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import create_all, create_db_engine, create_session_factory
from app.main import create_app
from app.repository import CardRepository, InMemoryCardRepository
from app.sql_repository import SqlCardRepository


def sqlite_repository(path: Path) -> SqlCardRepository:
    """A repository over a real SQLite file, tables created."""
    engine = create_db_engine(f"sqlite:///{path}")
    create_all(engine)
    return SqlCardRepository(create_session_factory(engine))


@pytest.fixture(params=["memory", "sqlite"])
def repository(request: pytest.FixtureRequest, tmp_path: Path) -> CardRepository:
    """Every test in the suite runs against both implementations.

    The API must not be able to tell them apart — that is what makes the store
    swappable, and it is cheaper to enforce here than to duplicate the suite.
    """
    if request.param == "memory":
        return InMemoryCardRepository()
    return sqlite_repository(tmp_path / "test.db")


@pytest.fixture
def client(repository: CardRepository) -> TestClient:
    return TestClient(create_app(repository=repository))


@pytest.fixture
def make_card(client: TestClient):
    """Creates a card through the API and returns its body."""

    def _make(**overrides) -> dict:
        payload = {"title": "A card"} | overrides
        response = client.post("/api/cards", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _make
