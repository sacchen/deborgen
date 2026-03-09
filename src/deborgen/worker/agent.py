from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
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
    parser.add_argument(
        "--work-hours",
        default=None,
        help="Optional time window to accept jobs (e.g. '22:00-08:00' or '09:00-17:00')",
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
    
    # Auto-detect labels
    labels["os"] = platform.system().lower()
    labels["arch"] = platform.machine().lower()
    
    cpu_cores = os.cpu_count()
    if cpu_cores is not None:
        labels["cpu_cores"] = cpu_cores

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


def is_within_work_hours(now: datetime, work_hours_str: str | None) -> bool:
    if not work_hours_str:
        return True
        
    try:
        start_str, end_str = work_hours_str.split("-")
        start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
    except ValueError:
        print(f"[worker] warning: invalid --work-hours format '{work_hours_str}'. Expected 'HH:MM-HH:MM'. Ignoring.")
        return True
        
    current_time = now.time()
    
    if start_time < end_time:
        # e.g., 09:00 - 17:00
        return start_time <= current_time <= end_time
    else:
        # e.g., 22:00 - 08:00 (spans midnight)
        return current_time >= start_time or current_time <= end_time


def worker_loop(
    coordinator: str,
    node_id: str,
    name: str | None,
    labels: dict[str, LabelValue],
    token: str | None,
    poll_seconds: float,
    work_dir: str | None,
    heartbeat_seconds: float,
    work_hours: str | None,
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

            if not is_within_work_hours(datetime.now(), work_hours):
                time.sleep(poll_seconds)
                continue

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

            with tempfile.TemporaryDirectory(dir=work_dir) as job_work_dir:
                exit_code, log_text, failure_reason = run_job(
                    command=command,
                    timeout_seconds=timeout_seconds,
                    work_dir=job_work_dir,
                )

                # Check for artifacts
                artifacts_found = any(Path(job_work_dir).iterdir())
                
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

                if artifacts_found:
                    try:
                        zip_path = shutil.make_archive(
                            base_name=os.path.join(tempfile.gettempdir(), f"{job_id}_artifacts"),
                            format="zip",
                            root_dir=job_work_dir,
                        )
                        
                        presign_resp = client.post(
                            f"/jobs/{job_id}/artifacts/presign",
                            json={
                                "node_id": node_id,
                                "lease_token": lease_token,
                                "filename": "artifacts.zip",
                            },
                        )
                        presign_resp.raise_for_status()
                        urls = presign_resp.json()
                        upload_url = urls["upload_url"]
                        download_url = urls["download_url"]
                        
                        # Upload to S3
                        with open(zip_path, "rb") as f:
                            # Use a separate client for the S3 upload to avoid sending our Bearer token
                            upload_resp = httpx.put(upload_url, content=f, timeout=300.0)
                            upload_resp.raise_for_status()
                            
                        # Record with coordinator
                        client.post(
                            f"/jobs/{job_id}/artifacts",
                            json={
                                "node_id": node_id,
                                "lease_token": lease_token,
                                "url": download_url,
                            },
                        ).raise_for_status()
                        
                        print(f"[worker] uploaded artifacts for {job_id}")
                    except Exception as exc:
                        print(f"[worker] artifact upload failed for {job_id}: {exc}")
                    finally:
                        try:
                            if 'zip_path' in locals() and os.path.exists(zip_path):
                                os.remove(zip_path)
                        except Exception:
                            pass

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
        work_hours=args.work_hours,
    )


if __name__ == "__main__":
    main()
