# Lab 02: Code Reading — The Coordinator

## Concept

Before porting the worker to Go, you need to understand the Python code
deeply enough that you could explain it to someone else. This lab has no
coding. It's about reading.

The test: could you rebuild this from scratch if the files were deleted?

## Task

Read `src/deborgen/coordinator/app.py` and `src/deborgen/worker/agent.py`
in full. Then answer the questions below **in writing** — create a file
`labs/02-answers.md` and write your answers there.

Don't look up answers before forming your own. Then verify against the code.

## Questions

**Threading and locking**

1. `sqlite3.connect` is called with `check_same_thread=False`. What does that
   argument do, and what does `self._lock = threading.Lock()` do that SQLite
   itself does not?

2. `assert_job_lease` acquires `self._lock`, and then `finish_job` acquires
   it again in a separate call. Why is this potentially a problem? What would
   you need to change to make the lease check and the status update atomic?

**The claim loop**

3. Two workers poll `GET /jobs/next` at exactly the same time. Both see
   `job_1` as queued and matching. Walk through the code and explain why only
   one of them ends up with the job. Which line is the one that makes this
   safe?

4. `claim_next_job` fetches all queued jobs with `fetchall()` and loops in
   Python. The old version used `LIMIT 1`. What is the trade-off? Name a
   scenario where the new version is necessary and one where it becomes a
   problem.

**Schema and migrations**

5. The `_init_schema` method runs `CREATE TABLE IF NOT EXISTS` and then
   tries `ALTER TABLE jobs ADD COLUMN requirements_json`. In two different
   scenarios — a fresh database and an existing database from before
   `requirements_json` was added — walk through what happens in each case.
   Is there a scenario where this silently fails to add the column?

**The worker loop**

6. The worker sends heartbeats even during quiet hours (`--work-hours`).
   Why? What would break if heartbeats stopped during quiet hours?

7. `is_within_work_hours` takes `now: datetime` as a parameter rather than
   calling `datetime.now()` internally. What is the reason for this design
   choice? What would be harder to do if `datetime.now()` were called inside
   the function?

8. The artifact upload block has a `finally` clause that deletes the zip
   file. It checks `if 'zip_path' in locals()` rather than just referencing
   `zip_path`. Why?

**Design**

9. `record_artifact` checks `if url not in artifact_urls` before appending.
   In theory the coordinator controls both sides of this. Why might a
   duplicate URL arrive?

10. The worker uses a separate `httpx.put(upload_url, ...)` call without the
    coordinator's `Authorization` header. Why is this correct? What would
    happen if the Bearer token were included?

## When you're done

You don't need to get every answer perfect. The point is to have read the
code carefully enough to have an opinion. Uncertain answers are fine — mark
them with a `?` and note what you'd need to look up.

Move to Lab 03 when you can answer at least 7 of the 10 with confidence.
