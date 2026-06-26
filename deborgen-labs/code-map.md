# Code Map: what to understand deeply vs. treat as plumbing

A reading guide for `coordinator/app.py` and `worker/agent.py`, written for someone
porting the worker to Go and trying to find the load-bearing ideas under the Python.

**The test used throughout:** *would this still be true if I rewrote it in another
language?* If yes → **core** (a distributed-systems idea, learn it deeply). If it only
exists because of Python/FastAPI/SQLite/boto3 → **incidental** (know what it does, move on).

---

## 0. The one mental model that makes everything click

**The coordinator owns all state. The worker owns nothing.**

The worker is a dumb loop: ask for work, run it, report the result, repeat. It keeps
*nothing* on disk, holds no authority, and could be killed and restarted at any moment
without corrupting anything. Every fact that matters — what jobs exist, who's running
what, who's allowed to finish a job — lives in the coordinator's SQLite database.

Once you believe that, the whole system is just: **how does the worker safely borrow a
job, and how does the coordinator make sure two workers never think they own the same
job?** That question is the core. Everything else is serialization, type-checker noise,
and framework wiring.

This is the same intuition as your trading exchange: the matching engine is the single
source of truth; clients submit orders and react to fills, but they don't *decide* fills.

---

## 1. End-to-end trace of one job (follow this before anything else)

This is the spine. Read it once and the file stops looking like 600 random lines.

```
CLIENT          POST /jobs                  -> coordinator.create_job()        status=queued
                                               row inserted, id assigned

WORKER loop     GET /jobs/next?node_id=...  -> coordinator.claim_next_job()
  (agent.py:174)                               atomically flips queued->running,
                                               writes a lease, returns {job, lease_token}

WORKER          run_job() in a temp dir     -> subprocess runs the command locally
  (agent.py:199)                               returns (exit_code, log_text, failure_reason)

WORKER          POST /jobs/{id}/logs        -> assert_job_lease() then append_logs()
  (agent.py:210)                               (proves "I own this job" before writing)

WORKER          [if files produced]         -> presign -> PUT to S3 -> record artifact url
  (agent.py:221)                               (optional; skip on first read)

WORKER          POST /jobs/{id}/finish      -> assert_job_lease() then finish_job()
  (agent.py:269)                               status -> succeeded/failed, lease deleted
```

**The single most important thing to notice for your `finishJob`:** the worker reports a
raw `exit_code`. It does **not** decide success vs. failure. The *coordinator* does that,
in one line:

```python
next_status = "succeeded" if request.exit_code == 0 else "failed"   # app.py:355
```

So your Go `finishJob` is small: assemble `{node_id, lease_token, exit_code,
failure_reason}`, POST it, check the HTTP status, log. The interesting logic lives on the
other side of the wire. Don't go looking for success/failure branching in the worker —
it isn't there, by design.

---

## 2. The component map (core vs. incidental)

### Coordinator — `coordinator/app.py`

| Thing | Lines | Verdict | Why |
|---|---|---|---|
| `claim_next_job` | 272–342 | **CORE** ⭐ | The heart of the scheduler. Atomic claim + lease creation. Read this five times. |
| `finish_job` | 344–369 | **CORE** | The state transition you're building the client for. |
| `assert_job_lease` | 394–414 | **CORE** | The ownership check — *the* failure-handling primitive. |
| The job state machine | (implicit) | **CORE** | queued → running → succeeded/failed. Lives in the `status` column + the WHERE-guards. |
| Lease model (`leases` table) | 163–173 | **CORE** | token + expiry = "who owns this job, until when." This is how the system tolerates a dead worker. |
| Requirements/labels matching | 285–308 | **CORE** | Scheduler *placement*: which node may run which job. This is the seed of the allocation work you actually care about. |
| `threading.Lock` serializing the store | 128, used everywhere | **CORE concept / incidental mechanism** | The *idea* (serialize access to shared state) is core. The specific `Lock()` + `check_same_thread=False` is SQLite/Python ceremony. |
| HTTP status codes (204/404/409) | throughout | **CORE (protocol)** | 204 = "no work", 409 = "you don't own this / wrong state". These encode the worker↔coordinator contract. The `HTTPException` wrapper around them is incidental. |
| Pydantic models (`Job`, `JobFinishRequest`, …) | 47–123 | **incidental** | These are just the *shapes* of the JSON. In Go they become structs with json tags. The shapes matter; `Field(default_factory=...)` does not. |
| `_row_to_job` / `_row_to_node` | 196–227 | **incidental** | Hand-rolled "DB row → object" mapping. Conceptually "deserialize a row"; in Go you'd `rows.Scan(...)`. |
| `to_iso`/`parse_iso`/`utcnow` | 22–35 | **incidental** | Datetime ⇄ string because SQLite has no real datetime type. Pure storage detail. |
| `json.dumps`/`loads` for labels/requirements/artifact_urls | throughout | **incidental (but know the why)** | SQLite has no array/object column, so structured fields are stuffed into TEXT. Worth understanding *that* it happens; the calls themselves are noise. |
| `parse_job_pk` (`job_` prefix) | 38–44 | **incidental** | A formatting convention (external `job_7` ↔ internal integer `7`). Cosmetic. |
| `require_auth` / `HTTPBearer` | 474–487 | **incidental** | Bearer-token auth wiring. Real concept (auth), boring implementation. |
| `presign_artifact` (boto3/S3) | 551–593 | **mostly incidental** | S3 SDK specifics. The *one* idea worth keeping: the coordinator hands the worker a short-lived URL so the worker uploads **directly to storage** and the file never transits the coordinator. Know that pattern; ignore the boto3 args. |
| `create_app` / routes / `uvicorn.run` / `parse_args` | 490–620 | **incidental** | Framework bootstrapping. The routes are a thin pass-through to `store.*`. |

### Worker — `worker/agent.py`

| Thing | Lines | Verdict | Why |
|---|---|---|---|
| `worker_loop` structure | 143–280 | **CORE** ⭐ | heartbeat → poll → run → report. This *is* the worker. This is what your Go is replicating. |
| The pull model (`GET /jobs/next`) | 174 | **CORE** | Worker *pulls* work; coordinator never pushes. Big architectural choice — simplifies everything (no worker needs to be reachable). |
| Heartbeat cadence | 159–167 | **CORE** | Node liveness + how the coordinator learns a node's labels. The `time.monotonic()` bookkeeping is the generalizable part. |
| `finish` POST | 268–280 | **CORE** | Exactly what you're writing. Note: best-effort — if it fails, the worker just logs and moves on (the lease will expire and the job can be retried). |
| 204 / 200 / other branching on poll | 180–187 | **CORE (protocol handling)** | How the worker reacts to "no work" vs. "here's a job" vs. "something's wrong." |
| `run_job` (subprocess) | 52–82 | **CORE concept / incidental details** | "Execute the command, capture output, map outcomes to exit codes" is core. The specific exit codes (124 timeout, 127 not-found) and `shlex.split` are Python/POSIX detail. |
| `parse_labels` auto-detection | 85–108 | **half core** | The *idea* (a node advertises its capabilities: os/arch/cpu) is core to matching. `platform.system()` etc. are incidental. |
| `is_within_work_hours` | 121–141 | **incidental (domain feature)** | A nice-to-have policy filter, not a distributed-systems primitive. The midnight-spanning logic is a self-contained puzzle; safe to skip on first pass. |
| Artifact upload block | 205–266 | **mostly incidental** | Concept: zip the output dir → get presigned URL → PUT to storage → record URL. Worth knowing as four steps. The nesting, `try/except/finally`, and cleanup are ceremony — see §4. |
| httpx client setup, `raise_for_status`, print logging | throughout | **incidental** | HTTP client plumbing. In Go: `net/http` + error checks. |

---

## 3. The four core ideas, in plain terms

If you only deeply understand four things, make it these.

**(a) The atomic claim — `claim_next_job`, app.py:313–322.**
This is the whole scheduler in one UPDATE:
```sql
UPDATE jobs SET status='running', assigned_node_id=?, started_at=?, attempts=attempts+1
WHERE id=? AND status='queued' AND attempts < max_attempts
```
The `WHERE status='queued'` is a compare-and-swap. If two workers race for the same job,
the database serializes the two UPDATEs; the first flips it to `running`, the second
matches zero rows. That's why the very next line checks `if updated.rowcount != 1: return
None`. **This is optimistic concurrency control** — the same idea as a CAS loop in your
exchange, expressed as a conditional UPDATE. Don't gloss over the rowcount check; it *is*
the race protection.

**(b) Leases = ownership with an expiry — `leases` table + `assert_job_lease`.**
When a job is claimed, the coordinator mints a random `lease_token` and an expiry
(`now + 30s`). Every mutating call from the worker (logs, finish, artifacts) must present
that token, and `assert_job_lease` rejects it if the token is wrong *or expired*. Why an
expiry? Because the worker might die mid-job. The lease lets a future "reaper" notice the
expiry passed and safely re-queue the job — without it you can't distinguish "slow
worker" from "dead worker." (The reaper itself isn't built yet; that's your July work.
The lease is the hook it will hang on.)

**(c) The state machine.** A job is always in exactly one of `queued / running /
succeeded / failed`. Transitions only happen through guarded UPDATEs (`WHERE
status='queued'`, `if status != 'running': 409`). The "rules" aren't in one place — they're
distributed across those guards. Worth sketching as a diagram on paper.

**(d) The pull loop.** The worker drives everything by polling. There's no callback, no
open socket the coordinator dials back on. This is why a worker behind a laptop firewall
"just works" — it only ever makes outbound requests. Cheap, simple, and the reason the
heartbeat exists (it's the only way the coordinator learns the node is alive).

---

## 4. Things that are confusing, over-engineered, or obscure the core idea

I'm flagging these so you don't burn an afternoon thinking they're load-bearing. I'm
**not** changing them — your call.

**Dead migration code — app.py:158–162.** The `ALTER TABLE … ADD COLUMN
requirements_json` wrapped in `try/except OperationalError: pass` is defensive migration
scaffolding for a column that **is already declared** in the `CREATE TABLE` right above it
(line 154). On a fresh DB it always throws and is swallowed. It reads like "this column is
special/optional" when it isn't. Clearer version: delete the ALTER entirely and trust the
CREATE TABLE. (Same smell: the `"requirements_json" in row.keys()` guards at lines 199 and
296 defend against rows that can't exist on a clean database.)

**The lease check and the finish are two separate lock windows — app.py:526–527.**
The route does `assert_job_lease(...)` (acquires the lock, checks, releases) and *then*
`finish_job(...)` (acquires the lock again, mutates). Between those two acquisitions the
lease could expire or change. This is the TOCTOU already noted in issue #12. For your
learning it matters two ways: (1) it's a genuine bug, and (2) it muddies the lesson —
"check ownership, then act" should be **one** atomic step, not two. A clearer version
folds the lease validation *into* `finish_job` under a single `with self._lock`. Good
thing to notice now, because your Go `finishJob` client will sit right on top of this seam.

**Matching is done in Python, row by row — app.py:285–308.** Instead of asking SQLite to
find a matching job, it pulls *all* queued jobs and loops in Python comparing each job's
requirements against the node's labels. Two notes: (1) for a *learner* this is actually
**clearer** than a clever SQL JSON query would be — you can read the matching rule
directly, so don't "fix" it for readability. (2) It's O(queued jobs) per poll per worker
and won't scale, and it's exactly the code you'll be replacing when you build real
allocation mechanisms. So: understand it deeply (it's your future playground), but know
its current form is a placeholder, not a pattern to admire.

**The artifact block is nested four deep — agent.py:221–266.** The *idea* is four linear
steps (zip → presign → PUT → record). The code buries them under `if artifacts_found`, a
big `try`, an `except Exception`, and a `finally` that re-checks whether the zip exists. A
clearer version is a separate `upload_artifacts(...)` function returning early on each
failure, called as one line in the loop. On first read, just hold the four steps in your
head and skip the wrapping.

---

## 5. Non-generalizable cleverness — safe to NOT understand

These work, but they teach you nothing portable. Recognize them, don't study them. None of
this survives the trip to Go.

- **`cast(...)` everywhere** (app.py, dozens of times) — pure mypy appeasement. Runtime
  no-op. `cast(int, row['id'])` means "trust me, type checker, this is an int." Mentally
  delete every `cast(...)`.
- **`assert now is not None`** after `to_iso(...)` — type-narrowing for the checker, not a
  real invariant. Ignore.
- **`'zip_path' in locals()`** (agent.py:263) — Python introspection trick to ask "did
  that variable get assigned before the exception?" This is a code smell standing in for
  proper structure; in Go the question can't even arise. Don't internalize it.
- **`from __future__ import annotations`** (top of both files) — lets you write modern type
  hints on Python 3.11. Zero runtime meaning.
- **`secrets.token_urlsafe(24)`** (app.py:324) — "give me a random unguessable string."
  That's the whole idea; the function name is the lesson.
- **`removeprefix` / `isdigit` / `shlex.split`** — string and shell-arg parsing trivia.
- **`row_factory = sqlite3.Row`** (app.py:131) — lets you write `row["status"]` instead of
  `row[3]`. Convenience, not concept.

---

## 6. What this means for your Go `finishJob`

Pulling it together so you can write with confidence:

1. Your `finishJob` is a **client**, not a decision-maker. It sends `{node_id,
   lease_token, exit_code, failure_reason}` to `POST /jobs/{id}/finish` and inspects the
   HTTP response. Success/failure classification happens server-side (§1).
2. `lease_token` is the thing that makes the call legal. Carry it from the claim response
   all the way to finish — losing it means a 409. That single token is the whole
   ownership story from the worker's side.
3. Treat finish as **best-effort**, like the Python does (agent.py:279–280): if the POST
   fails, log and continue. The lease expiry is the safety net, so you don't need
   retries-to-the-death here.
4. Expect **409** if the lease expired or the job isn't `running`, **404** if the job id
   is wrong, **200** with the updated job on success. Branch on those like the poll
   handler does (agent.py:180–187).
5. You can **ignore** artifacts and work-hours entirely for the finish path. They sit
   *before* finish in the loop and don't change its contract.

Read order if you're tracing: app.py `claim_next_job` → `leases` table → `assert_job_lease`
→ `finish_job`, then agent.py `worker_loop` lines 174 → 268. That path is the system. The
rest is plumbing you can borrow shallowly.
