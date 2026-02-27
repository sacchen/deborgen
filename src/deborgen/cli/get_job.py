from __future__ import annotations

import argparse
import os
from typing import Any

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show details for one deborgen job",
    )
    parser.add_argument("job_id", help="Job id, for example job_1")
    parser.add_argument("--coordinator", required=True, help="Coordinator base URL")
    parser.add_argument(
        "--token",
        default=os.getenv("DEBORGEN_TOKEN"),
        help="Bearer token (defaults to DEBORGEN_TOKEN)",
    )
    return parser.parse_args()


def build_headers(token: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def print_job(job: dict[str, Any]) -> None:
    fields = (
        "id",
        "status",
        "command",
        "assigned_node_id",
        "created_at",
        "started_at",
        "finished_at",
        "timeout_seconds",
        "attempts",
        "max_attempts",
        "exit_code",
        "failure_reason",
    )
    for field in fields:
        print(f"{field}: {job.get(field)}")


def main() -> None:
    args = parse_args()
    coordinator = args.coordinator.rstrip("/")
    headers = build_headers(args.token)

    with httpx.Client(headers=headers, timeout=30.0) as client:
        response = client.get(f"{coordinator}/jobs/{args.job_id}")
        response.raise_for_status()

    print_job(response.json())
