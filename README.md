# deborgen // compute with friends

**deborgen** is a small distributed compute cooperative for friends who want to build and run things together.

It connects personal machines — gaming PCs, laptops, workstations — into a shared job system so that idle compute can be pooled for modeling, optimization, simulation, and experimentation. Instead of renting cloud resources, a group can coordinate what they already have.

deborgen is intentionally lightweight. It provides a structured way for friends to share compute responsibly, transparently, and with clear rules without introducing production-orchestrator complexity.

## Why

Many computational projects don’t need tightly coupled HPC. They need parallel throughput: running many independent simulations, optimization sweeps, experiments, or model evaluations.

At the same time, most personal machines sit idle for large parts of the day.

deborgen exists to explore a simple idea: what if a small, trusted group pooled their machines during agreed hours and used them intentionally?

The primary goal is shared capability rather than maximum performance.

## What It Is

deborgen consists of a coordinator and a set of voluntary worker nodes.

The coordinator maintains a job queue, records job history, and provides a simple API for submitting work. Worker nodes opt in, connect securely over an overlay network, poll for jobs, execute them in isolated environments, and upload results and logs.

The system uses a pull-based model: machines take work when available rather than being directly controlled. This keeps participation lightweight and respectful of personal ownership.

Jobs are transparent. Each job records who submitted it, where it ran, when it started and finished, and what it produced. The system prioritizes clarity and auditability over complexity.

## Cooperative Model

Participation is voluntary. Nodes may join or leave at any time. Execution windows can be limited to agreed work hours. Jobs are time-bounded and resource-limited.

The system assumes a trusted group and emphasizes shared norms:

- transparency
- explicit rules
- opt-in participation
- shared benefit

When someone needs extra compute for a project, the cooperative makes it available. When they contribute a machine, they increase the group’s collective capacity.

## Scope (v0)

The first version of deborgen provides a minimal but complete loop:

- submit a job
- a remote machine runs it
- logs are recorded
- artifacts are stored
- the job history is visible

This is enough to coordinate real work across multiple personal machines while keeping the system understandable.

## Quickstart (v0)

Run the minimal cross-machine loop:

- submit a job
- worker claims and executes
- logs are recorded
- job reaches a terminal state

Start here: [`quickstart.md`](./quickstart.md)

Then use:

- [`architecture.md`](./architecture.md) for system model and state transitions
- [`api.md`](./api.md) for HTTP contract details
- [`docs/ops/deployment.md`](./docs/ops/deployment.md) for the validated v0 coordinator/worker operating model

## Intent

deborgen is both a practical tool and a shared experiment.

It explores distributed systems at a human scale, studies scheduling and allocation in a real environment, and helps people build together using the resources already in the room.

The system will grow only as needed.
