# Quickstart (v0)

This guide covers the minimal setup to run one remote job:

submit job -> worker runs it -> logs are recorded -> job completes.

This quickstart follows the v0 contract in [`api.md`](./api.md). It is contract-first: depending on current implementation status, some endpoints may still be in progress.

Related docs:

- [`architecture.md`](./architecture.md)
- [`api.md`](./api.md)
- [`docs/ops/deployment.md`](./docs/ops/deployment.md)

## Prerequisites

On coordinator and worker machines:

- Python 3.11+
- `uv` installed
- Tailscale installed and connected

On the coordinator host:

- repository cloned
- dependencies installed with `uv sync`

Set a token for authenticated API calls:

```bash
export DEBORGEN_TOKEN="<shared-token>"
```

For persistent deployments, prefer storing the coordinator token in a root-owned environment file and loading the client-side token at runtime instead of hard-coding it in shell startup files. See [`docs/ops/deployment.md`](./docs/ops/deployment.md).

## 1. Start Coordinator

From project root:

```bash
uv sync
uv run deborgen-coordinator
```

Health check:

```bash
curl http://<coordinator-tailscale-ip>:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## 2. Start Worker

On a second machine:

```bash
uv sync
uv run deborgen-worker --coordinator http://<coordinator-tailscale-ip>:8000 --node-id node-1
```

Worker behavior: heartbeat and polling for available jobs.

Important: the worker implementation lives in `deborgen.worker.agent`, not `deborgen.worker`.

If the worker appears idle after startup, that is usually expected. It stays in a poll loop until jobs are available.

## 3. Submit Job

From any machine that can reach the coordinator:

```bash
curl -X POST http://<coordinator-tailscale-ip>:8000/jobs \
  -H "Authorization: Bearer $DEBORGEN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"uv run python examples/demo.py"}'
```

Expected flow: job enters `queued`, then a worker claims and runs it.

## 4. Check Status

List jobs:

```bash
curl http://<coordinator-tailscale-ip>:8000/jobs \
  -H "Authorization: Bearer $DEBORGEN_TOKEN"
```

Get one job:

```bash
curl http://<coordinator-tailscale-ip>:8000/jobs/<job_id> \
  -H "Authorization: Bearer $DEBORGEN_TOKEN"
```

Completed success state:

```json
{"status":"succeeded"}
```

## 5. Read Logs

```bash
curl http://<coordinator-tailscale-ip>:8000/jobs/<job_id>/logs \
  -H "Authorization: Bearer $DEBORGEN_TOKEN"
```

## What This Demonstrates

- pull-based worker execution
- centralized coordinator state
- basic audit trail via status and logs

## Next Steps

- add persistent storage
- add containerized execution
- add lease heartbeats and expiry handling
- add conservative infra retry policy

For the validated `systemd` deployment shape, secret handling, SSH hardening, and recovery checklist, use [`docs/ops/deployment.md`](./docs/ops/deployment.md).
