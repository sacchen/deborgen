# Lab 06: Go Worker — CLI and Cross-Compilation

## Concept

Right now your Go code is a single `main.go`. This lab turns it into a proper
CLI binary with subcommands, then compiles it for every platform your friends
run.

The payoff: you send a friend a single file. They run it. They're in the
cluster. No Python, no `uv`, no virtual environments.

This is the thing Go is uniquely good at.

## Task

### Part 1: Subcommands

Restructure your binary to support two subcommands using the `cobra` library:

```
deborgen worker --coordinator http://... --node-id my-node
deborgen submit "echo hello" --coordinator http://...
```

`worker` is your existing Lab 03–05 implementation.

`submit` sends `POST /jobs` and prints the returned job ID. Flags:
- `--coordinator` (required)
- `--token` (optional)
- `--requirements` — JSON string, e.g. `'{"gpu":"rtx3060"}'`
- `--timeout` — integer seconds, default 3600

Add cobra to your module:
```bash
go get github.com/spf13/cobra
```

### Part 2: Cross-compilation

Write a `Makefile` (or shell script) that builds binaries for three targets:

```
bin/deborgen-linux-amd64
bin/deborgen-darwin-arm64
bin/deborgen-windows-amd64.exe
```

The environment variables `GOOS` and `GOARCH` control the target platform.
Go compiles natively across platforms with no external toolchain.

## Acceptance criteria

1. `go build -o bin/deborgen ./cmd/worker` produces a binary.

2. `./bin/deborgen worker --help` prints usage without error.

3. `./bin/deborgen submit "echo hello" --coordinator http://localhost:8000`
   prints something like `submitted job_3`.

4. `make build` (or `./build.sh`) produces all three platform binaries in
   `bin/`. Verify with `file bin/deborgen-linux-amd64` — it should say
   `ELF 64-bit` even if you're on a Mac.

5. The linux binary runs correctly on a Linux machine (your droplet). Copy it
   with `scp`, run it, confirm it registers a node in the coordinator.

## Hints

<details>
<summary>Hint 1: cobra structure</summary>

```go
var rootCmd = &cobra.Command{Use: "deborgen"}

var workerCmd = &cobra.Command{
    Use:   "worker",
    Short: "Start a worker node",
    Run: func(cmd *cobra.Command, args []string) {
        // your worker loop here
    },
}

var submitCmd = &cobra.Command{
    Use:   "submit [command]",
    Short: "Submit a job",
    Args:  cobra.ExactArgs(1),
    Run: func(cmd *cobra.Command, args []string) {
        command := args[0]
        // POST /jobs
    },
}

func init() {
    rootCmd.AddCommand(workerCmd)
    rootCmd.AddCommand(submitCmd)
    // add flags to each subcommand
}

func main() {
    rootCmd.Execute()
}
```
</details>

<details>
<summary>Hint 2: Cross-compilation Makefile</summary>

```makefile
build:
	GOOS=linux   GOARCH=amd64 go build -o bin/deborgen-linux-amd64    ./cmd/worker
	GOOS=darwin  GOARCH=arm64 go build -o bin/deborgen-darwin-arm64   ./cmd/worker
	GOOS=windows GOARCH=amd64 go build -o bin/deborgen-windows-amd64.exe ./cmd/worker
```

That's it. No Docker, no cross-compiler, no extra toolchain.
</details>

<details>
<summary>Hint 3: Making the binary smaller</summary>

By default Go binaries include debug symbols. Strip them for distribution:

```bash
go build -ldflags="-s -w" -o bin/deborgen ./cmd/worker
```

`-s` strips the symbol table, `-w` strips DWARF debug info. Typical savings:
30–40% smaller binary.
</details>

## When you're done

You have a cross-platform binary that can add any machine to the cluster
with a single file download. This is the full Go port of the Python worker.

**The capstone:** send the appropriate binary to someone with a computer and
have them join your cluster without installing anything.

---

## What's next

From here the natural directions are:

- **Streaming logs** — instead of capturing all output and uploading at the
  end, stream stdout/stderr to the coordinator in real time using goroutines
  and pipes. This is where Go's concurrency model gets interesting.

- **Work hours** — port the `--work-hours` flag and `is_within_work_hours`
  logic. Go's `time.Parse("15:04", ...)` is the equivalent of Python's
  `datetime.strptime`.

- **Phase 4 of the roadmap** — the system is working. Start using it for
  real workloads and see what breaks.
