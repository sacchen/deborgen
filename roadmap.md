# Roadmap

This roadmap reflects the current state of `deborgen` as implemented in the repository today. It keeps the project focused on a small, understandable cooperative system and avoids jumping ahead of the actual code.

## Phase 0: Make It Real (v0: the loop)

The goal of v0 is a real end-to-end loop across two machines.

A submitter can create a job, a worker can claim it, run it, upload logs, and report a terminal result. The coordinator remains small and exposes a minimal HTTP API. The state model stays simple: `queued` to `running` to `succeeded` or `failed`.

This phase is mostly in place now. The coordinator, worker polling loop, authentication, logs, leases, and basic documentation already exist. The main remaining gap is to align the docs and implementation around artifacts: the docs describe them, but the current code does not fully implement artifact handling yet.

## Phase 1: Make It Reliable Enough To Use (v1: hardening and boring ops)

The goal of v1 is to stop losing state, reduce surprise, and make the system restart-safe enough for regular use.

Some of this foundation already exists. The coordinator already persists state in SQLite by default, and the worker/coordinator model already includes heartbeats and leases. This phase is therefore not about introducing persistence from scratch. It is about hardening what is already there.

Work in this phase includes making restart behavior explicit, deciding whether SQLite remains the default long-term store or whether Postgres becomes an option, improving failure recovery, and making logs and artifacts consistently retrievable. Scheduling should remain simple FIFO in this phase.

## Phase 2: Make It Easy For Friends To Join (v1.5: onboarding and governance)

The goal of v1.5 is to make `deborgen` feel like a real cooperative instead of a one-off demo.

The project already has a Quickstart and basic deployment notes. The next step is not to invent documentation from zero, but to reduce friction: make worker setup easier, make the operating model clearer, and define participation expectations in plain language.

This phase includes improving onboarding docs, adding a minimal status view for jobs and nodes, and documenting participation rules. It also includes making safety limits explicit, such as timeouts, CPU or resource caps, and optional execution-hour policies.

## Phase 3: Make It A Cooperative Scheduler (v2: fairness and allocation rules)

The goal of v2 is to move from a functioning queue to a real cooperative scheduler.

This is where allocation policy starts to matter. The system should add a small number of understandable rules: per-user concurrency caps, simple fair-share rotation, and basic node eligibility constraints such as GPU-required jobs.

This phase should also add lightweight operational metrics such as queue wait time, success rate, and utilization. The project should stay intentionally small and understandable. It should not become a general-purpose orchestrator.

## Phase 4: Turn It Into An Allocation Laboratory (v3: experiments)

The goal of v3 is to use the working system as a controlled environment for practical distributed systems experiments.

At this stage, `deborgen` should be stable enough that experiments are meaningful. Good targets include failure handling when workers disappear, orchestration overhead such as startup and transfer time, and comparisons between simple scheduling policies such as FIFO, fair-share, and least-loaded.

Optional work in this phase includes deduplication or result caching based on a job fingerprint derived from a normalized job specification. That should remain opt-in and should not complicate the base execution path.

## Phase 5: Optimization-Driven Scheduling (v4: operations research)

The goal of v4 is to use real workload data to explore optimization-driven scheduling decisions.

Once the system has stable usage data, scheduling can be framed as an optimization problem for small batches and compared against simpler heuristics. This phase can explore tradeoffs such as fairness versus throughput, energy cost versus latency, and whether work should run locally or on the cooperative pool.

This phase depends on the earlier phases being real first. The system needs practical operational data before optimization work becomes grounded instead of speculative.
