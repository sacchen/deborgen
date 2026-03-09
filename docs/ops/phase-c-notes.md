# Phase C: Safe Participation (Node Rules)

## Goal
Make it safe and completely hands-off for friends to volunteer their personal machines (gaming PCs, laptops) by allowing them to define *when* their machines accept work. 

If someone is using their machine during the day, it shouldn't pull heavy jobs and ruin their experience. We will achieve this through **Time-of-Day Schedules**.

## Strategy

### 1. Time-of-Day Schedules (`--work-hours`)
- Add a new command-line argument to `src/deborgen/worker/agent.py` called `--work-hours` (e.g., `--work-hours "22:00-08:00"`).
- Implement a helper function `is_within_work_hours(current_time, work_hours_str)` that handles spanning across midnight.
- In the `worker_loop`, evaluate this check before making the HTTP `GET /jobs/next` call. 
- If the worker is outside its permitted hours, it will skip polling and just `time.sleep()`.
- **Crucial detail:** The worker should *still send heartbeats* even when outside work hours, so the coordinator knows the node is online but currently "resting."

### 2. Educational Notes

#### Why skip polling but keep heartbeating?
If a worker simply dies or disconnects during its "quiet hours," the cluster loses visibility into the total available capacity. By skipping the `GET /jobs/next` call but continuing to execute `POST /nodes/{id}/heartbeat`, the coordinator knows the machine is alive, properly configured, and will eventually return to the pool. This is useful for future features like forecasting ("Job X will wait until 22:00 because 5 machines are resting").

#### Spanning Midnight Logic
A naive time check like `start <= current <= end` fails when dealing with overnight schedules (e.g., 10 PM to 8 AM). If the start time is numerically greater than the end time, it implies the window crosses midnight, meaning the valid time is either *after* the start time OR *before* the end time.

## Progress
- [x] Create plan.
- [x] Add time parsing logic to `agent.py`.
- [x] Update `worker_loop` to respect work hours.
- [x] Add unit tests for the time boundary logic.
- [x] Update documentation to highlight the new safe participation feature.
