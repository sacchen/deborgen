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


def test_get_job_cli_help() -> None:
    result = run_help("deborgen-get-job")
    assert result.returncode == 0
    assert "Show details for one deborgen job" in result.stdout


def test_list_jobs_cli_help() -> None:
    result = run_help("deborgen-list-jobs")
    assert result.returncode == 0
    assert "List recent deborgen jobs" in result.stdout


def test_submit_example_cli_help() -> None:
    result = run_help("deborgen-submit-example")
    assert result.returncode == 0
    assert "Submit a built-in deborgen example job" in result.stdout


def test_watch_job_cli_help() -> None:
    result = run_help("deborgen-watch-job")
    assert result.returncode == 0
    assert "Watch a deborgen job until it reaches a terminal state" in result.stdout


def test_tutorial_cli_help() -> None:
    result = run_help("deborgen-tutorial")
    assert result.returncode == 0
    assert "Run the deborgen onboarding tutorial sequence" in result.stdout
