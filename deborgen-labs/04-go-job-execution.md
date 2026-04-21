# Lab 04: Go Worker — Claim and Execute Jobs

## Concept

This lab is where the Go worker becomes real. You'll add job polling, process
execution, log capture, and result reporting.

The most important new concept is **context cancellation**. In Go, a
`context.Context` carries a deadline or cancellation signal that flows through
your whole call stack. When a job times out, you pass a context with a
deadline to `exec.CommandContext` — Go sends SIGKILL automatically when the
deadline passes. No manual timer, no leftover zombie process.

Compare every function you write to its Python equivalent in `agent.py`.
Notice what's similar, what's different, and why.

## Task

Extend your Lab 03 binary to also:

1. Poll `GET /jobs/next?node_id={node_id}` on the same interval as heartbeats
   (or a separate configurable interval)
2. When a job is returned (HTTP 200), execute the command as a subprocess
3. Capture combined stdout+stderr
4. After the job finishes, `POST /jobs/{id}/logs` with the captured output
5. `POST /jobs/{id}/finish` with the exit code and any failure reason

The job claim response looks like:
```json
{
  "job": {
    "id": "job_1",
    "command": "echo hello",
    "timeout_seconds": 3600
  },
  "lease_token": "abc123"
}
```

## Acceptance criteria

With the Python coordinator running:

1. Submit a job: `curl -X POST http://localhost:8000/jobs -d '{"command":"echo hello from go"}'`

2. Your Go worker claims it and runs it. The coordinator shows the job as
   `succeeded`.

3. `GET /jobs/job_1/logs` returns `"hello from go\n"`.

4. Submit a job with a 2-second timeout: `{"command": "sleep 10", "timeout_seconds": 2}`.
   The job finishes as `failed` with `failure_reason` containing `"timeout"`.
   It completes in ~2 seconds, not 10.

5. Submit a job with a nonexistent command: `{"command": "notacommand"}`.
   The job finishes as `failed`. No panic, no crash.

## Key Go packages to use

- `os/exec` — `exec.CommandContext(ctx, args[0], args[1:]...)`
- `context` — `context.WithTimeout(context.Background(), duration)`
- `strings` — `strings.Fields(command)` splits a command string into args

## Hints

<details>
<summary>Hint 1: Splitting the command string</summary>

Python uses `shlex.split` to handle quoted strings like
`echo "hello world"` correctly. Go's `strings.Fields` splits on whitespace
only — it won't handle quotes. For now, `strings.Fields` is fine. Note it
as a known limitation.

```go
args := strings.Fields(command)
if len(args) == 0 {
    // handle empty command
}
cmd := exec.CommandContext(ctx, args[0], args[1:]...)
```
</details>

<details>
<summary>Hint 2: Capturing output</summary>

```go
output, err := cmd.CombinedOutput()
```

`CombinedOutput()` runs the command and returns stdout+stderr merged together
as a `[]byte`. It also returns an error — but a non-zero exit code IS an
error in Go's exec package. Check the type:

```go
var exitErr *exec.ExitError
if errors.As(err, &exitErr) {
    exitCode = exitErr.ExitCode()
} else if err != nil {
    // something else went wrong (command not found, etc.)
}
```
</details>

<details>
<summary>Hint 3: Context timeout for job execution</summary>

```go
timeout := time.Duration(job.TimeoutSeconds) * time.Second
ctx, cancel := context.WithTimeout(context.Background(), timeout)
defer cancel()

cmd := exec.CommandContext(ctx, args[0], args[1:]...)
output, err := cmd.CombinedOutput()

if ctx.Err() == context.DeadlineExceeded {
    // timed out
}
```

Always call `cancel()` — the `defer cancel()` pattern ensures it's called
even if the function returns early.
</details>

<details>
<summary>Hint 4: Running heartbeat and polling concurrently</summary>

Your heartbeat loop from Lab 03 needs to keep running while the job executes.
The cleanest approach is to run the heartbeat in a goroutine:

```go
go func() {
    ticker := time.NewTicker(15 * time.Second)
    defer ticker.Stop()
    for range ticker.C {
        sendHeartbeat()
    }
}()
```

A goroutine is like a lightweight thread. `go func()` starts it and your main
loop continues immediately.
</details>

## When you're done

Your Go binary is now a functional worker. It can claim, run, and report jobs.
Move to Lab 05.
