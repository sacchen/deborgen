# Deployment Notes (v0)

This guide covers the validated operational setup for the v0 coordinator and worker demo.

Related docs:

- [`quickstart.md`](../../quickstart.md)
- [`architecture.md`](../../architecture.md)
- [`api.md`](../../api.md)

Checked-in templates:

- [`ops/systemd/deborgen-coordinator.service`](../../ops/systemd/deborgen-coordinator.service)
- [`ops/env/coordinator.env.example`](../../ops/env/coordinator.env.example)

## Topology

- Coordinator runs on a remote Linux host.
- Worker and submitter can run from a laptop or another trusted machine.
- Connectivity is over Tailscale.

Use `http://<coordinator-tailscale-ip>:8000` as the coordinator URL in the examples below.

## Coordinator Service

Run the coordinator under `systemd` so it survives shell disconnects and reboots.

Service command:

```bash
uv run deborgen-coordinator
```

Use the checked-in service template at [`ops/systemd/deborgen-coordinator.service`](../../ops/systemd/deborgen-coordinator.service), then install it as `/etc/systemd/system/deborgen-coordinator.service`.

Use the checked-in env template at [`ops/env/coordinator.env.example`](../../ops/env/coordinator.env.example), then install it as `/etc/deborgen/coordinator.env`.

Before installing the service file, replace `User`, `WorkingDirectory`, and the `uv` path placeholders for the target host.

Environment keys:

```bash
DEBORGEN_DB_PATH=/home/dev/deborgen/deborgen.db
DEBORGEN_TOKEN=<real-random-token>
```

Useful commands:

```bash
sudo systemctl status deborgen-coordinator
sudo systemctl restart deborgen-coordinator
sudo journalctl -u deborgen-coordinator -f
sudo systemctl enable --now deborgen-coordinator
```

## Worker Startup

Start the worker with:

```bash
uv run deborgen-worker \
  --coordinator http://<coordinator-tailscale-ip>:8000 \
  --node-id node-1 \
  --work-dir /absolute/path/for/job-runs
```

The worker implementation lives in `deborgen.worker.agent`.

When the worker is healthy but idle, it may look like it is hanging. This is expected because it stays in its poll loop waiting for work.

The worker executes commands without a shell. Job commands must be valid executable invocations, not shell pipelines or compound shell expressions.

## Secrets

- Store the server token in `/etc/deborgen/coordinator.env`.
- Keep that file root-owned with mode `600`.
- Load the laptop token at runtime from macOS Keychain instead of shell startup files.

Example runtime load:

```bash
export DEBORGEN_TOKEN="$(security find-generic-password -a "$USER" -s deborgen_token -w)"
```

If API requests return `401` with `invalid auth token`, confirm that placeholder values have been replaced with the real shared token on both sides.

## Tailscale Access Model

Recommended split:

- Shared/older machines use `tag:shared`.
- Private/new coordinator hosts use `tag:private`.

ACL model:

- `group:me` -> `tag:private:*`
- `group:shared` -> `tag:shared:*`

Tailscale identity strings in ACL groups must exactly match the identities shown by Tailscale.

## SSH Hardening

Validated baseline:

- `PermitRootLogin no`
- `PasswordAuthentication no`
- `PubkeyAuthentication yes`

Keep both a primary admin account and a break-glass fallback account working before making further changes.

## Smoke Test

Health:

```bash
curl http://<coordinator-tailscale-ip>:8000/health
```

Submit:

```bash
curl -sS -H "Authorization: Bearer $DEBORGEN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"echo hello from worker"}' \
  http://<coordinator-tailscale-ip>:8000/jobs
```

Check:

```bash
curl -sS -H "Authorization: Bearer $DEBORGEN_TOKEN" \
  http://<coordinator-tailscale-ip>:8000/jobs/<job_id>
curl -sS -H "Authorization: Bearer $DEBORGEN_TOKEN" \
  http://<coordinator-tailscale-ip>:8000/jobs/<job_id>/logs
```

## Recovery Checklist

1. Keep both primary and fallback SSH keys tested.
2. Keep at least one active SSH session open while changing SSH or firewall settings.
3. If locked out, use your cloud provider's recovery flow to repair `authorized_keys` and `sshd_config`.
4. Take a snapshot after stable infrastructure changes.
