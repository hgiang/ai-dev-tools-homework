"""Card CRUD and the validation rules from _docs/specs.md section 3."""

from fastapi.testclient import TestClient


# ---------- create ----------


def test_create_returns_201_with_defaults(client: TestClient) -> None:
    response = client.post("/api/cards", json={"title": "Ship it"})

    assert response.status_code == 201
    card = response.json()
    assert card["title"] == "Ship it"
    assert card["description"] == ""
    assert card["labels"] == []
    assert card["due_date"] is None
    assert card["lane"] == "todo"
    assert card["position"] == 0
    assert card["id"]
    assert card["created_at"] == card["updated_at"]


def test_create_accepts_every_field(client: TestClient) -> None:
    card = client.post(
        "/api/cards",
        json={
            "title": "Wire up the database",
            "description": "SQLAlchemy behind the repository interface.",
            "labels": ["backend", "database"],
            "due_date": "2026-10-01",
            "lane": "doing",
        },
    ).json()

    assert card["labels"] == ["backend", "database"]
    assert card["due_date"] == "2026-10-01"
    assert card["lane"] == "doing"


def test_create_appends_to_the_end_of_its_lane(client: TestClient, make_card) -> None:
    make_card(title="First")
    second = make_card(title="Second")

    assert second["position"] == 1


def test_create_trims_the_title(client: TestClient) -> None:
    card = client.post("/api/cards", json={"title": "  padded  "}).json()

    assert card["title"] == "padded"


def test_create_deduplicates_labels_case_insensitively(client: TestClient) -> None:
    card = client.post(
        "/api/cards",
        json={"title": "T", "labels": ["Backend", "backend", " BACKEND ", "api"]},
    ).json()

    assert card["labels"] == ["Backend", "api"]


def test_create_drops_blank_labels(client: TestClient) -> None:
    card = client.post(
        "/api/cards", json={"title": "T", "labels": ["real", "  ", ""]}
    ).json()

    assert card["labels"] == ["real"]


# ---------- create: validation ----------


def test_create_rejects_missing_title(client: TestClient) -> None:
    assert client.post("/api/cards", json={}).status_code == 422


def test_create_rejects_blank_title(client: TestClient) -> None:
    assert client.post("/api/cards", json={"title": "   "}).status_code == 422


def test_create_rejects_overlong_title(client: TestClient) -> None:
    response = client.post("/api/cards", json={"title": "x" * 201})

    assert response.status_code == 422


def test_create_rejects_overlong_description(client: TestClient) -> None:
    response = client.post(
        "/api/cards", json={"title": "T", "description": "x" * 2001}
    )

    assert response.status_code == 422


def test_create_rejects_too_many_labels(client: TestClient) -> None:
    response = client.post(
        "/api/cards", json={"title": "T", "labels": [f"l{i}" for i in range(11)]}
    )

    assert response.status_code == 422


def test_create_rejects_overlong_label(client: TestClient) -> None:
    response = client.post("/api/cards", json={"title": "T", "labels": ["x" * 31]})

    assert response.status_code == 422


def test_create_rejects_malformed_due_date(client: TestClient) -> None:
    response = client.post("/api/cards", json={"title": "T", "due_date": "01/10/2026"})

    assert response.status_code == 422


def test_create_rejects_unknown_lane(client: TestClient) -> None:
    response = client.post("/api/cards", json={"title": "T", "lane": "backlog"})

    assert response.status_code == 422


# ---------- read ----------


def test_get_card(client: TestClient, make_card) -> None:
    created = make_card(title="Readable")

    response = client.get(f"/api/cards/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_card_is_404(client: TestClient) -> None:
    assert client.get("/api/cards/nope").status_code == 404


# ---------- update ----------


def test_update_changes_only_the_fields_sent(client: TestClient, make_card) -> None:
    created = make_card(
        title="Before", description="keep me", labels=["keep"], due_date="2026-10-01"
    )

    updated = client.patch(
        f"/api/cards/{created['id']}", json={"title": "After"}
    ).json()

    assert updated["title"] == "After"
    assert updated["description"] == "keep me"
    assert updated["labels"] == ["keep"]
    assert updated["due_date"] == "2026-10-01"


def test_update_can_clear_the_due_date(client: TestClient, make_card) -> None:
    created = make_card(due_date="2026-10-01")

    updated = client.patch(
        f"/api/cards/{created['id']}", json={"due_date": None}
    ).json()

    assert updated["due_date"] is None


def test_update_bumps_updated_at(client: TestClient, make_card) -> None:
    created = make_card()

    updated = client.patch(
        f"/api/cards/{created['id']}", json={"description": "changed"}
    ).json()

    assert updated["updated_at"] >= created["updated_at"]
    assert updated["created_at"] == created["created_at"]


def test_update_leaves_lane_and_position_alone(client: TestClient, make_card) -> None:
    created = make_card(lane="doing")

    updated = client.patch(f"/api/cards/{created['id']}", json={"title": "X"}).json()

    assert updated["lane"] == "doing"
    assert updated["position"] == created["position"]


def test_update_rejects_blank_title(client: TestClient, make_card) -> None:
    created = make_card()

    response = client.patch(f"/api/cards/{created['id']}", json={"title": "  "})

    assert response.status_code == 422


def test_update_unknown_card_is_404(client: TestClient) -> None:
    assert client.patch("/api/cards/nope", json={"title": "X"}).status_code == 404


# ---------- delete ----------


def test_delete_returns_204_and_removes_the_card(
    client: TestClient, make_card
) -> None:
    created = make_card()

    assert client.delete(f"/api/cards/{created['id']}").status_code == 204
    assert client.get(f"/api/cards/{created['id']}").status_code == 404


def test_delete_closes_the_position_gap(client: TestClient, make_card) -> None:
    first = make_card(title="First")
    middle = make_card(title="Middle")
    last = make_card(title="Last")

    client.delete(f"/api/cards/{middle['id']}")

    lanes = {lane["id"]: lane for lane in client.get("/api/board").json()["lanes"]}
    positions = {c["id"]: c["position"] for c in lanes["todo"]["cards"]}
    assert positions == {first["id"]: 0, last["id"]: 1}


def test_delete_unknown_card_is_404(client: TestClient) -> None:
    assert client.delete("/api/cards/nope").status_code == 404
