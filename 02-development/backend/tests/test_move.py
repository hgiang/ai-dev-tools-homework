"""Moving a card: reorder within a lane, cross lanes, clamp, renormalize."""

from fastapi.testclient import TestClient


def titles(client: TestClient, lane: str) -> list[str]:
    board = client.get("/api/board").json()
    found = next(item for item in board["lanes"] if item["id"] == lane)
    return [card["title"] for card in found["cards"]]


def positions(client: TestClient, lane: str) -> list[int]:
    board = client.get("/api/board").json()
    found = next(item for item in board["lanes"] if item["id"] == lane)
    return [card["position"] for card in found["cards"]]


def test_move_to_another_lane(client: TestClient, make_card) -> None:
    card = make_card(title="Travelling")

    moved = client.post(
        f"/api/cards/{card['id']}/move", json={"lane": "doing", "position": 0}
    ).json()

    assert moved["lane"] == "doing"
    assert moved["position"] == 0
    assert titles(client, "todo") == []
    assert titles(client, "doing") == ["Travelling"]


def test_move_down_within_a_lane(client: TestClient, make_card) -> None:
    first = make_card(title="A")
    make_card(title="B")
    make_card(title="C")

    client.post(f"/api/cards/{first['id']}/move", json={"lane": "todo", "position": 2})

    assert titles(client, "todo") == ["B", "C", "A"]
    assert positions(client, "todo") == [0, 1, 2]


def test_move_up_within_a_lane(client: TestClient, make_card) -> None:
    make_card(title="A")
    make_card(title="B")
    last = make_card(title="C")

    client.post(f"/api/cards/{last['id']}/move", json={"lane": "todo", "position": 0})

    assert titles(client, "todo") == ["C", "A", "B"]


def test_move_inserts_between_existing_cards(client: TestClient, make_card) -> None:
    make_card(title="A", lane="doing")
    make_card(title="B", lane="doing")
    incoming = make_card(title="X", lane="todo")

    client.post(
        f"/api/cards/{incoming['id']}/move", json={"lane": "doing", "position": 1}
    )

    assert titles(client, "doing") == ["A", "X", "B"]


def test_move_renormalizes_the_source_lane(client: TestClient, make_card) -> None:
    make_card(title="A")
    middle = make_card(title="B")
    make_card(title="C")

    client.post(f"/api/cards/{middle['id']}/move", json={"lane": "done", "position": 0})

    assert titles(client, "todo") == ["A", "C"]
    assert positions(client, "todo") == [0, 1]


def test_move_clamps_a_position_past_the_end(client: TestClient, make_card) -> None:
    make_card(title="A", lane="doing")
    card = make_card(title="B", lane="todo")

    moved = client.post(
        f"/api/cards/{card['id']}/move", json={"lane": "doing", "position": 99}
    ).json()

    assert moved["position"] == 1
    assert titles(client, "doing") == ["A", "B"]


def test_move_to_the_same_place_is_a_no_op(client: TestClient, make_card) -> None:
    make_card(title="A")
    card = make_card(title="B")

    moved = client.post(
        f"/api/cards/{card['id']}/move", json={"lane": "todo", "position": 1}
    ).json()

    assert moved["position"] == 1
    assert titles(client, "todo") == ["A", "B"]


def test_move_rejects_a_negative_position(client: TestClient, make_card) -> None:
    card = make_card()

    response = client.post(
        f"/api/cards/{card['id']}/move", json={"lane": "todo", "position": -1}
    )

    assert response.status_code == 422


def test_move_rejects_an_unknown_lane(client: TestClient, make_card) -> None:
    card = make_card()

    response = client.post(
        f"/api/cards/{card['id']}/move", json={"lane": "archive", "position": 0}
    )

    assert response.status_code == 422


def test_move_unknown_card_is_404(client: TestClient) -> None:
    response = client.post("/api/cards/nope/move", json={"lane": "done", "position": 0})

    assert response.status_code == 404
