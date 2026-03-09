import pytest
from fastapi.testclient import TestClient

from deborgen.coordinator.app import create_app

@pytest.fixture
def client() -> TestClient:
    app = create_app(db_path=":memory:")
    return TestClient(app)

def test_job_routing_requires_matching_labels(client: TestClient) -> None:
    # Submit job with GPU requirement
    client.post("/jobs", json={
        "command": "echo gpu_work",
        "requirements": {"gpu": "rtx3060"}
    })

    # Node without GPU polls -> Should get 204 No Content
    client.post("/nodes/node_cpu/heartbeat", json={"labels": {"os": "linux"}})
    resp = client.get("/jobs/next?node_id=node_cpu")
    assert resp.status_code == 204

    # Node with WRONG GPU polls -> Should get 204 No Content
    client.post("/nodes/node_wrong_gpu/heartbeat", json={"labels": {"gpu": "gtx1080"}})
    resp = client.get("/jobs/next?node_id=node_wrong_gpu")
    assert resp.status_code == 204

    # Node with CORRECT GPU polls -> Should get 200 OK and claim the job
    client.post("/nodes/node_right_gpu/heartbeat", json={"labels": {"os": "linux", "gpu": "rtx3060"}})
    resp = client.get("/jobs/next?node_id=node_right_gpu")
    assert resp.status_code == 200
    assert resp.json()["job"]["command"] == "echo gpu_work"

def test_job_routing_without_requirements_matches_any(client: TestClient) -> None:
    client.post("/jobs", json={"command": "echo basic_work"})

    # Any node should be able to claim it
    client.post("/nodes/node_any/heartbeat", json={"labels": {"os": "linux"}})
    resp = client.get("/jobs/next?node_id=node_any")
    assert resp.status_code == 200
    assert resp.json()["job"]["command"] == "echo basic_work"
