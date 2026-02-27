from __future__ import annotations

from fastapi.testclient import TestClient

from deborgen.coordinator.app import create_app


def _expired_lease_client() -> TestClient:
    return TestClient(create_app(db_path=":memory:", lease_duration_seconds=-1))


def test_expired_lease_rejects_finish() -> None:
    client = _expired_lease_client()
    job_id = client.post("/jobs", json={"command": "echo hi"}).json()["id"]
    assignment = client.get("/jobs/next", params={"node_id": "node-1"}).json()

    response = client.post(
        f"/jobs/{job_id}/finish",
        json={
            "node_id": "node-1",
            "lease_token": assignment["lease_token"],
            "exit_code": 0,
            "failure_reason": None,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "lease has expired"


def test_expired_lease_rejects_log_append() -> None:
    client = _expired_lease_client()
    job_id = client.post("/jobs", json={"command": "echo hi"}).json()["id"]
    assignment = client.get("/jobs/next", params={"node_id": "node-1"}).json()

    response = client.post(
        f"/jobs/{job_id}/logs",
        json={
            "node_id": "node-1",
            "lease_token": assignment["lease_token"],
            "text": "line 1\n",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "lease has expired"
