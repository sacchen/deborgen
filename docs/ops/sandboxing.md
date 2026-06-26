# Sandboxing: Goals, Options, and Tradeoffs

## Context

deborgen is a cooperative distributed job scheduler. Contributors share compute by running worker nodes on their own machines. The coordinator dispatches jobs to workers, which execute arbitrary commands submitted by job submitters.

Currently the worker has no sandboxing: `run_job` calls `subprocess.run` (Python) / `exec.Command` (Go) directly. A submitted job runs with the same OS privileges as the worker process.

---

## The core contributor concern

Contributors are unwilling to contribute compute if arbitrary code runs with full access to their machine. Specifically they fear:

- **File access** — jobs reading `~/Documents`, SSH keys, browser passwords
- **Network abuse** — jobs phoning home, hitting internal services, participating in botnets
- **Persistence** — jobs installing software, modifying startup entries, creating backdoors
- **Resource abuse** — jobs mining crypto, saturating CPU/RAM, filling disk
- **Damage** — jobs deleting or corrupting files

These are distinct threats. No single mechanism addresses all of them, but most can be mitigated without exotic tooling.

---

## Expected deployment reality

- **Majority of worker nodes are Windows** (contributor-owned, likely Windows Home)
- Workers also expected on macOS and Linux
- Contributors are friends contributing spare compute — high onboarding friction will kill participation
- The Go rewrite is planned; any sandboxing design should target the Go worker
- **Jobs are primarily Python** — ML training (PyTorch, RL), data analysis, simulation
- First major workloads include RL research (reproducing "Scaling Scaling Laws in Board Games") and scientific computing
- GPU access is required for serious ML workloads

---

## Options

### 1. Dedicated OS user + ACLs (low friction, cross-platform)

Create a restricted `deborgen` OS user at install time. Worker runs as that user. The user has:

- No access to the contributor's home directory
- Write access only to a designated work directory
- No ability to modify startup entries or install software

Resource limits via platform primitives (Job Objects on Windows, `ulimit`/cgroups on Linux/macOS).

**This directly addresses the core contributor fear on all three platforms without Docker.**

### 2. Docker containers (medium friction, strong isolation)

Job submissions include an image field. Worker pulls the image and runs the command inside a container with `--network none` and no host mounts by default.

On macOS and Windows, Docker Desktop runs a Linux VM — real hypervisor boundary, strong isolation. On Linux, container and host share the kernel (weaker, but sufficient for the threat model).

### 3. Platform-specific native sandboxing (high complexity, inconsistent quality)

Ship separate sandbox backends per platform:

- Linux: `bubblewrap` or `nsjail` + seccomp + landlock
- macOS: `sandbox-exec` (deprecated)
- Windows: AppContainer

Strong on Linux, weak on macOS/Windows — which is backwards given the Windows-majority contributor base.

### 4. WebAssembly / Wasmtime (not viable as primary model; promising as a second tier)

Running jobs inside a Wasm runtime (e.g. Wasmtime) provides strong, intrinsic isolation — the sandbox is the execution model, not a wrapper around it. Hardware can be exposed through controlled APIs (WGPU for GPU, SIMD for vectorized compute). Jobs would be compiled Wasm modules rather than shell commands.

The appeal is structural: the sandbox isn't a policy enforced by configuration, it's a property of the execution model. A contributor doesn't have to trust that the scheduler is correctly configured — the module physically cannot reach outside the runtime without an explicit capability grant.

**Why this doesn't work as the primary model:**

- PyTorch, JAX, and most ML libraries have no Wasm builds and no roadmap for one
- Pyodide (CPython compiled to Wasm) exists but excludes the entire ML stack — PyTorch is not available, Gymnasium and RL libraries are not available
- The job model changes fundamentally — "submit a shell command" becomes "submit a compiled module," which breaks the existing architecture and requires job submitters to compile to Wasm

**Why it could work as a second tier:**

Rust-native ML frameworks do compile to Wasm and are maturing:

- **Burn** — full training framework with a WGPU backend for GPU
- **Candle** (Hugging Face) — primarily inference, Wasm support exists
- **LiteRT** (formerly TensorFlow Lite) — inference only

A two-tier model is worth considering: Tier 1 for trusted Python/PyTorch jobs (restricted OS user or Docker), Tier 2 for fully arbitrary Wasm modules with intrinsic isolation. Contributors who want structural guarantees rather than policy-based ones could require Tier 2.

**Note on contributor fit:** Burn/Candle require writing Rust, not Python. The Wasm path is most attractive to Rust developers. For a Python-majority user base, Tier 2 would serve a small subset of contributors rather than the general case.

### 5. No sandboxing (current state)

Operator is responsible. Acceptable for trusted internal deployments, not for volunteer compute.

---

## What to consider

**Onboarding friction vs. isolation strength**
Every step up the isolation ladder adds setup steps. Docker requires installation, a running daemon, and a license on Windows. A restricted OS user requires running a setup script once. Each friction point loses contributors.

**Windows Home is a real constraint**
Docker Desktop requires Hyper-V, which requires Windows Pro/Enterprise, or WSL2 on Windows 11. Many contributor machines will not qualify. Any solution that requires Docker as a hard dependency excludes a significant portion of the contributor base.

**The threat model is "trusted submitters, untrusted execution environment"**
Contributors trust that job submitters (their friends) aren't sending malicious images or commands. The concern is accidental damage and resource abuse, not sophisticated adversarial attacks. This lowers the bar — a restricted user account is meaningful protection for this threat model.

**Docker is not a kernel boundary on Linux**
On Linux, containers share the host kernel. A kernel exploit breaks containment. For volunteer compute on personal machines, this is an acceptable risk — it's not a realistic casual threat.

**The Go rewrite creates a clean implementation opportunity**
`SysProcAttr` in Go's `os/exec` gives direct access to Linux namespace primitives. The Docker SDK is written in Go. A `Sandbox` interface with platform-specific backends is natural in Go and would be awkward in Python.

**Sandboxing should be a worker capability, not a global requirement**
Contributors have different risk tolerances and different machines. A tiered capability system lets the coordinator match jobs to appropriately sandboxed workers rather than blocking everyone on the weakest common denominator.

---

## Key insight

PyTorch and JAX are deeply native — CUDA kernels, C++ extensions, direct hardware access. Any sandboxing that intercepts or virtualizes at a layer *below* that breaks the stack. The only isolation boundary that doesn't interfere with how these libraries work is one that sits *outside* the entire runtime — a VM or a container.

That points at Docker. But Docker on Windows with CUDA requires WSL2 + Docker Desktop + NVIDIA Container Toolkit, which is real onboarding complexity for contributors with gaming PCs who haven't run ML workloads before.

**The core tension:** there is no clean general-purpose solution for sandboxed arbitrary Python + GPU on Windows. Something always loses — either sandboxing is weaker, onboarding is harder, or Python/GPU support is dropped. This is a genuine constraint, not a gap in the research.

---

## Tradeoffs summary

| Option | Windows Home | Onboarding | Isolation quality | Python/GPU support | Complexity |
|---|---|---|---|---|---|
| Dedicated OS user | Yes | Low (one-time script) | Moderate | Full | Low |
| Docker | Requires Pro/Enterprise or Win11+WSL2 | High | Strong | Full + CUDA | Medium |
| Platform-specific | Yes | Medium | Inconsistent | Full | High |
| Wasm | Yes (but Python/GPU not viable) | Medium | Strong | No PyTorch/GPU | High |
| None | Yes | None | None | Full | None |

---

## Tentative direction

No fully clean solution exists. The options below reflect pragmatic tradeoffs given the real constraints.

### Option A — Dedicated OS user as the baseline (recommended near-term)

Install script creates a restricted `deborgen` user. Worker runs as that user. Job Objects (Windows) or ulimit (Linux/macOS) handle resource limits. GPU works natively — no Docker, no WSL2, no NVIDIA Container Toolkit.

- Lowest onboarding friction for Windows gaming PC contributors
- GPU access works out of the box
- Sandboxing is meaningful (files protected, resource limits enforced) but not a container boundary
- Gets contributors running fastest

The coordinator can advertise this as: *"Jobs run as a restricted user with no access to your home directory, killed after timeout."*

### Option B — Docker as an opt-in upgrade

Workers that have Docker + NVIDIA Container Toolkit available advertise it as a capability. Contributors who want stronger isolation and have already set up the Docker/WSL2/NVIDIA stack can opt in. Not a requirement.

Full setup requires: WSL2 + Docker Desktop + NVIDIA Container Toolkit. Significant one-time effort for contributors who haven't done ML setup before.

### Capability advertisement

Workers report their sandbox level via node labels:

```json
{ "sandbox": "os_user" }
{ "sandbox": "docker" }
{ "sandbox": "none" }
```

Job submitters can require a minimum sandbox level. Supply meets demand without blocking anyone.

---

## Longer-term design directions

### Job type registry

A contributor raised the idea of a **public registry of job types** — versioned, declared-permission compute tasks that contributors can inspect and trust before opting in. This sits between two extremes:

- **Fully arbitrary** — job submitters upload anything, contributors must trust the sandbox entirely
- **BOINC-style opt-in** — contributors manually vet each project they participate in

A registry with a trust layer (verified publishers, community review, declared permissions) could give contributors confidence without requiring them to review every job individually. Contributors set a policy ("run anything from verified publishers") rather than making per-job decisions. Job submitters publish task types to the registry rather than submitting arbitrary commands.

This maps naturally onto deborgen's coordinator — task types become a first-class concept alongside jobs. The registry could be hosted centrally or be decentralized.

**Contrast with peer-to-peer arbitrary compute** (Golem, Akash) where there is no registry, no trust chain, and isolation must be entirely structural. That's a fundamentally different system with different tradeoffs — trustless but complex.

This direction is worth revisiting if deborgen grows beyond a small trusted network.

### Docker on Windows with CUDA

Docker on Windows is technically accessible (WSL2 ships with Windows 11 Home, Docker Desktop is free for personal use), but GPU passthrough adds real complexity:

- WSL2 required as the Docker backend
- NVIDIA Container Toolkit must be installed separately
- Virtualization must be enabled in BIOS (off by default on some machines)

For contributors with gaming PCs who haven't done ML setup before, this is a significant one-time burden. It is not a hard blocker for motivated contributors, but it will lose some people. **Podman Desktop** and **Rancher Desktop** are free Docker alternatives but don't reduce the NVIDIA/WSL2 complexity.

---

## Discussion archive

The design decisions in this document grew out of an extended conversation covering sandboxing mechanisms, platform constraints, Wasm viability, and job trust models. Full archive: https://gisthost.github.io/?bf73e28ffa73777101f476ac45fdd972/index.html

---

## Open questions for deeper dive

- What does the Windows install script look like? MSI vs. PowerShell script vs. something else.
- What ACLs does the `deborgen` user need? Work directory only, or also temp?
- Should the worker refuse to start if not running as the restricted user?
- What Job Object limits are reasonable defaults (CPU %, RAM, wall time)?
- How does the Docker path handle image caching to avoid pull latency on every job?
- Should `sandbox` be a hard job requirement or a preference with fallback?
- How does GPU passthrough work in Docker on Windows (NVIDIA Container Toolkit)?
- Can contributors on Windows Home get GPU access at all without Docker? GPU contributors are particularly valuable for ML workloads — losing them to Docker friction is a real cost.
- Is a two-tier job model (trusted Python + arbitrary Wasm) worth the architectural complexity? How mature are Burn/Candle for real RL research workloads?
- Do contributors want structural isolation guarantees (Wasm) or is policy-based isolation (restricted OS user, Docker) acceptable?
