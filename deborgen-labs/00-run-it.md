# Lab 00: Run it and watch one job

## Concept

Before you test this system (Lab 01) or read its code (Lab 02), you need to
**watch it move**. The architecture doc describes a heartbeat, a lease, and a
pull loop in prose. This lab turns that prose into something you see happen,
line by line, on your own machine.

The whole system runs locally in three terminals — no droplet, no Tailscale.
The quickstart assumes a cloud deployment; ignore that for now. Coordinator and
worker both run on your laptop.

The one idea to leave with: **the coordinator is passive.** It is a web server
that owns the database and answers HTTP. It never reaches out. The worker does
everything by *asking* — "I'm alive," "got work?", "here are my logs," "I'm
done." Scheduling is a worker asking a question on a loop and the answer
changing when a job appears.

## Task

Run the coordinator and one worker, submit a job, and watch its full lifecycle
in the coordinator's log. There is no code to write. The work is *observing*
and *predicting* — CS61A style: say what will happen, then check.

### 1. Start the coordinator (terminal 1)

```bash
uv run deborgen-coordinator --host 127.0.0.1 --port 8000
```

Leave it running. Read its startup lines. The last thing it does is start
*listening* on port 8000 — then it sits and waits for someone to knock.

In another shell, knock:

```bash
curl http://127.0.0.1:8000/health
```

You get `{"status":"ok"}`, and a `GET /health ... 200 OK` appears in terminal 1.
That `200` is the whole system in miniature: the coordinator answers requests.

### 2. Start a worker (terminal 2)

```bash
uv run deborgen-worker \
  --coordinator http://127.0.0.1:8000 \
  --node-id node-1 \
  --work-dir /tmp/deborgen-runs \
  --poll-seconds 5
```

The worker prints little. **Watch terminal 1 instead.** You will see the worker
talking, on a loop:

```
POST /nodes/node-1/heartbeat        200 OK          "I'm node-1, I'm alive"
GET  /jobs/next?node_id=node-1      204 No Content  "got work?"  "nope"
GET  /jobs/next?node_id=node-1      204 No Content  "got work?"  "nope"
   ... forever, while idle
```

That repeating `204` is the system idling. The `heartbeat` and the `GET /jobs/next` poll are the exact loop you will rewrite in Go in Lab 03.

### 3. Submit a job and watch the handoff (terminal 3)

Use a command that needs no working directory and no shell (see Gotchas):

```bash
curl -s -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"command": "/usr/bin/python3 -c print(6*7)"}'
```

**Predict first:** before you press enter, watch terminal 1 and say out loud
what its next few lines will be. Then submit, and watch the idle `204` stream
change:

```
POST /jobs                      201 Created     job created -> status=queued
GET  /jobs/next?node_id=node-1  200 OK          THE HANDOFF: not 204 -> queued becomes running
POST /jobs/job_1/logs           200 OK          worker streams output back
POST /jobs/job_1/finish         200 OK          running -> succeeded
```

The flip from `204` to `200` on `GET /jobs/next` **is** the `queued -> running`
transition from the architecture state model. Nothing was pushed. The worker
asked at the right moment and got a different answer.

### 4. Read the final job record

Via the API:

```bash
curl -s http://127.0.0.1:8000/jobs/job_1 | python3 -m json.tool
curl -s http://127.0.0.1:8000/jobs/job_1/logs
```

Or go straight to the database. The coordinator writes to `deborgen.db` in
whatever directory you ran it from (the project root):

```bash
# one-liner — quick column view of all jobs
sqlite3 -column -header deborgen.db "SELECT id, status, exit_code, assigned_node_id FROM jobs"

# interactive shell — for exploring
sqlite3 deborgen.db
.tables                       -- see all tables
.schema jobs                  -- see every column
SELECT * FROM jobs;           -- all rows
.quit
```

Look for `lease_expires_at` in the schema — that single column is the entire
lease mechanism from the architecture doc. It gets set when the worker claims
a job and extended on each heartbeat.

Compare this record to a freshly queued one. The fields that were `null` —
`started_at`, `finished_at`, `assigned_node_id`, `exit_code` — are now filled
in. That is the same database row, mutated through its lifecycle by the
worker's HTTP calls. This JSON shape is what your Lab 01 tests will assert on.

A successful run shows `status: succeeded`, `exit_code: 0`, and logs `42`.

## Acceptance criteria

You are done when you can, without looking:

1. Name the three roles — submitter, coordinator, worker — and say which one
  runs the job. (The worker. The coordinator never runs jobs.)
2. Explain why the coordinator's log is full of `204 No Content` when idle.
3. Point at the single log line that is the `queued -> running` transition, and
  say why it is a `200` and not a `204`.
4. Say which fields in the job record change when a job goes from `queued` to a
  terminal state.

## Gotchas (you will hit these — that's the point)

Two architecture rules bite immediately. Trigger them on purpose:

- **Isolated working directory.** Submit the built-in example:
`uv run deborgen-submit-example hello --coordinator http://127.0.0.1:8000`,
then watch it. It **fails** with "No such file or directory" for
`examples/01_hello_worker.py`. Why? The worker runs each job in a fresh temp
dir (`/tmp/deborgen-runs/tmpXXXX`), so the *relative* path points at nothing.
This is architecture.md's "dedicated working directories" — jobs do not run
where you submit them. The fix the doc recommends: use job-specific absolute
paths.
- **No shell.** Our `print(6*7)` command has no quotes for a reason. The worker
runs raw argv, not a shell line (architecture.md: "executes commands without
a shell"). Quotes and pipes are not interpreted. Try
`'{"command": "/usr/bin/python3 -c print(\"hi\")"}'` and watch it fail with a
`NameError` — the quotes were stripped, so Python saw a bare name.

## The automated replay

Once you have done this by hand, `deborgen-tutorial` runs the same submit ->
watch cycle automatically for the `hello` and `pi` examples
(`src/deborgen/cli/tutorial.py`). It is the scripted version of this lab. Note
it inherits the relative-path gotcha above for those examples, so treat its
output as "watch the loop run," not "this is how to write a job command."

## When you're done

Stop the worker and coordinator with Ctrl-C in their terminals. Then go to
Lab 01 — testing the lifecycle you just watched. The "submit -> heartbeat ->
claim" setup in Lab 01's first hint is exactly the three terminals you just
ran, collapsed into one fixture.