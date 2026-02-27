from __future__ import annotations

from fastapi.testclient import TestClient


def test_job_lifecycle_success(client: TestClient) -> None:
    create_response = client.post("/jobs", json={"command": "python -c 'print(42)'", "max_attempts": 1})
    assert create_response.status_code == 201
    job_id = create_response.json()["id"]
    assert create_response.json()["status"] == "queued"

    claim_response = client.get("/jobs/next", params={"node_id": "node-1"})
    assert claim_response.status_code == 200
    payload = claim_response.json()
    assert payload["job"]["id"] == job_id
    assert payload["job"]["status"] == "running"
    lease_token = payload["lease_token"]

    finish_response = client.post(
        f"/jobs/{job_id}/finish",
        json={
            "node_id": "node-1",
            "lease_token": lease_token,
            "exit_code": 0,
            "failure_reason": None,
        },
    )
    assert finish_response.status_code == 200
    assert finish_response.json()["status"] == "succeeded"
    assert finish_response.json()["finished_at"] is not None

    get_response = client.get(f"/jobs/{job_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "succeeded"


def test_next_job_empty_returns_204(client: TestClient) -> None:
    response = client.get("/jobs/next", params={"node_id": "node-1"})
    assert response.status_code == 204
