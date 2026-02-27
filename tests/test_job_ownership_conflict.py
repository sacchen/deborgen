from __future__ import annotations

from fastapi.testclient import TestClient


def test_only_claiming_worker_can_finish_job(client: TestClient) -> None:
    create_response = client.post("/jobs", json={"command": "echo hi"})
    job_id = create_response.json()["id"]
    assignment = client.get("/jobs/next", params={"node_id": "node-1"}).json()

    conflict_response = client.post(
        f"/jobs/{job_id}/finish",
        json={
            "node_id": "node-2",
            "lease_token": assignment["lease_token"],
            "exit_code": 0,
            "failure_reason": None,
        },
    )

    assert conflict_response.status_code == 409
    assert "different worker" in conflict_response.json()["detail"]
