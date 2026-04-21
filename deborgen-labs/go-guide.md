# Go Guide for deborgen-labs

This guide is specific to the Go you'll write in Labs 03–06. It pairs every
concept with the Python equivalent from `agent.py` so you can translate what
you already know.

---

## The one rule: errors are values

Python raises exceptions. Go returns errors. Every function that can fail
returns `(result, error)`. You must handle it explicitly — Go will not remind
you at runtime.

```python
# Python
response = client.post(url, json=payload)
response.raise_for_status()
```

```go
// Go
resp, err := client.Do(req)
if err != nil {
    log.Printf("[worker] request failed: %v", err)
    return
}
if resp.StatusCode != http.StatusOK {
    log.Printf("[worker] unexpected status: %d", resp.StatusCode)
    return
}
```

If you use `_` to discard an error, be intentional. A discarded error is a
silent failure waiting to bite you.

---

## Structs and JSON

Python uses dicts. Go uses structs with field tags that control JSON keys.

```python
# Python (agent.py send_heartbeat)
client.post(f"/nodes/{node_id}/heartbeat", json={
    "name": name,
    "labels": labels,
})
```

```go
// Go equivalent
type HeartbeatRequest struct {
    Name   *string                `json:"name"`
    Labels map[string]interface{} `json:"labels"`
}

payload := HeartbeatRequest{
    Name:   nil,           // serializes to JSON null
    Labels: map[string]interface{}{
        "os":        runtime.GOOS,
        "arch":      runtime.GOARCH,
        "cpu_cores": runtime.NumCPU(),
    },
}

body, err := json.Marshal(payload)
```

`*string` is a pointer to string. When nil, it marshals to JSON `null` — which
is what the coordinator expects for an absent name. A plain `string` would
marshal to `""`.

---

## Making HTTP requests

```python
# Python
response = client.post(url, content=data, headers={"Content-Type": "application/json"})
```

```go
// Go
req, err := http.NewRequest("POST", url, bytes.NewReader(body))
if err != nil { ... }
req.Header.Set("Content-Type", "application/json")
req.Header.Set("Authorization", "Bearer "+token)

client := &http.Client{Timeout: 10 * time.Second}
resp, err := client.Do(req)
if err != nil { ... }
defer resp.Body.Close()   // always close the body
```

Always call `resp.Body.Close()`. If you don't, the HTTP connection leaks.
`defer` (explained below) is the right tool for this.

---

## CLI flags

```python
# Python (agent.py parse_args)
parser.add_argument("--coordinator", required=True)
parser.add_argument("--node-id", required=True)
parser.add_argument("--token", default=None)
args = parser.parse_args()
```

```go
// Go standard library
coordinator := flag.String("coordinator", "", "coordinator URL")
nodeID      := flag.String("node-id", "", "node identifier")
token       := flag.String("token", "", "bearer token")
flag.Parse()

// flags are pointers — dereference with *
fmt.Println(*coordinator)
```

For Lab 06 you'll switch to `cobra` for subcommands, but `flag` is the right
tool for Labs 03–05.

---

## Goroutines

Python's `agent.py` uses a single thread with a `while True` loop, interleaving
heartbeats and job polling by tracking `next_heartbeat`. Go uses goroutines —
lightweight threads you start with `go`.

```python
# Python (agent.py worker_loop) — single thread, manual timing
next_heartbeat = 0.0
while True:
    now = time.monotonic()
    if now >= next_heartbeat:
        send_heartbeat(...)
        next_heartbeat = now + heartbeat_seconds
    # ... poll for jobs
```

```go
// Go — heartbeat runs in its own goroutine
go func() {
    ticker := time.NewTicker(15 * time.Second)
    defer ticker.Stop()
    for range ticker.C {
        sendHeartbeat()
    }
}()

// main goroutine handles job polling
for {
    pollForJob()
    time.Sleep(2 * time.Second)
}
```

`go func()` starts the goroutine and returns immediately. Both loops run
concurrently. The `ticker.C` channel delivers a value every 15 seconds —
`for range ticker.C` blocks until the next tick.

---

## defer — cleanup that always runs

Python uses `with` statements and `finally` blocks for cleanup. Go uses `defer`.

```python
# Python (agent.py artifact upload)
finally:
    try:
        if 'zip_path' in locals() and os.path.exists(zip_path):
            os.remove(zip_path)
    except Exception:
        pass
```

```go
// Go
tmpDir, err := os.MkdirTemp("", "job-*")
if err != nil { ... }
defer os.RemoveAll(tmpDir)  // runs when surrounding function returns, no matter what

zipFile, err := os.CreateTemp("", "artifacts-*.zip")
if err != nil { ... }
defer os.Remove(zipFile.Name())
```

`defer` runs when the enclosing *function* returns — not the block. If you
need cleanup at block scope, extract a function. Multiple defers run in
reverse order (LIFO).

---

## Running subprocesses

```python
# Python (agent.py run_job)
completed = subprocess.run(
    argv,
    capture_output=True,
    text=True,
    timeout=timeout_seconds,
    cwd=work_dir,
)
```

```go
// Go
ctx, cancel := context.WithTimeout(context.Background(),
    time.Duration(timeoutSeconds)*time.Second)
defer cancel()

args := strings.Fields(command)   // strings.Fields ≈ shlex.split (no quote handling)
cmd := exec.CommandContext(ctx, args[0], args[1:]...)
cmd.Dir = workDir

output, err := cmd.CombinedOutput()  // stdout + stderr merged, like capture_output=True

// Distinguish timeout from other errors
if ctx.Err() == context.DeadlineExceeded {
    failureReason = fmt.Sprintf("timeout exceeded (%ds)", timeoutSeconds)
    exitCode = 124
} else {
    var exitErr *exec.ExitError
    if errors.As(err, &exitErr) {
        exitCode = exitErr.ExitCode()
    } else if err != nil {
        failureReason = fmt.Sprintf("exec error: %v", err)
        exitCode = 127
    }
}
```

`context.WithTimeout` is the Go equivalent of subprocess's `timeout=` parameter.
When the deadline passes, Go sends SIGKILL automatically.

Note: `strings.Fields` does not handle quoted arguments (`echo "hello world"`
becomes three args). This is a known limitation vs `shlex.split` — acceptable
for now.

---

## System info

```python
# Python (agent.py parse_labels)
labels["os"] = platform.system().lower()
labels["arch"] = platform.machine().lower()
labels["cpu_cores"] = os.cpu_count()
```

```go
// Go — from the runtime package
labels := map[string]interface{}{
    "os":        runtime.GOOS,    // "linux", "darwin", "windows"
    "arch":      runtime.GOARCH,  // "amd64", "arm64"
    "cpu_cores": runtime.NumCPU(),
}
```

---

## Zip file creation

```python
# Python (agent.py artifact upload)
zip_path = shutil.make_archive(
    base_name=...,
    format="zip",
    root_dir=job_work_dir,
)
```

```go
// Go — manual but explicit
zipFile, _ := os.CreateTemp("", "artifacts-*.zip")
defer os.Remove(zipFile.Name())

w := zip.NewWriter(zipFile)
filepath.Walk(srcDir, func(path string, info fs.FileInfo, err error) error {
    if info.IsDir() {
        return nil
    }
    relPath, _ := filepath.Rel(srcDir, path)
    f, _ := w.Create(relPath)
    src, _ := os.Open(path)
    defer src.Close()
    io.Copy(f, src)
    return nil
})
w.Close()
zipFile.Close()
```

---

## S3 upload via presigned URL

```python
# Python (agent.py) — separate client, no auth header
with open(zip_path, "rb") as f:
    httpx.put(upload_url, content=f, timeout=300.0).raise_for_status()
```

```go
// Go — same idea: no Authorization header, set ContentLength
file, _ := os.Open(zipPath)
defer file.Close()

stat, _ := file.Stat()
req, _ := http.NewRequest("PUT", uploadURL, file)
req.ContentLength = stat.Size()   // some S3 providers require this

uploadClient := &http.Client{Timeout: 5 * time.Minute}
resp, err := uploadClient.Do(req)
```

Use a separate `http.Client` for S3 uploads — not the one with your
`Authorization: Bearer` header. Sending your coordinator token to S3 is
harmless but wrong.

---

## Cobra subcommands (Lab 06)

```go
var rootCmd = &cobra.Command{Use: "deborgen"}

var workerCmd = &cobra.Command{
    Use:   "worker",
    Short: "Start a worker node",
    Run: func(cmd *cobra.Command, args []string) {
        // pull flags, call workerLoop()
    },
}

var submitCmd = &cobra.Command{
    Use:  "submit [command]",
    Args: cobra.ExactArgs(1),
    Run: func(cmd *cobra.Command, args []string) {
        command := args[0]
        // POST /jobs
    },
}

func init() {
    rootCmd.AddCommand(workerCmd, submitCmd)
    workerCmd.Flags().StringVar(&coordinator, "coordinator", "", "coordinator URL")
}

func main() {
    rootCmd.Execute()
}
```

---

## Cross-compilation (Lab 06)

Go compiles for other platforms natively — no Docker, no cross-compiler.

```makefile
build:
	GOOS=linux   GOARCH=amd64 go build -ldflags="-s -w" -o bin/deborgen-linux-amd64    ./cmd/worker
	GOOS=darwin  GOARCH=arm64 go build -ldflags="-s -w" -o bin/deborgen-darwin-arm64   ./cmd/worker
	GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o bin/deborgen-windows-amd64.exe ./cmd/worker
```

`-ldflags="-s -w"` strips debug symbols — reduces binary size ~30%.

---

## Quick reference

| Python | Go |
|--------|-----|
| `platform.system().lower()` | `runtime.GOOS` |
| `platform.machine().lower()` | `runtime.GOARCH` |
| `os.cpu_count()` | `runtime.NumCPU()` |
| `shlex.split(cmd)` | `strings.Fields(cmd)` (no quote handling) |
| `subprocess.run(..., timeout=N)` | `exec.CommandContext(ctx, ...)` with `context.WithTimeout` |
| `with tempfile.TemporaryDirectory() as d:` | `os.MkdirTemp(...)` + `defer os.RemoveAll(d)` |
| `shutil.make_archive(..., format="zip")` | `archive/zip` + `filepath.Walk` |
| `time.sleep(n)` | `time.Sleep(n * time.Second)` |
| `while True:` with manual timing | goroutine + `time.NewTicker` |
| `try/finally` | `defer` |
| `argparse` | `flag` (Labs 03–05), `cobra` (Lab 06) |
| `httpx.Client(base_url=..., headers=...)` | `http.Client{}` + set headers per-request |
