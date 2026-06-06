"""Match datetimes against cron expressions and compute next run times.

This module turns a parsed :class:`~cron_job_scheduler.parser.CronExpression`
into useful behaviour:

- :func:`matches` — does a given ``datetime`` satisfy the expression?
- :func:`next_run` — the next ``datetime`` strictly after a reference time
  that satisfies the expression.
- :class:`Scheduler` — a small in-memory registry that maps cron expressions
  to callables and reports which jobs are due at a given time.

Day-of-month and day-of-week are combined with cron's classic OR semantics:
when **both** are restricted (neither is ``*``), a datetime matches if *either*
field matches. When one is ``*``, only the other constrains the day.

Python's ``datetime.weekday()`` returns Monday=0..Sunday=6; cron uses
Sunday=0..Saturday=6. :func:`_cron_weekday` converts between them.

Part of Cron Job Scheduler by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from cron_job_scheduler.parser import CronExpression, parse

__all__ = ["Job", "Scheduler", "matches", "next_run"]

# Upper bound on minutes to scan forward before giving up (~4 years), so an
# impossible expression like "0 0 30 2 *" raises instead of looping forever.
_MAX_MINUTES = 4 * 366 * 24 * 60


def _cron_weekday(dt: datetime) -> int:
    """Return the cron day-of-week (Sunday=0..Saturday=6) for ``dt``."""
    # Python: Monday=0..Sunday=6 -> cron: Sunday=0..Saturday=6.
    return (dt.weekday() + 1) % 7


def _day_matches(expr: CronExpression, dt: datetime) -> bool:
    """Apply cron's OR semantics between day-of-month and day-of-week."""
    dom_restricted = expr.dom.values != frozenset(range(expr.dom.low, expr.dom.high + 1))
    dow_restricted = expr.dow.values != frozenset(range(expr.dow.low, expr.dow.high + 1))
    dom_ok = expr.dom.matches(dt.day)
    dow_ok = expr.dow.matches(_cron_weekday(dt))

    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def matches(expression: str | CronExpression, dt: datetime) -> bool:
    """Return ``True`` if ``dt`` satisfies the cron ``expression``.

    Seconds and microseconds are ignored — cron has minute resolution.

    Args:
        expression: A cron string or a pre-parsed :class:`CronExpression`.
        dt: The datetime to test.

    Returns:
        Whether all cron fields match ``dt`` (with day OR semantics).
    """
    expr = expression if isinstance(expression, CronExpression) else parse(expression)
    return (
        expr.minute.matches(dt.minute)
        and expr.hour.matches(dt.hour)
        and expr.month.matches(dt.month)
        and _day_matches(expr, dt)
    )


def next_run(expression: str | CronExpression, after: datetime) -> datetime:
    """Compute the next datetime strictly after ``after`` matching ``expression``.

    The search starts at the minute following ``after`` (seconds/microseconds
    truncated) and steps minute-by-minute until a match is found.

    Args:
        expression: A cron string or a pre-parsed :class:`CronExpression`.
        after: The reference time; the result is strictly greater than this
            (truncated to whole minutes).

    Returns:
        The next matching datetime, with second and microsecond set to zero.

    Raises:
        ValueError: If no match is found within the scan horizon (about four
            years), which indicates an unsatisfiable expression.
    """
    expr = expression if isinstance(expression, CronExpression) else parse(expression)
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

    for _ in range(_MAX_MINUTES):
        if matches(expr, candidate):
            return candidate
        candidate += timedelta(minutes=1)

    raise ValueError(f"no run time found for {expr.raw!r} within scan horizon")


@dataclass
class Job:
    """A registered job: a cron expression plus the callable to invoke.

    Attributes:
        name: A unique, human-readable identifier.
        expression: The parsed cron expression governing when the job runs.
        action: The zero-argument callable executed when the job is due.
    """

    name: str
    expression: CronExpression
    action: Callable[[], None]


@dataclass
class Scheduler:
    """An in-memory registry of cron jobs.

    The scheduler does not run a background loop; it is a deterministic,
    side-effect-free index you drive yourself. Call :meth:`due` to find jobs
    that match a wall-clock time, then :meth:`run_due` to invoke them.

    Attributes:
        jobs: Registered jobs keyed by name (insertion order preserved).
    """

    jobs: dict[str, Job] = field(default_factory=dict)

    def register(self, name: str, expression: str, action: Callable[[], None]) -> Job:
        """Register ``action`` under ``name`` to run on ``expression``.

        Args:
            name: Unique job name.
            expression: A cron string (validated immediately).
            action: Zero-argument callable to invoke when due.

        Returns:
            The created :class:`Job`.

        Raises:
            ValueError: If ``name`` is already registered.
            CronParseError: If ``expression`` is invalid.
        """
        if name in self.jobs:
            raise ValueError(f"job {name!r} already registered")
        job = Job(name=name, expression=parse(expression), action=action)
        self.jobs[name] = job
        return job

    def unregister(self, name: str) -> None:
        """Remove the job named ``name``.

        Raises:
            KeyError: If no such job exists.
        """
        del self.jobs[name]

    def due(self, dt: datetime) -> list[Job]:
        """Return the jobs whose cron expression matches ``dt``.

        Args:
            dt: The wall-clock time to evaluate against.

        Returns:
            Matching jobs in registration order.
        """
        return [job for job in self.jobs.values() if matches(job.expression, dt)]

    def run_due(self, dt: datetime) -> list[str]:
        """Invoke every job due at ``dt`` and return their names in order.

        Args:
            dt: The wall-clock time to evaluate against.

        Returns:
            The names of the jobs that were run.
        """
        ran: list[str] = []
        for job in self.due(dt):
            job.action()
            ran.append(job.name)
        return ran

    def next_runs(self, name: str, after: datetime, count: int = 5) -> list[datetime]:
        """Return the next ``count`` run times for the job named ``name``.

        Args:
            name: The registered job name.
            after: Reference time; results are strictly after it.
            count: How many upcoming run times to return.

        Returns:
            A list of up to ``count`` matching datetimes in ascending order.

        Raises:
            KeyError: If no such job exists.
        """
        expr = self.jobs[name].expression
        return upcoming(expr, after, count)


def upcoming(expression: str | CronExpression, after: datetime, count: int = 5) -> list[datetime]:
    """Return the next ``count`` matching datetimes after ``after``.

    Args:
        expression: A cron string or parsed :class:`CronExpression`.
        after: Reference time; results are strictly after it.
        count: Number of upcoming run times to produce.

    Returns:
        Ascending list of up to ``count`` matching datetimes.
    """
    expr = expression if isinstance(expression, CronExpression) else parse(expression)
    out: list[datetime] = []
    cursor = after
    for _ in range(count):
        cursor = next_run(expr, cursor)
        out.append(cursor)
    return out
