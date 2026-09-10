"""The board resource: fixed lanes, fixed order, cards ordered by position."""

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_empty_board_has_three_lanes_in_order(client: TestClient) -> None:
    board = client.get("/api/board").json()

    assert [lane["id"] for lane in board["lanes"]] == ["todo", "doing", "done"]
    assert [lane["name"] for lane in board["lanes"]] == [
        "To Do",
        "In Progress",
        "Done",
    ]
    assert all(lane["cards"] == [] for lane in board["lanes"])


def test_board_returns_cards_grouped_by_lane(client: TestClient, make_card) -> None:
    make_card(title="First", lane="todo")
    make_card(title="Second", lane="doing")
    make_card(title="Third", lane="todo")

    lanes = {lane["id"]: lane for lane in client.get("/api/board").json()["lanes"]}

    assert [c["title"] for c in lanes["todo"]["cards"]] == ["First", "Third"]
    assert [c["title"] for c in lanes["doing"]["cards"]] == ["Second"]
    assert lanes["done"]["cards"] == []


def test_board_positions_are_contiguous_from_zero(
    client: TestClient, make_card
) -> None:
    for index in range(4):
        make_card(title=f"Card {index}")

    lanes = {lane["id"]: lane for lane in client.get("/api/board").json()["lanes"]}

    assert [c["position"] for c in lanes["todo"]["cards"]] == [0, 1, 2, 3]
