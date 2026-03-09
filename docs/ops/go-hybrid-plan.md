# Educational Plan: The Go Hybrid Architecture

This plan outlines the steps for rewriting the `deborgen` worker and CLI in Go, while leaving the central coordinator in Python. This polyglot architecture is designed to maximize educational yield, forcing a strict separation of concerns, strong API boundaries, and hands-on experience with OS-level process management.

## Why We Are Doing This
* **Distribution:** We want a single, zero-dependency binary (`deborgen.exe` / `deborgen`) that friends can download and run instantly, without installing Python or Docker.
* **API Contracts:** Forcing a compiled language (Go) to talk to a dynamic backend (Python) hardens the API design and JSON serialization logic.
* **Systems Engineering:** Go's `os/exec` and goroutines provide deep exposure to low-level process and stream management.

---

## Phase 1: Go Setup & The Minimum Viable Worker

**Goal:** Set up a Go project and replicate the basic heartbeat and polling loop of `agent.py`.

1. **Initialize the Module:**
   * Create a new directory alongside `src/` (e.g., `cmd/deborgen/` or `go-client/`).
   * Run `go mod init github.com/yourusername/deborgen`.
2. **Define the Types (JSON Unmarshaling):**
   * Review `api.md` and define Go `struct`s for `Job`, `Node`, and the heartbeat/polling responses. 
   * *Educational focus:* Learn how Go uses struct tags (e.g., ``json:"job_id"``) to map JSON to strong types.
3. **Implement the HTTP Client:**
   * Use Go's standard `net/http` library to implement the `sendHeartbeat` and `pollNextJob` functions.
   * Do not use third-party HTTP libraries yet; learn the standard library first.
   * *Educational focus:* Learn how to construct requests, add `Authorization` headers, and use `json.NewDecoder`.
4. **Hardware Auto-Detection:**
   * Use `runtime.GOOS`, `runtime.GOARCH`, and `runtime.NumCPU()` to auto-populate the node's capabilities.
5. **The Loop:**
   * Write the main `for {}` loop using `time.Sleep`. 
   * Implement the `--work-hours` logic using Go's `time` package (parsing strings with `time.Parse`).

## Phase 2: Process Execution & Stream Handling

**Goal:** Replicate the `run_job` function, safely spawning processes and capturing output.

1. **Subprocesses in Go:**
   * Use the `os/exec` package to spawn the job command.
   * *Challenge:* Python's `shlex.split()` handles quoted strings gracefully. In Go, you may need a lightweight library like `github.com/google/shlex` to parse the command string into an array of arguments, or require jobs to pass arguments explicitly.
2. **Context and Timeouts:**
   * Use Go's `context.WithTimeout` to strictly enforce the job's `timeout_seconds`.
   * *Educational focus:* Understand how `exec.CommandContext` sends a `SIGKILL` to a runaway process when the timer expires.
3. **Temporary Directories:**
   * Use `os.MkdirTemp` to create the isolated working directory.
4. **Streaming Output (Advanced):**
   * Instead of waiting for the job to finish to collect logs, use `StdoutPipe()` and `StderrPipe()` to capture the output as it streams.
   * *Optional:* Learn how to buffer this stream and periodically `POST` it to the coordinator so you get real-time logs.

## Phase 3: Artifact Uploads (S3)

**Goal:** Zip the isolated directory and upload it using the Presigned URL.

1. **Zipping in Go:**
   * Use the standard `archive/zip` library to walk the temporary directory and compress any generated files.
   * *Educational focus:* Learn how `filepath.Walk` works and how to write data into a zip writer stream.
2. **The Direct Upload:**
   * Request the presigned URL from the Python coordinator.
   * Perform an HTTP `PUT` using the presigned URL, attaching the zip file as the request body.
3. **Cleanup:**
   * Use `defer os.RemoveAll(tmpDir)` to guarantee the host machine is wiped clean regardless of whether the job succeeds, fails, or panics.

## Phase 4: CLI Ergonomics & Cross-Compilation

**Goal:** Polish the binary so it contains both the Worker and the Submitter CLI, and distribute it.

1. **The CLI Router:**
   * Use a library like `cobra` (or Go 1.22's new flag routing) to create a multi-command CLI.
   * `deborgen worker --work-hours "22:00-08:00"` starts the background agent.
   * `deborgen submit "python train.py" --gpu` sends a POST request to the coordinator.
2. **Cross-Compilation:**
   * Write a simple build script or Makefile.
   * Run `GOOS=windows GOARCH=amd64 go build -o bin/deborgen.exe`.
   * Run `GOOS=darwin GOARCH=arm64 go build -o bin/deborgen-mac`.
   * *Educational focus:* Experience the power of static compilation. Send the `.exe` to a friend and watch them join the cluster immediately.

---

## What Happens to the Python Code?
* `src/deborgen/coordinator/app.py`: **Keep it.** It remains the source of truth, API router, and scheduling brain.
* `src/deborgen/worker/agent.py`: **Deprecate it.** Keep it around as a reference implementation, but treat the new Go binary as the official `deborgen` node agent moving forward.
