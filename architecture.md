# Architecture

`deborgen` is a cooperative distributed compute system for small, trusted groups. It pools personal machines into a shared job execution pool using a coordinator-worker architecture.

The system targets embarrassingly parallel workloads such as simulations, optimization sweeps, and parameter searches where jobs can run independently on separate machines.

The core design choice is a pull-based model. A central coordinator maintains global state, while workers initiate job execution by polling for work. This avoids long-lived connections, tolerates machines that go offline, and fits the reality of personal devices that are not always available.

Related docs:

- [`quickstart.md`](./quickstart.md)
- [`api.md`](./api.md)

## Coordinator

The coordinator is the control plane. It runs on a small always-on host, such as a cloud droplet, and maintains the authoritative state of the system.

Coordinator responsibilities:

- accept job submissions
- store job definitions
- track job lifecycle state
- record execution metadata
- expose APIs for workers and submitters

The coordinator does not run heavy computation and should remain lightweight.

## Workers

Workers are voluntary participant machines such as gaming PCs, laptops, or workstations. Each worker connects to the coordinator over a secure overlay network and periodically polls for eligible jobs.

When a worker receives a job, it executes it in an isolated environment, captures logs, uploads artifacts, and reports completion back to the coordinator.

Workers may join and leave at any time and retain full control over their machines.

## Networking

`deborgen` assumes workers and coordinator communicate over a private overlay network, such as Tailscale.

The architecture does not require worker-to-worker communication and does not require exposing public ports on residential networks.

The system assumes intermittent connectivity and heterogeneous bandwidth. A worker can disappear without breaking the system as a whole.

## Jobs

Jobs are declarative and immutable once submitted. A job specifies what to run and the constraints needed to run it, including:

- command
- optional environment variables
- optional container image reference
- timeout

The coordinator assigns jobs to workers indirectly through the pull mechanism. The system records which worker executed each job, when it ran, and how it exited.

The v0 job model is intentionally simple to keep the system understandable and preserve room for later scheduling experimentation.

## Isolation and Resource Limits

Jobs execute in isolation to avoid contaminating worker machines and to keep runs reproducible. In practice, this means running jobs in containers or constrained subprocess environments with dedicated working directories.

Jobs are time-bounded and should be resource-limited to prevent runaway execution. These limits are enforced locally by the worker, and the coordinator treats the worker as responsible for safe execution within agreed norms.

## Logs, Artifacts, and Auditability

`deborgen` prioritizes transparency because it is a cooperative system. The coordinator maintains an audit trail for each job, including:

- submitter identity
- execution node
- timestamps
- exit status
- logs
- artifact metadata

Logs and artifacts may be stored on the coordinator or in external object storage, but the coordinator remains the authoritative source of metadata.

The intent is that participants can see what ran and where without relying on informal trust alone.

## Failure Handling

The architecture assumes workers can disconnect mid-run, machines can reboot, and networks can drop.

The coordinator is the source of truth and can mark jobs failed when workers stop reporting progress.

The system favors recoverability and clear state transitions over strong distributed consistency. v0 focuses on correct behavior in the common case, with minimal mechanisms for detecting and handling likely failures.

## Trust Boundaries

`deborgen` is designed for trusted groups and is not adversarially hardened. It does not attempt to defend against malicious participants or sophisticated attacks.

Instead, it relies on opt-in participation, isolation, resource limits, and auditability to support cooperative governance.

Any future hardening should be evaluated against the project goal of staying lightweight and human-scale.

## Non-goals

`deborgen` intentionally avoids becoming a general-purpose orchestrator. It does not implement:

- distributed consensus
- peer-to-peer worker coordination
- tightly coupled HPC
- high-availability production guarantees

The architecture stays small and comprehensible so it can be used, modified, and reasoned about by a small group.

## Recommended v0 State Model

A job state is one of:

- `queued`
- `running`
- `succeeded`
- `failed`

A job starts in `queued` and ends in either `succeeded` or `failed`.

The coordinator is the source of truth for job state. Workers do not directly edit queue state; they request a lease and report outcomes.

### Allowed Transitions

Only these transitions are valid in v0:

- `queued` -> `running`
- `running` -> `succeeded`
- `running` -> `failed`

There are no other transitions in v0.

### Who Triggers Transitions

`queued` -> `running`:
- Trigger: worker claim accepted by coordinator
- Owner: coordinator writes state transition
- Required metadata: `worker_id`, `started_at`, `lease_expires_at`

`running` -> `succeeded`:
- Trigger: worker reports completion with exit code `0` before timeout
- Owner: coordinator validates report and writes final state

`running` -> `failed`:
- Trigger: worker reports nonzero exit, timeout is exceeded, or lease expires without heartbeat
- Owner: coordinator writes final state

### Simplified Lease Concept (v0)

Claims should be exclusive to avoid duplicate execution.

When a worker claims a job, the coordinator creates a lease by storing:

- `worker_id`
- `lease_expires_at`

While leased, the job is not eligible for other workers.

Workers send periodic heartbeats while running. Each heartbeat extends `lease_expires_at`. If heartbeats stop and the lease expires, the coordinator treats the run as lost and resolves the job according to retry policy.

For early v0, heartbeats can be minimal. A simple model is acceptable as long as ownership and lease expiry rules remain explicit.

### Retry Semantics (v0)

Retries should be conservative.

- Each job has `max_attempts` (default `1`)
- Each execution increments `attempts`
- Program failures (nonzero exit) transition to `failed` with no automatic retry in v0
- Infrastructure failures (worker unreachable, lease expired) may retry if `attempts < max_attempts`

If retried, the job returns to `queued` and can be leased again. Attempt history should be preserved, at minimum as an `attempts` counter.

### Idempotency Expectation

Retries can cause the same logical job to run more than once. Jobs should therefore be designed as potentially non-idempotent.

Recommended pattern: write outputs into job-specific or attempt-specific paths that include job identifiers.

v0 does not deduplicate outputs across retries. It records attempts and stores artifacts according to configured path and overwrite behavior.
