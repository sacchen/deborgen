from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from deborgen.coordinator.app import create_app


def make_client() -> TestClient:
    return TestClient(create_app(db_path=":memory:"))


@pytest.fixture
def client() -> TestClient:
    return make_client()
