# Server Profile

This repo is currently being worked on from a small production-adjacent droplet.

- RAM: 2 GB
- Swap: 2 GB
- CPU: x86_64 (Intel-class VPS)
- Disk: 70 GB droplet class (current root filesystem is about 67 GB)

# Current Layout

- Production-oriented checkout: `/home/dev/deborgen`
- Dev checkout for Codex work: `/home/dev/deborgen-dev`
- The deborgen coordinator is already managed by `systemd` and runs from `/home/dev/deborgen`
- The worker should stay off during Codex sessions

# Safe Usage

- Use Codex, editing, inspection, and light git work in `/home/dev/deborgen-dev`
- Leave the running coordinator alone unless you are intentionally doing service work
- Treat heavier tasks cautiously on this machine: large test runs, dependency installs, builds, and multiple concurrent services can add pressure quickly on a 2 GB host
- If you need to start the worker, do it only when you are not actively using Codex for a longer session
