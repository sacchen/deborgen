# Lab 03: Go Worker — Heartbeat Loop

<details>
<summary>claude code on UX prioritization</summary>
-----BEGIN AGE ENCRYPTED FILE-----
YWdlLWVuY3J5cHRpb24ub3JnL3YxCi0+IFgyNTUxOSBxYWhQK25ZYkZZU1BCdHVv
K1ZJWGU2TUxZUDhlZnFNazZvckpUOENMc3pJCnBkY0hsTnYxS2dEbTJxNGdVUGFJ
dk5FR2xPYzJIekNZNGUxVnpKZitVUHMKLT4gc3NoLWVkMjU1MTkgdWNJZG5BIDJy
U1JJM1h6c2twUGI1YnM5RnhHS2FBK1JNS01GVzhUMkYySGE2b3lSeEEKOWlvRzlm
SGVXcTI0dDdyc20vVEJacjQ2NzhQZ01HcWJXYlF5TFE1NGY1NAotPiBzc2gtZWQy
NTUxOSB3eTRzeWcgRUVhUXZjb1hYTlJIYTFtU3lEWFBycG5hZ2N5OFRaelYzUkZt
bWhpM0FSYwpKTnhGYnRlMW15Q2w2a3d2cW5DTTdlQUE3Q2w5YU1kNG1RU0hEcUlo
bXdBCi0+IHNzaC1lZDI1NTE5IEx0dld0ZyBNdU1abEtkd2xZd1FkZGVQdlgrQnQ5
d2NudmI4VDBCektRYXVVSjd1VjJNCnowVC9oeC92YXZFcVRKb0dmQUxFbHZ1TGhx
a1VPSzlKcURmVU1uTy95SGcKLS0tIGJLS0lCRVNKalpoWk8yNDFZbG0renRZd2wx
bGZFKyt5Z0k4OHhOSTNWS2cKIXSPMlQ8Ij7xL5byyxWwBmp5wDtk4EkAXcQvr8Xh
uCMBqBt6J0q03X2DxWeDxG0MeeHtNP+FQUgtZHshp6zfCfJtSamqOAC5SUuwbJpM
0+jvJUDL
-----END AGE ENCRYPTED FILE-----
</details>

## Concept

Go is the language of infrastructure tooling. Docker, Kubernetes, Prometheus,
Consul, Nomad — all Go. The reason is simple: Go compiles to a single static
binary with no runtime dependencies. Your friends can download one file and
join the cluster.

This lab gets you to the simplest useful thing: a Go binary that identifies
itself to the coordinator and stays connected.

Go has no exceptions. Errors are values returned by functions. Go has no
classes. Structs have methods. Go has no implicit type coercion. These aren't
limitations — they're why Go code is easy to read six months later.

**Compare as you go.** The Python worker is in `src/deborgen/worker/agent.py`.
For every piece of Go you write, find the equivalent Python. Understanding the
translation is the point.

## Setup

Create the Go module. From the repo root:

```bash
mkdir -p cmd/worker
cd cmd/worker
go mod init github.com/yourusername/deborgen
```

You'll write your code in `cmd/worker/main.go`. Run it with:

```bash
go run cmd/worker/main.go --coordinator http://... --node-id my-node
```

## Task

Implement a Go program that:

1. Parses `--coordinator`, `--node-id`, `--token` flags from the command line
2. Auto-detects `os`, `arch`, and `cpu_cores` using Go's standard library
3. Sends a heartbeat to the coordinator every 15 seconds
4. Prints a log line each time a heartbeat is sent or fails

The heartbeat endpoint is `POST /nodes/{node_id}/heartbeat` with body:
```json
{
  "name": null,
  "labels": {"os": "linux", "arch": "x86_64", "cpu_cores": 8}
}
```

## Acceptance criteria

With the Python coordinator running (`uv run deborgen-coordinator`):

1. `go run cmd/worker/main.go --coordinator http://localhost:8000 --node-id go-node-1`
   runs without error and prints a heartbeat log line.

2. `curl http://localhost:8000/nodes` (or `GET /jobs` to check the node table)
   shows `go-node-1` registered with correct `os`, `arch`, and `cpu_cores`
   labels matching your machine.

3. Wait 20 seconds. The `last_seen_at` timestamp on `go-node-1` has advanced.

4. Start with `--token wrong-token` against a coordinator that requires a
   token. The program logs the 401 error and keeps retrying rather than
   crashing.

## Key Go packages to use

- `flag` — standard library CLI flag parsing
- `runtime` — `runtime.GOOS`, `runtime.GOARCH`, `runtime.NumCPU()`
- `net/http` — HTTP client (use the standard library, not a third-party library)
- `encoding/json` — `json.Marshal` to serialize, `json.NewDecoder` to read responses
- `time` — `time.NewTicker(15 * time.Second)`
- `fmt`, `log` — printing and logging

## Hints

<details>
<summary>Hint 1: Struct tags for JSON</summary>

Go uses struct field tags to control JSON serialization. The coordinator
expects `snake_case` keys but Go uses `PascalCase` field names:

```go
type HeartbeatRequest struct {
    Name   *string                `json:"name"`
    Labels map[string]interface{} `json:"labels"`
}
```

`*string` is a pointer to string, which serializes to `null` when nil.
</details>

<details>
<summary>Hint 2: Making an HTTP POST with a JSON body</summary>

The pattern in Go:

```go
body, err := json.Marshal(payload)
if err != nil { ... }

req, err := http.NewRequest("POST", url, bytes.NewReader(body))
if err != nil { ... }
req.Header.Set("Content-Type", "application/json")
if token != "" {
    req.Header.Set("Authorization", "Bearer "+token)
}

client := &http.Client{Timeout: 10 * time.Second}
resp, err := client.Do(req)
```

Always check `err` after each call. Go will not remind you.
</details>

<details>
<summary>Hint 3: The ticker pattern</summary>

`time.Sleep` works but blocks the goroutine. A ticker is the standard way
to repeat something on an interval:

```go
ticker := time.NewTicker(15 * time.Second)
defer ticker.Stop()

for range ticker.C {
    sendHeartbeat()
}
```

This is the Go idiom. You'll use it for both heartbeat and polling later.
</details>

<details>
<summary>Hint 4: cpu_cores label type</summary>

The coordinator's label values accept `string | int | float | bool`. In Go
your labels map will be `map[string]interface{}`. `runtime.NumCPU()` returns
an `int`, which is fine — Go's JSON encoder will serialize it as a number.
</details>

## When you're done

You should have a working Go binary that registers and maintains a node in the
cluster. Move to Lab 04.
