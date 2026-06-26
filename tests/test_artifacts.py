import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from deborgen.coordinator.app import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app(db_path=":memory:")
    return TestClient(app)


@pytest.fixture
def running_job(client: TestClient) -> tuple[str, str]:
    """Submit a job and claim it. Returns (job_id, lease_token)."""
    client.post("/jobs", json={"command": "echo hello"})
    client.post("/nodes/node1/heartbeat", json={"labels": {}})
    resp = client.get("/jobs/next?node_id=node1")
    data = resp.json()
    return data["job"]["id"], data["lease_token"]


def test_record_artifact_url_appears_on_job(
    client: TestClient, running_job: tuple[str, str]
) -> None:
    job_id, lease_token = running_job

    client.post(
        f"/jobs/{job_id}/artifacts",
        json={
            "node_id": "node1",
            "lease_token": lease_token,
            "url": "https://example.com/artifacts.zip",
        },
    ).raise_for_status()

    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    assert "https://example.com/artifacts.zip" in resp.json()["artifact_urls"]


def test_artifact_url_survives_finish(client: TestClient, running_job: tuple[str, str]) -> None:
    job_id, lease_token = running_job

    client.post(
        f"/jobs/{job_id}/artifacts",
        json={
            "node_id": "node1",
            "lease_token": lease_token,
            "url": "https://example.com/artifacts.zip",
        },
    ).raise_for_status()

    client.post(
        f"/jobs/{job_id}/finish",
        json={
            "node_id": "node1",
            "lease_token": lease_token,
            "exit_code": 0,
        },
    ).raise_for_status()

    resp = client.get(f"/jobs/{job_id}")
    assert resp.json()["status"] == "succeeded"
    assert "https://example.com/artifacts.zip" in resp.json()["artifact_urls"]


def test_record_artifact_rejects_wrong_lease_token(
    client: TestClient, running_job: tuple[str, str]
) -> None:
    job_id, _ = running_job  # discard lease token

    resp = client.post(
        f"/jobs/{job_id}/artifacts",
        json={
            "node_id": "node1",
            "lease_token": "not-the-real-token",
            "url": "https://attacker.com/malicious.zip",
        },
    )

    assert resp.status_code == 409


def test_record_artifact_deduplicates_urls(
    client: TestClient, running_job: tuple[str, str]
) -> None:
    job_id, lease_token = running_job
    url = "https://example.com/artifacts.zip"

    for _ in range(3):
        client.post(
            f"/jobs/{job_id}/artifacts",
            json={"node_id": "node1", "lease_token": lease_token, "url": url},
        ).raise_for_status()

    resp = client.get(f"/jobs/{job_id}")
    assert resp.json()["artifact_urls"].count(url) == 1


def test_presign_without_s3_confif_returns_500(
    client: TestClient, running_job: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id, lease_token = running_job

    # Make sure no S3 env vars are set
    for var in ("S3_ENDPOINT_URL", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_BUCKET_NAME"):
        monkeypatch.delenv(var, raising=False)

    resp = client.post(
        f"/jobs/{job_id}/artifacts/presign",
        json={"node_id": "node1", "lease_token": lease_token, "filename": "artifacts.zip"},
    )

    assert resp.status_code == 500
    assert "not configured" in resp.json()["detail"]


def test_presign_returns_upload_and_download_urls(
    client: TestClient, running_job: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id, lease_token = running_job

    monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.example.com")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "fake-key")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "fake-secret")
    monkeypatch.setenv("S3_BUCKET_NAME", "my-bucket")

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.side_effect = [
        "https://s3.example.com/upload-url",
        "https://s3.example.com/download-url",
    ]

    with patch("deborgen.coordinator.app.boto3.client", return_value=mock_s3):
        resp = client.post(
            f"/jobs/{job_id}/artifacts/presign",
            json={"node_id": "node1", "lease_token": lease_token, "filename": "artifacts.zip"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["upload_url"] == "https://s3.example.com/upload-url"
    assert data["download_url"] == "https://s3.example.com/download-url"
