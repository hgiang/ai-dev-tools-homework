import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repository import InMemoryCardRepository


@pytest.fixture
def repository() -> InMemoryCardRepository:
    """A fresh, empty store for every test — no cross-test leakage."""
    return InMemoryCardRepository()


@pytest.fixture
def client(repository: InMemoryCardRepository) -> TestClient:
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
