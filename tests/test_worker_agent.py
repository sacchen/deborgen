from __future__ import annotations

import pytest

from deborgen.worker.agent import parse_labels, run_job


def test_parse_labels_accepts_json_object() -> None:
    labels = parse_labels('{"gpu":"rtx3060","cpu_cores":12}')
    assert labels["gpu"] == "rtx3060"
    assert labels["cpu_cores"] == 12


def test_parse_labels_rejects_non_object() -> None:
    with pytest.raises(ValueError):
        parse_labels('["not", "an", "object"]')


def test_parse_labels_rejects_nested_values() -> None:
    with pytest.raises(ValueError, match="must be str/int/float/bool"):
        parse_labels('{"nested": {"key": "value"}}')


def test_run_job_captures_output_and_exit_code() -> None:
    exit_code, text, failure_reason = run_job("python -c \"print('ok')\"", timeout_seconds=5)
    assert exit_code == 0
    assert "ok" in text
    assert failure_reason is None
