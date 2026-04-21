# Context managers and locks

Two concepts that unlock reading the coordinator code.

---

## Part 1: Context managers (`with` blocks)

A context manager runs setup before the indented block and teardown after it — no matter how the block exits (normal return, exception, crash).

The simplest example is a file:

```python
# Without a context manager
f = open("data.txt")
data = f.read()
f.close()   # what if .read() raises an exception? close() never runs. file leaks.

# With a context manager
with open("data.txt") as f:
    data = f.read()
# f.close() runs automatically here, even if .read() raised
```

That's it. `with X as y:` means:
1. Call setup on `X` → get `y`
2. Run the indented block
3. Call teardown on `X` — **always**, even if the block raised an exception

You don't need to know how to *write* a context manager yet. You just need to recognize what `with` *does*.

---

## Part 2: `threading.Lock` — your exchange intuition, Python syntax

You already know why locks exist. When two threads share mutable state, you need to ensure only one touches it at a time. That's exactly what `threading.Lock` does.

```python
import threading

lock = threading.Lock()

# Without lock — race condition
balance = 1000

def withdraw(amount):
    global balance
    current = balance       # thread A reads 1000
                            # thread B reads 1000  <-- both see same value
    balance = current - amount  # A writes 900, B writes 900
                                # one withdrawal is lost

# With lock
def withdraw_safe(amount):
    global balance
    with lock:              # only one thread can be here at a time
        current = balance   # guaranteed: no other thread touches balance right now
        balance = current - amount
```

`with lock:` is a context manager. Setup = acquire the lock (block if another thread holds it). Teardown = release the lock. The indented block is the critical section — only one thread runs it at a time.

In Java you wrote `synchronized` blocks. `with lock:` is the same idea.

---

## Part 3: Reading the coordinator

Now look at the coordinator with fresh eyes.

```python
class SqliteJobStore:
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path)
        self._lock = threading.Lock()   # one lock for the whole store
```

`self._lock` is an instance variable (like a Java field). Every method on the same `SqliteJobStore` instance shares this one lock.

```python
    def assert_job_lease(self, job_id: str, node_id: str, lease_token: str) -> None:
        with self._lock:
            row = self._get_job_row(job_pk)
            lease = self._conn.execute("SELECT ...").fetchone()
            if lease is None:
                raise HTTPException(status_code=409, ...)
```

`with self._lock:` means: acquire the store's lock before reading the database, release it after. While one request is inside this block, any other request that tries to enter *any* `with self._lock:` block on the same store will wait.

```python
    def record_artifact(self, job_id: str, url: str) -> None:
        with self._lock, self._conn:   # two context managers on one line
            ...
```

`with self._lock, self._conn:` enters both context managers. `self._lock` you know. `self._conn` (the SQLite connection used as a context manager) wraps the operations in a database transaction — if anything raises, the transaction rolls back.

---

## What the lock guarantees — and what it doesn't

The lock guarantees that **the code inside `with self._lock:`** runs atomically with respect to other code that also uses `self._lock`.

It does NOT make separate lock acquisitions atomic with each other.

Look at `finish_job`:

```python
def finish_job(self, job_id, request):
    store.assert_job_lease(job_id, request.node_id, request.lease_token)  # acquires + releases lock
    return store.finish_job(...)   # acquires + releases lock again
```

There are two separate `with self._lock:` blocks, called one after the other. Between them, the lock is released. Another thread could sneak in between the lease check and the actual finish. This is a real gap in the coordinator — it's one of the questions Lab 02 asks you to identify.

---

## HTTP status codes (quick reference)

| Code | Meaning | When you see it |
|------|---------|-----------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource was created (`POST /jobs`) |
| 204 | No Content | Success, nothing to return (`GET /jobs/next` when queue is empty) |
| 404 | Not Found | The resource doesn't exist |
| 409 | Conflict | Resource exists but your request conflicts with its state |
| 500 | Server Error | Something broke on the server side |

409 is the one you'll see most. `assert_job_lease` returns 409 when the job exists but you don't own it, or the lease expired.

---

## The three lines you can now read

```python
with self._lock:           # acquire threading.Lock, release when block exits
    ...

with self._conn:           # begin SQLite transaction, commit or rollback when block exits
    ...

with self._lock, self._conn:   # both, in order
    ...
```

Next: a notebook on what the lock actually guarantees under concurrent load — with code you can run to see a race condition break things, then fix it.
