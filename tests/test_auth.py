from __future__ import annotations

from fastapi.testclient import TestClient

from deborgen.coordinator.app import create_app


def test_auth_not_required_when_token_not_set(monkeypatch) -> None:
    monkeypatch.delenv("DEBORGEN_TOKEN", raising=False)
    client = TestClient(create_app(db_path=":memory:"))
    response = client.post("/jobs", json={"command": "echo hi"})
    assert response.status_code == 201


def test_auth_required_when_token_is_set(monkeypatch) -> None:
    monkeypatch.setenv("DEBORGEN_TOKEN", "secret-token")
    client = TestClient(create_app(db_path=":memory:"))

    unauthorized = client.post("/jobs", json={"command": "echo hi"})
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/jobs",
        headers={"Authorization": "Bearer secret-token"},
        json={"command": "echo hi"},
    )
    assert authorized.status_code == 201
