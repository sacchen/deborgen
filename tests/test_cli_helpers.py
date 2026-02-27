from __future__ import annotations

import argparse

import pytest

from deborgen.cli.list_jobs import parse_limit
from deborgen.cli.submit_example import print_follow_up


def test_parse_limit_accepts_valid_range() -> None:
    assert parse_limit("1") == 1
    assert parse_limit("1000") == 1000


@pytest.mark.parametrize("value", ["0", "-1", "1001"])
def test_parse_limit_rejects_out_of_range(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parse_limit(value)


def test_print_follow_up_uses_env_token_placeholder_when_token_came_from_env(
    capsys: pytest.CaptureFixture[str],
) -> None:
    print_follow_up(
        job_id="job_1",
        coordinator="http://coord:8000",
        token_from_env=True,
    )
    output = capsys.readouterr().out
    assert '--token "$DEBORGEN_TOKEN"' in output


def test_print_follow_up_omits_placeholder_when_token_was_not_from_env(
    capsys: pytest.CaptureFixture[str],
) -> None:
    print_follow_up(
        job_id="job_1",
        coordinator="http://coord:8000",
        token_from_env=False,
    )
    output = capsys.readouterr().out
    assert '--token "$DEBORGEN_TOKEN"' not in output
