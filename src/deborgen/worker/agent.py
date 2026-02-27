from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import time
from typing import Any

import httpx

LabelValue = str | int | float | bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="deborgen v0 worker agent")
    parser.add_argument("--coordinator", required=True, help="Coordinator base URL")
    parser.add_argument("--node-id", required=True, help="Worker node ID")
    parser.add_argument("--name", default=None, help="Optional human-readable node name")
    parser.add_argument(
        "--labels-json",
        default="{}",
        help='Node labels as a JSON object, e.g. \'{"gpu":"rtx3060","cpu_cores":12}\'',
    )
    parser.add_argument("--token", default=None, help="Bearer token")
    parser.add_argument("--poll-seconds", type=float, default=2.0, help="Poll interval when queue is empty")
    parser.add_argument(
        "--work-dir",
        default=None,
        help="Optional working directory for executed jobs",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=15.0,
        help="Heartbeat interval",
    )
    return parser.parse_args()


def run_job(
    command: str,
    timeout_seconds: int,
    work_dir: str | None = None,
) -> tuple[int, str, str | None]:
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return 2, "", f"invalid command: {exc}"

    if not argv:
        return 2, "", "invalid command: empty command"

    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=work_dir,
        )
        text = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode, text, None
    except FileNotFoundError:
        return 127, "", f"command not found: {argv[0]}"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        output = stdout + stderr
        return 124, output, f"timeout exceeded ({timeout_seconds}s)"


def parse_labels(labels_json: str) -> dict[str, LabelValue]:
    parsed = json.loads(labels_json)
    if not isinstance(parsed, dict):
        raise ValueError("--labels-json must decode to an object")

    labels: dict[str, LabelValue] = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            raise ValueError("--labels-json keys must be strings")
        if not isinstance(value, (str, int, float, bool)):
            raise ValueError(
                f"--labels-json value for '{key}' must be str/int/float/bool"
            )
        labels[key] = value
    return labels


def send_heartbeat(client: httpx.Client, node_id: str, name: str | None, labels: dict[str, LabelValue]) -> None:
    client.post(
        f"/nodes/{node_id}/heartbeat",
        json={
            "name": name,
            "labels": labels,
        },
    ).raise_for_status()


def worker_loop(
    coordinator: str,
    node_id: str,
    name: str | None,
    labels: dict[str, LabelValue],
    token: str | None,
    poll_seconds: float,
    work_dir: str | None,
    heartbeat_seconds: float,
) -> None:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(base_url=coordinator.rstrip("/"), headers=headers, timeout=30.0) as client:
        next_heartbeat = 0.0
        while True:
            now = time.monotonic()
            if now >= next_heartbeat:
                try:
                    send_heartbeat(client=client, node_id=node_id, name=name, labels=labels)
                except httpx.HTTPError as exc:
                    print(f"[worker] heartbeat failed: {exc}")
                next_heartbeat = now + heartbeat_seconds

            try:
                response = client.get("/jobs/next", params={"node_id": node_id})
            except httpx.HTTPError as exc:
                print(f"[worker] poll failed: {exc}")
                time.sleep(poll_seconds)
                continue

            if response.status_code == 204:
                time.sleep(poll_seconds)
                continue

            if response.status_code != 200:
                print(f"[worker] poll returned {response.status_code}: {response.text}")
                time.sleep(poll_seconds)
                continue

            payload: dict[str, Any] = response.json()
            job: dict[str, Any] = payload["job"]
            lease_token = payload["lease_token"]

            job_id = str(job["id"])
            command = str(job["command"])
            timeout_seconds = int(job.get("timeout_seconds", 3600))
            print(f"[worker] running {job_id}: {command}")

            exit_code, log_text, failure_reason = run_job(
                command=command,
                timeout_seconds=timeout_seconds,
                work_dir=work_dir,
            )

            if log_text:
                try:
                    client.post(
                        f"/jobs/{job_id}/logs",
                        json={
                            "node_id": node_id,
                            "lease_token": lease_token,
                            "text": log_text,
                        },
                    ).raise_for_status()
                except httpx.HTTPError as exc:
                    print(f"[worker] log upload failed for {job_id}: {exc}")

            try:
                client.post(
                    f"/jobs/{job_id}/finish",
                    json={
                        "node_id": node_id,
                        "lease_token": lease_token,
                        "exit_code": exit_code,
                        "failure_reason": failure_reason,
                    },
                ).raise_for_status()
                print(f"[worker] finished {job_id} exit_code={exit_code}")
            except httpx.HTTPError as exc:
                print(f"[worker] finish failed for {job_id}: {exc}")


def main() -> None:
    args = parse_args()
    labels = parse_labels(args.labels_json)
    worker_loop(
        coordinator=args.coordinator,
        node_id=args.node_id,
        name=args.name,
        labels=labels,
        token=args.token,
        poll_seconds=args.poll_seconds,
        work_dir=args.work_dir,
        heartbeat_seconds=args.heartbeat_seconds,
    )


if __name__ == "__main__":
    main()
