from __future__ import annotations

import argparse
import os
from typing import Any

import httpx


def parse_limit(value: str) -> int:
    limit = int(value)
    if limit < 1 or limit > 1000:
        raise argparse.ArgumentTypeError("--limit must be between 1 and 1000")
    return limit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List recent deborgen jobs",
    )
    parser.add_argument("--coordinator", required=True, help="Coordinator base URL")
    parser.add_argument(
        "--token",
        default=os.getenv("DEBORGEN_TOKEN"),
        help="Bearer token (defaults to DEBORGEN_TOKEN)",
    )
    parser.add_argument(
        "--status",
        choices=("queued", "running", "succeeded", "failed"),
        default=None,
        help="Optional status filter",
    )
    parser.add_argument(
        "--limit",
        type=parse_limit,
        default=10,
        help="Maximum number of jobs to list",
    )
    return parser.parse_args()


def build_headers(token: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def format_job(job: dict[str, Any]) -> str:
    node = job.get("assigned_node_id") or "unassigned"
    return (
        f"{job['id']} status={job['status']} node={node} "
        f"attempts={job['attempts']}/{job['max_attempts']} command={job['command']}"
    )


def main() -> None:
    args = parse_args()
    coordinator = args.coordinator.rstrip("/")
    headers = build_headers(args.token)
    params: dict[str, str | int] = {"limit": args.limit}
    if args.status:
        params["status"] = args.status

    with httpx.Client(headers=headers, timeout=30.0) as client:
        response = client.get(f"{coordinator}/jobs", params=params)
        response.raise_for_status()

    payload = response.json()
    jobs = payload["jobs"]
    if not jobs:
        print("no jobs found")
        return

    for job in jobs:
        print(format_job(job))
