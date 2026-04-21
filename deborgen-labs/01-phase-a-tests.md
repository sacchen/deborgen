# Lab 01: Phase A Tests

## Concept

Tests are how you prove code works. Not "I think it works" or "it worked when
I ran it manually" — proven, repeatable, automated.

Phase A (artifact upload) is the most complex feature in the codebase and has
zero test coverage. You're going to fix that.

The key insight for this lab: **the coordinator side of artifact upload requires
no real S3 bucket**. You can test everything except the actual PUT to cloud
storage using the same in-memory database and TestClient pattern already used
in `tests/test_scheduling.py`.

## Task

Create `tests/test_artifacts.py` and write tests that prove the following
behaviors work correctly.

Before you start, read `src/deborgen/coordinator/app.py` and find:
- `record_artifact` (the store method)
- `presign_artifact` (the route handler)
- `assert_job_lease`

Understand what each one does. Then write the tests.

## Acceptance criteria

Run `uv run pytest tests/test_artifacts.py -v` and all of these pass:

1. After calling `POST /jobs/{id}/artifacts` with a URL, `GET /jobs/{id}`
   returns that URL in `artifact_urls`.

2. The artifact URL is still present after the job is finished
   (`POST /jobs/{id}/finish`).

3. `POST /jobs/{id}/artifacts` with a wrong lease token returns `409`.

4. Calling `POST /jobs/{id}/artifacts` with the same URL three times results
   in that URL appearing exactly once in `artifact_urls`.

5. `POST /jobs/{id}/artifacts/presign` when S3 environment variables are not
   set returns `500` with a message containing `"not configured"`.

6. `POST /jobs/{id}/artifacts/presign` with S3 env vars set returns `200`
   with both `upload_url` and `download_url` fields.

## Hints

<details>
<summary>Hint 1: Setup pattern</summary>

Look at how `test_scheduling.py` sets up its `client` fixture and registers
a node before claiming a job. You'll need the same pattern: submit a job,
heartbeat a node, claim the job to get a lease token. Every artifact test
needs a running job with an active lease.

Consider writing a `running_job` fixture so you don't repeat this setup in
every test.
</details>

<details>
<summary>Hint 2: Environment variables in tests</summary>

pytest has a built-in `monkeypatch` fixture for setting and unsetting
environment variables without affecting other tests:

```python
def test_something(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://example.com")
    monkeypatch.delenv("SOME_VAR", raising=False)  # raising=False = don't error if not set
```
</details>

<details>
<summary>Hint 3: Mocking boto3 for the presign happy path</summary>

The presign endpoint calls `boto3.client(...)` and then
`generate_presigned_url(...)`. You can replace boto3.client with a fake for
the duration of one test using `unittest.mock.patch` and `MagicMock`.

The key rule: patch the name **where it is used**, not where it is defined.
boto3 is used inside `deborgen.coordinator.app`, so the patch target is
`"deborgen.coordinator.app.boto3.client"`.

```python
from unittest.mock import MagicMock, patch

mock_s3 = MagicMock()
mock_s3.generate_presigned_url.side_effect = ["url-one", "url-two"]

with patch("deborgen.coordinator.app.boto3.client", return_value=mock_s3):
    # make the request inside here
    ...
```

`side_effect` with a list means: first call returns `"url-one"`, second call
returns `"url-two"`.
</details>

<details>
<summary>Full walkthrough</summary>

If you're still stuck after trying, the full walkthrough with code is in
`docs/ops/writing-phase-a-tests.md`. Read it, understand it, then close it
and write the tests from memory.
</details>

## When you're done

Run the full test suite to make sure nothing is broken:

```bash
uv run pytest -v
```

Then move to Lab 02.
