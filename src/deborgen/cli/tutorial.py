from __future__ import annotations

import argparse
import os

from deborgen.cli.submit_example import EXAMPLE_COMMANDS, submit_example_job
from deborgen.cli.watch_job import watch_job

DEFAULT_SEQUENCE = ("hello", "primes")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deborgen onboarding tutorial sequence",
    )
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
        default=60.0,
        help="Per-job timeout while waiting for completion",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    coordinator = args.coordinator.rstrip("/")

    print("starting deborgen tutorial")
    for example in DEFAULT_SEQUENCE:
        print("")
        print(f"submitting example={example}")
        print(f"command={EXAMPLE_COMMANDS[example]}")
        job_id, _ = submit_example_job(
            coordinator=coordinator,
            example=example,
            token=args.token,
            timeout_seconds=int(args.timeout_seconds),
            max_attempts=1,
        )
        print(f"submitted {job_id}")
        watch_job(
            coordinator=coordinator,
            job_id=job_id,
            token=args.token,
            poll_seconds=args.poll_seconds,
            timeout_seconds=args.timeout_seconds,
            include_logs=True,
        )

    print("")
    print("tutorial complete")
