# Agent State Transitions

(this file incorrectly uses the term agent instead of worker)

The worker agent does not manage global state—that is the responsibility of the coordinator. Instead, the agent operates an internal state machine driven by network responses, local OS timers, and process execution results. 

## The Internal Polling Loop

The agent continuously transitions through the following internal states:

### 1. `EVALUATE_SCHEDULE`
**Trigger:** Start of the loop.
**Action:** Evaluates `datetime.now()` against the `--work-hours` flag.
*   **Path A (Within Hours):** Proceed to `POLL_QUEUE`.
*   **Path B (Outside Hours):** Transition to `REST`. Wait `poll_seconds` and return to `EVALUATE_SCHEDULE`.

### 2. `POLL_QUEUE`
**Trigger:** Agent is within work hours.
**Action:** Sends an HTTP `GET /jobs/next?node_id=...` to the coordinator.
*   **Path A (Status 200 - Job Claimed):** The coordinator has validated the agent's labels and granted a lease. Transition to `EXECUTE_JOB`.
*   **Path B (Status 204 - Queue Empty/No Match):** Transition to `REST`. Wait `poll_seconds` and return to `EVALUATE_SCHEDULE`.
*   **Path C (Network Error):** Log the exception, transition to `REST`, wait, and retry.

### 3. `EXECUTE_JOB`
**Trigger:** A valid job payload and cryptographic `lease_token` are received.
**Action:** 
1.  Create an isolated temporary directory.
2.  Spawn the job's `command` as an OS subprocess (`os/exec` or `subprocess.run`).
3.  Enforce the job's `timeout_seconds`.
*   **Path A (Process Exits normally):** Transition to `PROCESS_ARTIFACTS`.
*   **Path B (Process Timeouts/Exceptions):** Log the error and transition to `REPORT_FAILURE`.

### 4. `PROCESS_ARTIFACTS`
**Trigger:** The local subprocess has terminated (successfully or otherwise).
**Action:** Scans the isolated temporary directory.
*   **Path A (Files Found):** Zip the directory $\rightarrow$ Request S3 Presigned URL $\rightarrow$ Upload to S3 $\rightarrow$ Notify Coordinator. Transition to `REPORT_TERMINAL_STATE`.
*   **Path B (No Files Found):** Skip upload logic. Transition to `REPORT_TERMINAL_STATE`.

### 5. `REPORT_TERMINAL_STATE`
**Trigger:** Execution and artifact handling are complete.
**Action:** Agent explicitly surrenders the lease by sending an HTTP `POST /jobs/{id}/finish` to the coordinator, including the `exit_code` (0 for success, non-zero for failure).
*   **Path:** Always transitions to `REST`, waits, and returns to `EVALUATE_SCHEDULE`.

---

## Asynchronous Heartbeats

Independently of the states above, a time-based threshold controls the heartbeat.

*   **`HEARTBEAT`:** If `time.monotonic() >= next_heartbeat`, the agent immediately executes an HTTP `POST /nodes/{id}/heartbeat` containing its identity and auto-detected labels. 
*   **Rule:** This action executes *regardless* of whether the agent is in `REST` or `EVALUATE_SCHEDULE`, ensuring the coordinator never falsely assumes a resting node has died.
