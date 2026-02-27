from __future__ import annotations

from fastapi.testclient import TestClient


def test_logs_append_and_read(client: TestClient) -> None:
    job_id = client.post("/jobs", json={"command": "echo hi"}).json()["id"]
    assignment = client.get("/jobs/next", params={"node_id": "node-1"}).json()

    append_response = client.post(
        f"/jobs/{job_id}/logs",
        json={
            "node_id": "node-1",
            "lease_token": assignment["lease_token"],
            "text": "line 1\n",
        },
    )
    assert append_response.status_code == 200

    read_response = client.get(f"/jobs/{job_id}/logs")
    assert read_response.status_code == 200
    assert read_response.json()["text"] == "line 1\n"
