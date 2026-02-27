from __future__ import annotations

import argparse
import os
import time

import httpx

TERMINAL_STATES = {"succeeded", "failed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch a deborgen job until it reaches a terminal state",
    )
    parser.add_argument("job_id", help="Job id, for example job_1")
    parser.add_argument("--coordinator", required=True, help="Coordinator base URL")
    parser.add_argument(
        "--token",
        default=os.getenv("DEBORGEN_TOKEN"),
        help="Bearer token (defaults to DEBORGEN_TOKEN)",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=1.0,
        help="Polling interval while waiting for completion",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="How long to wait before giving up",
    )
    parser.add_argument(
        "--no-logs",
        action="store_true",
        help="Do not fetch logs after the job completes",
    )
    return parser.parse_args()


def build_headers(token: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def format_summary(job: dict[str, object]) -> str:
    status = job.get("status")
    node = job.get("assigned_node_id") or "unassigned"
    exit_code = job.get("exit_code")
    return f"job={job['id']} status={status} node={node} exit_code={exit_code}"


def main() -> None:
    args = parse_args()
    coordinator = args.coordinator.rstrip("/")
    deadline = time.monotonic() + args.timeout_seconds
    headers = build_headers(args.token)

    with httpx.Client(headers=headers, timeout=30.0) as client:
        while True:
            response = client.get(f"{coordinator}/jobs/{args.job_id}")
            response.raise_for_status()
            job: dict[str, object] = response.json()
            print(format_summary(job))

            status = str(job["status"])
            if status in TERMINAL_STATES:
                if args.no_logs:
                    return

                logs_response = client.get(f"{coordinator}/jobs/{args.job_id}/logs")
                logs_response.raise_for_status()
                logs = logs_response.json()["text"]
                if logs:
                    print("")
                    print("logs:")
                    print(logs, end="" if logs.endswith("\n") else "\n")
                return

            if time.monotonic() >= deadline:
                raise SystemExit(f"timed out waiting for {args.job_id}")

            time.sleep(args.poll_seconds)
