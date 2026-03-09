# Ops Notes (2026-02-28): Shared Droplet Efficiency Pass

This note records the low-risk changes made on the shared production droplet to reduce wasted CPU and improve stability without taking live sites down.

## Goal

- reduce unnecessary load
- reduce crash-loop churn
- add basic memory safety margin
- avoid breaking production traffic

## Starting State

- Host: `ubuntu-s-1vcpu-1gb-35gb-intel-sfo3-01`
- RAM: `1.9 GiB`
- Swap: `0B`
- Disk (`/`): about `33G` total, about `18G` used
- The box was already running multiple long-lived Node applications under `PM2`.
- Initial load average was roughly:
  - `2.16` (1 minute)
  - `2.24` (5 minute)
  - `2.33` (15 minute)

On a single-vCPU host, that indicated sustained CPU contention.

## What We Changed

### 1. Added Swap

Added a `2G` swapfile and enabled it immediately.

Commands used:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swap.conf
echo 'vm.vfs_cache_pressure=50' | sudo tee -a /etc/sysctl.d/99-swap.conf
sudo sysctl --system
```

Post-change verification:

- `free -h` showed `2.0 GiB` swap available.
- `swapon --show` confirmed `/swapfile` was active.
- `vmstat 2 5` showed no active swap-in or swap-out, so the box was not immediately thrashing.

Purpose:

- This does not make the server faster by itself.
- It reduces OOM risk and gives the system a safer fallback under memory pressure.

### 2. Stopped Two PM2 Crash Loops

We inspected `PM2` and found two applications with extremely high restart counts:

- `2048chan`
  - restarts: about `8,017,477`
  - uptime: `0s`
  - error: repeated `EADDRINUSE` on port `5002`
- `pactnexus`
  - restarts: about `1,176,712`
  - uptime: `1s`
  - error: repeated startup failure from `path-to-regexp`

We then confirmed both ports were already in use by other processes:

```bash
ss -lntp | egrep ':5001|:5002'
```

Observed listeners:

- `5002` already served by Node PID `1548526`
- `5001` already served by Node PID `2062511`

We also verified both local endpoints were healthy before changing anything:

```bash
curl -I http://127.0.0.1:5002
curl -I http://127.0.0.1:5001
```

Both returned `HTTP/1.1 200 OK`.

Because the live ports were already being served by other processes, the PM2 entries above were not the active serving instances. They were only burning CPU by restarting repeatedly.

We stopped the broken PM2 entries:

```bash
pm2 stop 2048chan
pm2 stop pactnexus
```

Then re-ran the same `curl -I` checks for `5001` and `5002`.

Result:

- both endpoints still returned `200 OK`
- live traffic was unaffected
- the crash-looping PM2 processes were no longer consuming resources

## Outcome

After stopping the two crash loops:

- the 1-minute load average dropped from roughly `2.16` to `0.90`
- the obvious high-CPU churn disappeared from the process list
- production endpoints on ports `5001` and `5002` remained healthy

This indicates the restart loops were a major source of unnecessary load.

## Important Notes

- We did **not** delete the PM2 app definitions.
- We only used `pm2 stop`, which keeps the change easy to reverse.
- If needed, the previous PM2 behavior can be restored with:

```bash
pm2 restart 2048chan
pm2 restart pactnexus
```

- We did **not** change nginx, systemd service definitions, application code, or firewall settings.
- We did **not** shut down the live processes already serving ports `5001` and `5002`.

## Recommended Follow-Up

Low-risk next step:

```bash
pm2 save
```

Reason:

- This preserves the current PM2 state so the two stopped entries do not come back as active after a PM2 resurrect/reload event.

This is still relatively safe because the entries remain in PM2 and can be restarted manually later if needed.

## Remaining Questions

The live listeners on ports `5001` and `5002` are still running, but they are not the PM2 processes we stopped. That means there is still some process-management ambiguity on the host.

Specifically, it is still worth identifying:

- what owns PID `1548526`
- what owns PID `2062511`
- whether those processes are manually started, wrapped by another parent process, or managed outside PM2

That is a cleanup task for later. It was intentionally left untouched today to avoid production risk.

## Summary

Today’s work was intentionally conservative:

- added swap for resilience
- identified two non-serving PM2 crash loops
- stopped those loops
- verified live sites still worked
- reduced load without changing the production serving processes

This was the highest-value low-risk efficiency improvement available on the shared droplet.
