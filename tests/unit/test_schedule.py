"""Tests for matching and next-run computation against known cases."""

from __future__ import annotations

from datetime import datetime

import pytest

from cron_job_scheduler.schedule import (
    Scheduler,
    matches,
    next_run,
    upcoming,
)


def test_every_15_minutes_yields_quarter_hours() -> None:
    start = datetime(2025, 1, 1, 10, 7)
    runs = upcoming("*/15 * * * *", start, 4)
    assert [r.minute for r in runs] == [15, 30, 45, 0]
    assert [r.hour for r in runs] == [10, 10, 10, 11]


def test_next_run_is_strictly_after() -> None:
    on_boundary = datetime(2025, 1, 1, 10, 15)
    assert next_run("*/15 * * * *", on_boundary) == datetime(2025, 1, 1, 10, 30)


def test_weekday_9am_matches_only_weekdays() -> None:
    expr = "0 9 * * 1-5"
    # 2025-01-06 is a Monday, 2025-01-11 is a Saturday.
    assert matches(expr, datetime(2025, 1, 6, 9, 0)) is True
    assert matches(expr, datetime(2025, 1, 10, 9, 0)) is True  # Friday
    assert matches(expr, datetime(2025, 1, 11, 9, 0)) is False  # Saturday
    assert matches(expr, datetime(2025, 1, 6, 8, 0)) is False  # wrong hour


def test_next_weekday_run_skips_weekend() -> None:
    # Friday 2025-01-10 at 09:00 -> next is Monday 2025-01-13 at 09:00.
    friday = datetime(2025, 1, 10, 9, 0)
    assert next_run("0 9 * * 1-5", friday) == datetime(2025, 1, 13, 9, 0)


def test_sunday_is_zero_and_seven_equivalent() -> None:
    sunday = datetime(2025, 1, 5, 12, 0)  # a Sunday
    assert matches("* * * * 0", sunday) is True
    assert matches("* * * * 7", sunday) is True


def test_day_or_semantics() -> None:
    # Both DOM and DOW restricted -> match if EITHER holds.
    expr = "0 0 13 * 5"  # 13th OR any Friday, at midnight
    assert matches(expr, datetime(2025, 6, 13, 0, 0)) is True  # the 13th (Friday too)
    assert matches(expr, datetime(2025, 6, 6, 0, 0)) is True  # a Friday, not 13th
    assert matches(expr, datetime(2025, 6, 7, 0, 0)) is False  # Saturday, not 13th


def test_monthly_run() -> None:
    start = datetime(2025, 1, 15, 0, 0)
    runs = upcoming("30 2 1 * *", start, 2)
    assert runs == [datetime(2025, 2, 1, 2, 30), datetime(2025, 3, 1, 2, 30)]


def test_unsatisfiable_expression_raises() -> None:
    # February never has 30 days.
    with pytest.raises(ValueError):
        next_run("0 0 30 2 *", datetime(2025, 1, 1, 0, 0))


def test_scheduler_registers_and_runs_due_jobs() -> None:
    log: list[str] = []
    sched = Scheduler()
    sched.register("backup", "0 9 * * 1-5", lambda: log.append("backup"))
    sched.register("ping", "*/15 * * * *", lambda: log.append("ping"))

    monday_9 = datetime(2025, 1, 6, 9, 0)
    due = sched.due(monday_9)
    assert {j.name for j in due} == {"backup", "ping"}

    ran = sched.run_due(monday_9)
    assert ran == ["backup", "ping"]
    assert log == ["backup", "ping"]


def test_scheduler_only_due_jobs_run() -> None:
    sched = Scheduler()
    sched.register("backup", "0 9 * * 1-5", lambda: None)
    sched.register("ping", "*/15 * * * *", lambda: None)
    # 09:07 on a Monday: ping is not due (not a quarter hour), backup not due.
    assert sched.run_due(datetime(2025, 1, 6, 9, 7)) == []


def test_scheduler_duplicate_name_raises() -> None:
    sched = Scheduler()
    sched.register("a", "* * * * *", lambda: None)
    with pytest.raises(ValueError):
        sched.register("a", "* * * * *", lambda: None)


def test_scheduler_next_runs() -> None:
    sched = Scheduler()
    sched.register("ping", "*/15 * * * *", lambda: None)
    runs = sched.next_runs("ping", datetime(2025, 1, 1, 10, 0), 2)
    assert runs == [datetime(2025, 1, 1, 10, 15), datetime(2025, 1, 1, 10, 30)]
