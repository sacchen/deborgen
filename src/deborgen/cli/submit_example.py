from __future__ import annotations

import argparse
import os
from typing import Any

import httpx

EXAMPLE_COMMANDS: dict[str, str] = {
    "hello": "uv run python examples/01_hello_worker.py",
    "primes": "uv run python examples/02_count_primes.py",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit a built-in deborgen example job",
    )
    parser.add_argument(
        "example",
        choices=sorted(EXAMPLE_COMMANDS),
        help="Which example job to submit",
    )
    parser.add_argument("--coordinator", required=True, help="Coordinator base URL")
    parser.add_argument(
        "--token",
        default=os.getenv("DEBORGEN_TOKEN"),
        help="Bearer token (defaults to DEBORGEN_TOKEN)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3600,
        help="Job timeout passed to the coordinator",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=1,
        help="Maximum attempts passed to the coordinator",
    )
    return parser.parse_args()


def build_headers(token: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def build_job_request(example: str, timeout_seconds: int, max_attempts: int) -> dict[str, Any]:
    return {
        "command": EXAMPLE_COMMANDS[example],
        "timeout_seconds": timeout_seconds,
        "max_attempts": max_attempts,
    }


def print_follow_up(job_id: str, coordinator: str, token: str | None) -> None:
    print(f"submitted {job_id}")
    watch_cmd = f"uv run deborgen-watch-job {job_id} --coordinator {coordinator}"
    if token:
        watch_cmd += " --token \"$DEBORGEN_TOKEN\""
    print(f"watch: {watch_cmd}")


def main() -> None:
    args = parse_args()
    coordinator = args.coordinator.rstrip("/")
    headers = build_headers(args.token)
    payload = build_job_request(
        example=args.example,
        timeout_seconds=args.timeout_seconds,
        max_attempts=args.max_attempts,
    )

    with httpx.Client(headers=headers, timeout=30.0) as client:
        response = client.post(f"{coordinator}/jobs", json=payload)
        response.raise_for_status()

    job = response.json()
    job_id = str(job["id"])
    print(f"example={args.example}")
    print(f"command={payload['command']}")
    print_follow_up(job_id=job_id, coordinator=coordinator, token=args.token)
