# Phase B: Heterogeneous Label-Based Routing

## Goal
Transform the system from a pure FIFO queue into a label-aware scheduler. Jobs should be able to declare hardware or environment requirements (e.g., `gpu: true`, `os: linux`), and the coordinator should only assign these jobs to worker nodes that possess matching capabilities. 

To reduce friction for participants, the worker agent should also auto-detect basic hardware capabilities.

## Strategy

### 1. Data Model & Schema Updates
- **Models:** Add a `requirements` field (a dictionary of key-value pairs) to `JobCreateRequest` and the `Job` Pydantic model.
- **Database:** Add a `requirements_json` column to the `jobs` SQLite table. Default to `{}` for backward compatibility.

### 2. Coordinator Matching Logic
- Currently, `claim_next_job` blindly grabs the oldest queued job.
- **New Flow:**
  1. Fetch the node's current `labels_json` from the `nodes` table using the requesting `node_id`.
  2. Fetch a batch of oldest `queued` jobs.
  3. In Python, evaluate each job's `requirements` against the node's `labels`. A job matches if every key in `requirements` exists in `labels` and the values are exactly equal.
  4. Attempt an atomic `UPDATE` on the first matched job. If it succeeds, issue the lease.

### 3. Worker Auto-Detection (Zero-Friction Onboarding)
- Update `agent.py` to automatically detect basic system characteristics upon startup:
  - `os`: `platform.system().lower()` (e.g., `linux`, `darwin`, `windows`)
  - `arch`: `platform.machine().lower()` (e.g., `x86_64`, `arm64`)
  - `cpu_cores`: `os.cpu_count()`
- Merge these auto-detected labels with any manual labels provided by the user via `--labels-json`. Manual labels override auto-detected ones.

### 4. Educational Notes

#### Why Subset Matching in Python instead of SQL?
SQLite's `JSON1` extension provides functions like `json_extract`, but testing if JSON object A is a complete subset of JSON object B purely in SQL can be surprisingly complex and brittle across different SQLite versions. By fetching the oldest `queued` jobs and performing the matching logic in Python, we keep the code readable, highly testable, and independent of specific SQLite extension versions. We still retain atomicity by executing a targeted `UPDATE` using the matched job's specific `id`.

#### Frictionless Node Onboarding
By automatically detecting the node's `os`, `arch`, and `cpu_cores` via Python's standard `platform` and `os` libraries, users can instantly participate in the cluster without needing to figure out the correct command-line arguments to describe their machines.

## Progress
- [x] Create plan.
- [x] Update models and schema in `app.py`.
- [x] Implement subset matching logic in `claim_next_job`.
- [x] Add auto-detection to `worker/agent.py`.
- [x] Write tests for label matching.
- [x] Update `api.md`.
