"""Integration test for SPEC.md acceptance scenario 1.

Unlike test_agent_relay.py (which drives the ASGI app in-process with
TestClient), this test talks to a *running* Agent Relay over real HTTP and
whatever database that server is configured with.  The same file therefore
verifies the local dev server, the container from Q3, the Compose stack from
Q4, and the Kubernetes deployment from Q5 -- only RELAY_BASE_URL changes:

    uv run pytest test_integration.py -q
    RELAY_BASE_URL=http://127.0.0.1:8080 uv run pytest test_integration.py -q

It never drops or recreates tables: it registers fresh agents on every run so
it is safe against a database that holds data you care about.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

BASE_URL = os.getenv("RELAY_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ENROLLMENT_SECRET = os.getenv("RELAY_ENROLLMENT_SECRET")
TIMEOUT = httpx.Timeout(30.0)


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as http:
        try:
            ready = http.get("/ready")
        except httpx.HTTPError as exc:
            pytest.skip(f"No Agent Relay at {BASE_URL} ({exc}). Start the server first.")
        if ready.status_code != 200:
            pytest.skip(f"Agent Relay at {BASE_URL} is not ready: {ready.status_code} {ready.text}")
        yield http


def register(client: httpx.Client, name: str) -> tuple[str, dict[str, str]]:
    """Register a uniquely named agent; return its id and auth headers."""
    headers = {"X-Enrollment-Secret": ENROLLMENT_SECRET} if ENROLLMENT_SECRET else {}
    response = client.post("/api/v1/agents", json={"name": f"{name}-{uuid.uuid4().hex[:8]}"}, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    return body["agent_id"], {"Authorization": f"Bearer {body['token']}"}


def test_two_agents_exchange_a_task_and_its_result(client: httpx.Client) -> None:
    """SPEC.md scenario 1: one agent sends, the other claims and completes,
    and the sender reads the result."""
    _alice_id, alice = register(client, "alice")
    bob_id, bob = register(client, "uppercase")

    # 1. Alice sends a task to Bob.  It starts queued.
    payload = f"hello relay {uuid.uuid4().hex[:8]}"
    sent = client.post("/api/v1/tasks", headers=alice, json={"to": bob_id, "input": payload})
    assert sent.status_code == 201, sent.text
    task_id = sent.json()["task_id"]
    assert sent.json()["status"] == "queued"

    # 2. Bob's worker claims it.  The claim carries the input and a claim token
    #    distinct from Bob's agent token, and flips the task to processing.
    claimed = client.post(
        "/api/v1/tasks/claim",
        headers=bob,
        json={"worker_id": "pytest-worker", "wait_seconds": 5},
    )
    assert claimed.status_code == 200, claimed.text
    claim = claimed.json()
    assert claim["task_id"] == task_id
    assert claim["input"] == payload
    assert claim["attempt"] == 1
    assert client.get(f"/api/v1/tasks/{task_id}", headers=alice).json()["status"] == "processing"

    # 3. Bob does the work (the deterministic worker uppercases) and completes.
    completed = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers=bob,
        json={"claim_token": claim["claim_token"], "output": payload.upper()},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"

    # 4. The sender reads the result.  This is the homework's Q2 answer.
    final = client.get(f"/api/v1/tasks/{task_id}", headers=alice)
    assert final.status_code == 200, final.text
    assert final.json()["status"] == "completed"
    assert final.json()["output"] == payload.upper()

    # 5. The delivery history the dashboard renders is persisted, and never
    #    leaks the claim token.
    attempts = client.get(f"/api/v1/tasks/{task_id}/attempts", headers=alice).json()["items"]
    assert len(attempts) == 1
    assert attempts[0]["outcome"] == "completed"
    assert attempts[0]["attempt"] == 1
    assert attempts[0]["worker_id"] == "pytest-worker"
    assert "claim_token" not in attempts[0]
    assert "claim_token_hash" not in attempts[0]


def test_completion_is_idempotent_and_a_stale_token_is_rejected(client: httpx.Client) -> None:
    """Guards the at-least-once contract: a retried completion must not create
    a second result, and a wrong claim token must not be accepted."""
    _alice_id, alice = register(client, "alice")
    bob_id, bob = register(client, "uppercase")

    task_id = client.post(
        "/api/v1/tasks", headers=alice, json={"to": bob_id, "input": "retry me"}
    ).json()["task_id"]
    claim = client.post(
        "/api/v1/tasks/claim", headers=bob, json={"worker_id": "pytest-worker", "wait_seconds": 5}
    ).json()

    body = {"claim_token": claim["claim_token"], "output": "RETRY ME"}
    first = client.post(f"/api/v1/tasks/{task_id}/complete", headers=bob, json=body)
    assert first.status_code == 200, first.text

    # Replaying the exact terminal request (lost response) changes nothing.
    replay = client.post(f"/api/v1/tasks/{task_id}/complete", headers=bob, json=body)
    assert replay.status_code == 200
    assert replay.json() == first.json()

    # A different result on the same claim token is a conflict.
    conflict = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers=bob,
        json={"claim_token": claim["claim_token"], "output": "SOMETHING ELSE"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflicting_terminal"

    # An unknown claim token is never accepted.
    stale = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers=bob,
        json={"claim_token": "clm_not-a-real-token", "output": "RETRY ME"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_claim"

    assert client.get(f"/api/v1/tasks/{task_id}", headers=alice).json()["output"] == "RETRY ME"


def test_another_agent_cannot_read_or_claim_someone_elses_task(client: httpx.Client) -> None:
    """Scenario 9: task content must not leak to a third agent."""
    _alice_id, alice = register(client, "alice")
    bob_id, bob = register(client, "uppercase")
    _mallory_id, mallory = register(client, "mallory")

    task_id = client.post(
        "/api/v1/tasks", headers=alice, json={"to": bob_id, "input": "secret payload"}
    ).json()["task_id"]

    assert client.get(f"/api/v1/tasks/{task_id}", headers=mallory).status_code == 404
    # Mallory's own inbox is empty, so claiming returns 204 rather than Bob's task.
    assert client.post(
        "/api/v1/tasks/claim", headers=mallory, json={"worker_id": "thief", "wait_seconds": 0}
    ).status_code == 204
    assert client.get(f"/api/v1/tasks/{task_id}").status_code == 401

    # Bob can still claim it.
    assert client.post(
        "/api/v1/tasks/claim", headers=bob, json={"worker_id": "pytest-worker", "wait_seconds": 5}
    ).status_code == 200
