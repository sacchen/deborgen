# deborgen — Project Context for Claude

## What this is

A cooperative distributed job scheduler (coordinator + worker nodes). Primary purpose right now: **educational** — building toward a portfolio piece for marketplace/allocation engineering roles.

## Where Samuel is in the learning path

**Background:** CS61A-level Python (functions, loops, recursion, HOF, scope — no classes/decorators/context managers in practice yet). Java OOP basics. Concurrency intuition from a trading exchange project (understands locks and race conditions conceptually, not Python mechanics). Brand new to Go. SQL not comfortable.

**Labs status:**

| Lab | Topic | State |
|-----|-------|-------|
| 01 | Phase A tests (Python) | In progress — blocked on pytest fixtures notebook needing rework |
| 02 | Code reading: the coordinator | Not started |
| 03 | Go worker: heartbeat | Not started |
| 04 | Go worker: job execution | Not started |
| 05 | Go worker: artifacts | Not started |
| 06 | Go worker: CLI + cross-compilation | Not started |

Full learning plan: `deborgen-labs/learning-plan.md`

## Career target

Marketplace / matching / allocation engineering — roles where allocation under scarcity is the product. Named examples: dispatch/matching at Uber/Lyft/DoorDash, GPU compute markets (SF Compute), logistics/freight, energy/grid markets. Mechanism design wearing an engineering hat, not pure OR or infra scheduling.

## Summer roadmap

| When | Work |
|---|---|
| Now → mid-June | Labs 01–02: Python, pytest, read the coordinator |
| Mid-June → July | Labs 03–06: Go worker |
| July | Lease reaper + metrics infrastructure |
| July–August | Allocation mechanisms (the portfolio piece) |

## Portfolio piece goal

Three allocation mechanisms with metrics comparing them:
1. FIFO (baseline, exists)
2. Weighted fair-share
3. Credit/accounting ledger with heterogeneous hardware pricing (GPU-hour vs CPU-hour) — this is the spike, directly relevant to compute markets

Metrics to build: queue wait time, node utilization by hardware class, Jain's fairness index, starvation detection.

## How to work with Samuel

- Frame explanations at CS61A level. Use Java analogies where helpful (self = this).
- Don't assume SQL fluency — explain queries when they come up.
- Connect distributed systems concepts to the trading exchange intuition he already has.
- Don't jump to the allocation/portfolio work — the labs must come first.

## Environment

- `uv` for dependency management — `uv sync` to install, `uv run pytest` to test
- Python 3.11, FastAPI, SQLite, pytest
- 34/34 tests pass on main
