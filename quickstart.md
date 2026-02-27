# Quickstart (v0)

This guide is a guided first run for the simplest useful setup:

- local machine = submitter
- droplet = coordinator + first worker

The goal is to get to a first result quickly, then run one small practical compute job.

This quickstart follows the v0 contract in [`api.md`](./api.md). It is contract-first: depending on current implementation status, some endpoints may still be in progress.

Related docs:

- [`architecture.md`](./architecture.md)
- [`api.md`](./api.md)
- [`docs/ops/deployment.md`](./docs/ops/deployment.md)

## Mental Model

The coordinator does not execute jobs by itself. It only stores state and exposes the API.

A worker is the machine running the `deborgen-worker` process. Jobs run on whichever worker claims them.

- If the droplet is only running the coordinator, jobs do not run on the droplet.
- If the droplet is running both the coordinator and a worker, jobs can run on the droplet.
- If your laptop submits a job, that still does not mean the job runs on the laptop. It runs on the worker that claims it.

In this tutorial, the droplet is both the coordinator and the first worker. Your local machine only submits jobs and reads results.

## Prerequisites

On the droplet:

- Python 3.11+
- `uv` installed
- Tailscale installed and connected
- repository cloned
- dependencies installed with `uv sync`

On your local machine:

- `uv` installed
- repository cloned if you want to use the helper command below
- dependencies installed with `uv sync`
- network access to the coordinator over Tailscale
- the same `DEBORGEN_TOKEN` used by the coordinator

Set the shared token for authenticated API calls:

```bash
export DEBORGEN_TOKEN="<shared-token>"
```

For persistent deployments, prefer storing the coordinator token in a root-owned environment file and loading the client-side token at runtime instead of hard-coding it in shell startup files. See [`docs/ops/deployment.md`](./docs/ops/deployment.md).

## Fastest Path

If you want the quickest first run from your local machine after the coordinator and worker are up, use:

```bash
uv run deborgen-tutorial \
  --coordinator http://<coordinator-tailscale-ip>:8000
```

That command submits the `hello` example, waits for it to finish, prints logs, then does the same for the `pi` example.

## 1. Start Coordinator

On the droplet, from the project root:

```bash
uv sync
uv run deborgen-coordinator
```

Keep this process running. Leave it in its own SSH session or terminal window.

Health check:

```bash
curl http://<coordinator-tailscale-ip>:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## 2. Start Worker

In a second SSH session on the droplet, start a worker too:

```bash
uv sync
uv run deborgen-worker \
  --coordinator http://<coordinator-tailscale-ip>:8000 \
  --node-id node-1 \
  --work-dir /absolute/path/for/job-runs
```

Worker behavior: heartbeat and polling for available jobs.

Important: the worker implementation lives in `deborgen.worker.agent`, not `deborgen.worker`.

If the worker appears idle after startup, that is usually expected. It stays in a poll loop until jobs are available.

The worker executes commands without a shell. Commands must therefore be valid executable invocations, not shell pipelines or compound shell expressions.

Because the worker is running on the droplet in this tutorial, any job it claims will execute on the droplet.

## 3. First Result: Prove Where The Job Runs

From your local machine, in the project root:

```bash
uv run deborgen-submit-example hello \
  --coordinator http://<coordinator-tailscale-ip>:8000
```

Expected flow: the job enters `queued`, the droplet worker claims it, and the script runs on the droplet.

The submit helper prints the returned job id and a follow-up watch command. Run that next.

## 4. Watch The Job Finish

Run the watch command printed by the submit helper. It looks like this:

```bash
uv run deborgen-watch-job job_1 \
  --coordinator http://<coordinator-tailscale-ip>:8000
```

This command polls until the job reaches a terminal state, then prints the job summary and logs.

Expected log output includes the worker hostname and working directory. That proves the command ran on the droplet rather than on your local machine.

## 5. Practical Compute: Run A Small Real Job

Once the first example works, submit a small compute task:

```bash
uv run deborgen-submit-example pi \
  --coordinator http://<coordinator-tailscale-ip>:8000
```

This job runs a Monte Carlo estimate of pi and reports:

- how many samples it used
- how many points landed inside the circle
- the estimated value of pi
- the absolute error versus the real value of pi
- a tiny terminal-friendly accuracy bar
- how long the computation took

The point is to show the obvious next step after “proof of execution”: use the same loop to run one meaningful simulation job and get a useful result back quickly.

This also hints at why multiple workers matter later: the same Monte Carlo experiment can be split into many independent jobs with different random seeds.

Use the watch command printed by the submit helper for this second job too.

## Adding More Workers Later

Once the droplet is working as coordinator + first worker, add more workers from other machines:

- keep the droplet coordinator running
- start `deborgen-worker` on a gaming PC
- point that worker at the same coordinator URL
- submit jobs from the same local machine

At that point, jobs will run on whichever worker claims them first.

## What This Demonstrates

- local submitter / remote worker mental model
- pull-based worker execution
- centralized coordinator state
- basic audit trail via status and logs
- a path from first proof to small practical compute

## Next Steps

- add more workers
- add containerized execution on workers
- add artifact storage and retrieval
- add stronger execution isolation

For the validated `systemd` deployment shape, secret handling, SSH hardening, and recovery checklist, use [`docs/ops/deployment.md`](./docs/ops/deployment.md).
