# Writing the Phase A Tests

This document walks you through writing the missing tests for Phase A (artifact upload).
The goal is that you type these yourself — don't copy-paste. The act of typing forces you
to read every line.

---

## The mental model before writing a single test

Ask yourself: **what does Phase A actually promise?**

Look at `coordinator/app.py` and `worker/agent.py` and trace the sequence:

1. Worker runs a job inside a temp dir
2. Worker sees files were created
3. Worker asks coordinator for a presigned URL (`POST /jobs/{id}/artifacts/presign`)
4. Coordinator returns `upload_url` and `download_url`
5. Worker PUTs the zip directly to S3 using `upload_url`
6. Worker tells coordinator the artifact exists (`POST /jobs/{id}/artifacts`)
7. Worker finishes the job (`POST /jobs/{id}/finish`)
8. Anyone can `GET /jobs/{id}` and see the artifact URL in `artifact_urls`

Steps 3, 4, 6, 7, and 8 are all coordinator logic. **None of them require a real S3 bucket.**
Step 5 touches real S3 — we'll handle that separately using a mock.

A test's job is to prove each of these promises holds. Start with the most important one:
**does the URL end up on the job?**

---

## Setup: create the test file

Create `tests/test_artifacts.py`. Start with this boilerplate — it's the same pattern
used in `test_scheduling.py` and `test_auth.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from deborgen.coordinator.app import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app(db_path=":memory:")
    return TestClient(app)
```

`db_path=":memory:"` gives each test a fresh, isolated database. Tests never share state.

---

## The helper fixture: a running job

Every artifact test needs a job that has been submitted and claimed (i.e., it's `running`
with an active lease). Rather than repeating that setup in every test, write it once as
a fixture.

Add this below your `client` fixture:

```python
@pytest.fixture
def running_job(client: TestClient) -> tuple[str, str]:
    """Submit a job and claim it. Returns (job_id, lease_token)."""
    client.post("/jobs", json={"command": "echo hello"})
    client.post("/nodes/node1/heartbeat", json={"labels": {}})
    resp = client.get("/jobs/next?node_id=node1")
    data = resp.json()
    return data["job"]["id"], data["lease_token"]
```

Notice it takes `client` as an argument — pytest injects it automatically. The fixture
returns a tuple: the job's string ID (like `"job_1"`) and the lease token the worker
would use to prove it owns the job.

---

## Test 1: The core promise — URL appears on the job

This is the most important test. It proves the full coordinator-side flow works:
record a URL, then read it back.

```python
def test_record_artifact_url_appears_on_job(client: TestClient, running_job: tuple[str, str]) -> None:
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
```

**Why `.raise_for_status()`?** If the POST fails for any reason (a bug, a missing field,
a 409), the test will error with a clear HTTP error rather than silently passing the
assert because `artifact_urls` is empty. Make your setup calls loud.

Run it now: `uv run pytest tests/test_artifacts.py -v`

If it passes, the basic write-then-read path works. If it fails, read the error before
continuing.

---

## Test 2: The URL survives `finish`

There's a subtle question: the `finish_job` route deletes the lease row. Does it
accidentally wipe `artifact_urls` too? Prove it doesn't.

```python
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
```

This test embodies "code proven to work" — it exercises the real sequence the worker
runs and checks both outcomes (status and artifacts) in one shot.

---

## Test 3: The wrong lease token is rejected

Security: a different node shouldn't be able to attach artifacts to a job it doesn't own.

```python
def test_record_artifact_rejects_wrong_lease_token(client: TestClient, running_job: tuple[str, str]) -> None:
    job_id, _ = running_job  # discard the real token

    resp = client.post(
        f"/jobs/{job_id}/artifacts",
        json={
            "node_id": "node1",
            "lease_token": "not-the-real-token",
            "url": "https://attacker.com/malicious.zip",
        },
    )
    assert resp.status_code == 409
```

The `_` is a Python convention: "I'm deliberately ignoring this value." It signals
intent to the reader.

---

## Test 4: Duplicate URLs are deduplicated

Look at `record_artifact` in `coordinator/app.py` — it has an explicit `if url not in
artifact_urls` check. Prove it works.

```python
def test_record_artifact_deduplicates_urls(client: TestClient, running_job: tuple[str, str]) -> None:
    job_id, lease_token = running_job
    url = "https://example.com/artifacts.zip"

    for _ in range(3):
        client.post(
            f"/jobs/{job_id}/artifacts",
            json={"node_id": "node1", "lease_token": lease_token, "url": url},
        ).raise_for_status()

    resp = client.get(f"/jobs/{job_id}")
    assert resp.json()["artifact_urls"].count(url) == 1
```

---

## Test 5: Presign fails gracefully when S3 is not configured

The presign endpoint reads S3 credentials from environment variables. If they're absent,
it should return 500 with a clear message — not crash with an unhandled exception.

```python
def test_presign_without_s3_config_returns_500(
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
```

`monkeypatch` is a pytest built-in. `raising=False` means "don't error if the variable
wasn't set in the first place."

---

## Test 6: Presign happy path — using a mock

This is the most advanced test. The presign endpoint creates a real `boto3.client` and
calls `generate_presigned_url`. We don't have a real S3 bucket, so we replace the boto3
client with a fake object that returns predictable values.

```python
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
```

**How the mock works:**
- `MagicMock()` creates an object that accepts any method call without crashing
- `.side_effect = [a, b]` means the first call returns `a`, the second returns `b`
- `patch("deborgen.coordinator.app.boto3.client", ...)` replaces `boto3.client` *as seen
  from inside `app.py`* for the duration of the `with` block

The `with patch(...)` ends before the `assert` lines — that's intentional. You want to
make assertions outside the mock context so that if the assertions fail, you're not
inside a patched environment.

**The import path matters.** You must patch `deborgen.coordinator.app.boto3.client`,
not `boto3.client`. The rule is: patch the name *where it is used*, not where it is
defined. Read that sentence twice — it's the most common mocking mistake.

---

## Running everything

```bash
uv run pytest tests/test_artifacts.py -v
```

You should see 6 passing tests. Then run the full suite to make sure you haven't broken
anything:

```bash
uv run pytest -v
```

---

## What you've proven

| Claim | Proven by |
|---|---|
| Record artifact → URL visible on job | Test 1 |
| URL persists after job finishes | Test 2 |
| Wrong token is rejected | Test 3 |
| Duplicate URLs don't accumulate | Test 4 |
| Missing S3 config fails gracefully | Test 5 |
| Presign returns correct URLs | Test 6 |

Phase A is now proven to work at the coordinator layer. The one thing not tested is the
worker-side zip-and-upload sequence — that requires either a real S3 bucket or a more
complex mock of `httpx.put`. Leave that for later.
