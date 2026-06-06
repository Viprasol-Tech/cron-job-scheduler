"""Tests for cron expression parsing against known field expansions."""

from __future__ import annotations

import pytest

from cron_job_scheduler.parser import CronParseError, parse


def test_wildcard_minute_expands_full_range() -> None:
    expr = parse("* * * * *")
    assert expr.minute.values == frozenset(range(0, 60))
    assert expr.hour.values == frozenset(range(0, 24))
    assert expr.dom.values == frozenset(range(1, 32))
    assert expr.month.values == frozenset(range(1, 13))
    assert expr.dow.values == frozenset(range(0, 7))


def test_step_field() -> None:
    expr = parse("*/15 * * * *")
    assert sorted(expr.minute.values) == [0, 15, 30, 45]


def test_list_field() -> None:
    expr = parse("1,2,3 * * * *")
    assert sorted(expr.minute.values) == [1, 2, 3]


def test_range_field() -> None:
    expr = parse("0 9 * * 1-5")
    assert sorted(expr.dow.values) == [1, 2, 3, 4, 5]
    assert sorted(expr.hour.values) == [9]


def test_range_with_step() -> None:
    expr = parse("10-30/5 * * * *")
    assert sorted(expr.minute.values) == [10, 15, 20, 25, 30]


def test_combined_list_range_step() -> None:
    expr = parse("0,30,45-50 * * * *")
    assert sorted(expr.minute.values) == [0, 30, 45, 46, 47, 48, 49, 50]


def test_dow_seven_normalizes_to_sunday() -> None:
    expr = parse("* * * * 7")
    assert 0 in expr.dow.values
    assert 7 not in expr.dow.values


@pytest.mark.parametrize(
    "bad",
    [
        "* * * *",  # too few fields
        "* * * * * *",  # too many fields
        "60 * * * *",  # minute out of range
        "* 24 * * *",  # hour out of range
        "* * 0 * *",  # day-of-month below 1
        "* * * 13 *",  # month out of range
        "* * * * 8",  # dow above 7
        "5-1 * * * *",  # inverted range
        "*/0 * * * *",  # zero step
        "a * * * *",  # non-numeric
        "",  # empty
    ],
)
def test_invalid_expressions_raise(bad: str) -> None:
    with pytest.raises(CronParseError):
        parse(bad)
