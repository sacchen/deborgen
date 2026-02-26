# API (v0)

This document defines the minimal HTTP API contract for `deborgen` v0.

Goal: one end-to-end loop.

1. A submitter creates a job.
2. A worker polls for work.
3. The worker executes and reports outcome.
4. Logs and artifacts remain discoverable.

The coordinator is the source of truth for job state.

Related docs:

- [`quickstart.md`](./quickstart.md)
- [`architecture.md`](./architecture.md)

## Conventions

- JSON request/response bodies
- `Authorization: Bearer <token>` for authenticated endpoints
- ISO 8601 UTC timestamps
- Standard HTTP status codes

v0 may use a single shared token. Role-specific tokens can be added later.

## Resource Shapes

### Job

```json
{
  "id": "job_123",
  "status": "queued",
  "command": "uv run python examples/demo.py",
  "created_at": "2026-02-26T18:00:00Z",
  "started_at": null,
  "finished_at": null,
  "assigned_node_id": null,
  "timeout_seconds": 3600,
  "attempts": 0,
  "max_attempts": 1,
  "exit_code": null,
  "failure_reason": null,
  "artifact_urls": []
}
```

### Node

```json
{
  "node_id": "node_abc",
  "name": "bf-gaming-pc",
  "labels": {
    "gpu": "rtx3060",
    "cpu_cores": 12,
    "ram_gb": 32
  },
  "last_seen_at": "2026-02-26T18:05:00Z"
}
```

Node registration may be implicit on first heartbeat in v0.

## Endpoints

### Health

`GET /health`

Response `200`:

```json
{ "status": "ok" }
```

### Submit Job

`POST /jobs`

Creates a job in `queued`.

Request:

```json
{
  "command": "uv run python examples/demo.py",
  "timeout_seconds": 3600,
  "max_attempts": 1
}
```

`command` is required. Defaults:

- `timeout_seconds`: implementation-defined (for example `3600`)
- `max_attempts`: `1`

Response: `201` with job object.

### List Jobs

`GET /jobs?status=&limit=`

Query params:

- `status` (optional): `queued|running|succeeded|failed`
- `limit` (optional)

Response `200`:

```json
{ "jobs": [] }
```

### Get Job

`GET /jobs/{job_id}`

Response: `200` with job object, or `404`.

### Worker Heartbeat

`POST /nodes/{node_id}/heartbeat`

Used to track worker liveness and optional labels.

Request:

```json
{
  "name": "bf-gaming-pc",
  "labels": {
    "gpu": "rtx3060",
    "cpu_cores": 12,
    "ram_gb": 32
  }
}
```

Response: `200` with node object.

### Poll Next Job (Claim)

`GET /jobs/next?node_id=...`

Returns an exclusive assignment if available.

Response when available (`200`):

```json
{
  "job": {},
  "lease_token": "lease_opaque_string"
}
```

Response when empty: `204`.

Coordinator behavior:

- claim is exclusive
- assigned job moves to `running`
- coordinator stores `assigned_node_id`, `started_at`, and lease metadata

### Finish Job

`POST /jobs/{job_id}/finish`

Workers report terminal result.

Request:

```json
{
  "node_id": "node_abc",
  "lease_token": "lease_opaque_string",
  "exit_code": 0,
  "failure_reason": null
}
```

Result mapping:

- `exit_code == 0` -> `succeeded`
- nonzero `exit_code` -> `failed`

Coordinator rejects reports from non-owning workers (or invalid lease).

### Append Logs

`POST /jobs/{job_id}/logs`

Request:

```json
{
  "node_id": "node_abc",
  "lease_token": "lease_opaque_string",
  "text": "line 1\nline 2\n"
}
```

Response: `200`.

### Read Logs

`GET /jobs/{job_id}/logs`

Response can be inline text:

```json
{ "text": "..." }
```

Or a URL:

```json
{ "url": "https://..." }
```

### Artifacts

`POST /jobs/{job_id}/artifacts`

Upload artifact data (directly or via presigned URL flow). Coordinator must store artifact metadata.

`GET /jobs/{job_id}/artifacts`

Response `200`:

```json
{
  "artifacts": [
    { "name": "result.json", "url": "..." }
  ]
}
```

## Errors

Core v0 errors:

- `400` malformed request
- `401` missing/invalid token
- `404` unknown job or node
- `409` invalid ownership or state transition

## Minimal Required v0 Contract

Smallest complete cross-machine loop:

- `POST /jobs`
- `GET /jobs/next`
- `POST /jobs/{id}/finish`
- `GET /health`

Strongly recommended:

- `POST /jobs/{id}/logs`
