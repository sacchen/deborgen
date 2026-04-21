# Learning plan

---

## Where I'm starting from

**Java OOP:** Took a class. Know what a class, instance, and method are. Not strong at it. Python's `self` maps directly to Java's `this`.

**Python:** First half of CS61A (Berkeley). Solid on functions, loops, recursion, higher-order functions, and Python's environment/scope model. No classes, decorators, or context managers in practice — CS61A covers OOP in the second half.

**Concurrency:** Real intuition from a trading exchange project — know why locks are needed, know what a race condition costs. Don't know the Python mechanics.

**Go:** Brand new.

**SQL:** Not comfortable. Reading a query requires effort.

**HTTP:** Know 404 from browsing. Don't know the rest of the status code vocabulary.

---

## What I need to learn, in order

### 1. Context managers — done (read `context-managers-and-locks.md`)

What `with X:` does: setup before the block, teardown after it, always — even if the block raises. The file example, the lock example, and how to read `with self._lock, self._conn:` in the coordinator.

**When this unblocks me:** I can read any method in `SqliteJobStore` fluently.

---

### 2. threading.Lock — done (same doc)

`with lock:` acquires before the block, releases after. Only one thread inside at a time. Maps directly to the trading exchange intuition.

Key gap to still internalize: the lock guarantees atomicity *within* a single `with self._lock:` block. It does NOT make two separate acquisitions atomic with each other. The coordinator has a real instance of this bug in `finish_job`.

---

### 3. HTTP status codes — done (same doc)

| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created |
| 204 | No content |
| 404 | Doesn't exist |
| 409 | Exists but conflicts with current state |
| 500 | Server error |

**When this unblocks me:** I can write test assertions confidently and understand what `assert_job_lease` is returning and why.

---

### 4. Race conditions under concurrent load — notebook to build

The concept: what exactly breaks without a lock, and what exactly does the lock fix. The interesting detail is the coordinator's own gap — `assert_job_lease` and `finish_job` acquire the lock separately, so another thread can sneak between them. This is Lab 02 Q2 and Q3.

**Format:** Notebook. The behavior needs to be demonstrated, not just described. Run code that breaks, see why, fix it.

**When this unblocks me:** Lab 02 code reading questions, and understanding concurrent Go code in Labs 03–06.

---

### 5. pytest fixtures — notebook exists, needs rework

`deborgen-labs/pytest-fixtures.ipynb` exists but is too procedural. It teaches "how to set up this specific test" not "what fixtures are." The core concept worth teaching: isolation + composition. Each test gets a fresh database, and fixtures compose so shared setup is expressed once.

**When this unblocks me:** Lab 01. I can write `test_artifacts.py` without repeating the submit → heartbeat → claim setup in every test.

---

### 6. SQL basics — defer to Lab 02

Not needed for Lab 01. Lab 02 has questions about specific SQL patterns (`UPDATE ... WHERE status = 'queued'`, the `fetchall` loop, the schema migration). Learn when I get there.

---

### 7. Go — ongoing through Labs 03–06

Guide written at `deborgen-labs/go-guide.md`. Every Go concept is paired with the Python equivalent from `agent.py`. Work through it alongside the labs.

---

## Resources built so far

| File | What it covers | Status |
|------|---------------|--------|
| `context-managers-and-locks.md` | `with` blocks, `threading.Lock`, HTTP status codes | Read this next |
| `go-guide.md` | Go concepts paired with Python equivalents from `agent.py` | Use during Labs 03–06 |
| `pytest-fixtures.ipynb` | Fixture setup for artifact tests | Exists, needs rework |

---

## Lab state

| Lab | Topic | State |
|-----|-------|-------|
| 01 | Phase A tests (Python) | In progress — blocked on pytest fixtures |
| 02 | Code reading: the coordinator | Not started |
| 03 | Go worker: heartbeat | Not started |
| 04 | Go worker: job execution | Not started |
| 05 | Go worker: artifacts | Not started |
| 06 | Go worker: CLI + cross-compilation | Not started |

---

## What a good notebook looks like (DESIGN.md summary)

- Open with the bug or broken behavior, not the explanation
- Encounter → trace → fix → verify → exercise
- Real code from the project, not invented examples
- One pause point before the fix: "try it yourself"
- The success condition is specific: "once your cell raises X instead of Y, you've got it"
- Ask before building: after this exercise, what can I go do that I couldn't before?
- If the lesson fits in a page of prose, it's a reference doc — not a notebook
