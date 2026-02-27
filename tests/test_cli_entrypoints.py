from __future__ import annotations

import subprocess


def run_help(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", command, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )


def test_coordinator_cli_help() -> None:
    result = run_help("deborgen-coordinator")
    assert result.returncode == 0
    assert "deborgen v0 coordinator" in result.stdout


def test_worker_cli_help() -> None:
    result = run_help("deborgen-worker")
    assert result.returncode == 0
    assert "deborgen v0 worker agent" in result.stdout
