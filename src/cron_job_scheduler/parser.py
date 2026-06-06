"""Parse standard 5-field cron expressions into matchable field sets.

A cron expression has five whitespace-separated fields::

    minute  hour  day-of-month  month  day-of-week
    *        *     *             *      *

Each field supports:

- ``*``              — every value in the field's range.
- a single number    — ``5``
- a list             — ``1,2,3``
- a range            — ``1-5``
- a step             — ``*/15`` or ``10-30/5`` (step over a range/wildcard)

Day-of-week accepts ``0``-``6`` where ``0`` (and ``7``) is Sunday. Month and
day-of-week are 1-based and 1-based respectively; all other fields follow the
ranges below. Out-of-range or malformed input raises :class:`CronParseError`.

Part of Cron Job Scheduler by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CronExpression", "CronParseError", "FieldSpec", "parse"]


class CronParseError(ValueError):
    """Raised when a cron expression cannot be parsed or is out of range."""


@dataclass(frozen=True)
class FieldSpec:
    """A single cron field: its valid bounds and the set of allowed values.

    Attributes:
        name: Human-readable field name (for error messages).
        low: Smallest legal value for the field.
        high: Largest legal value for the field.
        values: The concrete set of values this expression matches.
    """

    name: str
    low: int
    high: int
    values: frozenset[int]

    def matches(self, value: int) -> bool:
        """Return ``True`` if ``value`` is in this field's allowed set."""
        return value in self.values


# (name, low, high) for each of the five positional fields.
_FIELD_BOUNDS: tuple[tuple[str, int, int], ...] = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day-of-month", 1, 31),
    ("month", 1, 12),
    ("day-of-week", 0, 6),
)


@dataclass(frozen=True)
class CronExpression:
    """A fully parsed cron expression.

    Attributes:
        raw: The original expression string.
        minute: Allowed minutes (0-59).
        hour: Allowed hours (0-23).
        dom: Allowed days of month (1-31).
        month: Allowed months (1-12).
        dow: Allowed days of week (0-6, Monday=0? No — 0=Sunday).
    """

    raw: str
    minute: FieldSpec
    hour: FieldSpec
    dom: FieldSpec
    month: FieldSpec
    dow: FieldSpec


def _parse_field(token: str, name: str, low: int, high: int) -> FieldSpec:
    """Parse a single cron field token into a :class:`FieldSpec`.

    Args:
        token: The raw field text, e.g. ``"*/15"`` or ``"1-5"``.
        name: Field name, used in error messages.
        low: Smallest legal value.
        high: Largest legal value.

    Returns:
        A :class:`FieldSpec` holding the expanded value set.

    Raises:
        CronParseError: If the token is empty, malformed, or out of range.
    """
    if token == "":
        raise CronParseError(f"{name}: empty field")

    # Day-of-week accepts 7 as an alias for Sunday (0); allow it through the
    # range check, then fold it back to 0 so the stored set stays 0-6.
    is_dow = name == "day-of-week"
    parse_high = 7 if is_dow else high

    values: set[int] = set()
    for part in token.split(","):
        values |= _parse_part(part, name, low, parse_high)

    if is_dow and 7 in values:
        values.discard(7)
        values.add(0)

    if not values:
        raise CronParseError(f"{name}: no values produced from {token!r}")
    return FieldSpec(name=name, low=low, high=high, values=frozenset(values))


def _parse_part(part: str, name: str, low: int, high: int) -> set[int]:
    """Parse one comma-separated sub-expression (``*``, ``a``, ``a-b``, ``*/n``)."""
    step = 1
    range_text = part
    if "/" in part:
        range_text, _, step_text = part.partition("/")
        step = _to_int(step_text, name)
        if step <= 0:
            raise CronParseError(f"{name}: step must be positive in {part!r}")

    if range_text == "*":
        start, end = low, high
    elif "-" in range_text:
        start_text, _, end_text = range_text.partition("-")
        start = _to_int(start_text, name)
        end = _to_int(end_text, name)
        if start > end:
            raise CronParseError(f"{name}: range start {start} > end {end} in {part!r}")
    else:
        start = end = _to_int(range_text, name)

    if start < low or end > high:
        raise CronParseError(f"{name}: value out of range [{low}, {high}] in {part!r}")
    return set(range(start, end + 1, step))


def _to_int(text: str, name: str) -> int:
    """Convert ``text`` to an int, raising :class:`CronParseError` on failure."""
    try:
        return int(text)
    except ValueError as exc:
        raise CronParseError(f"{name}: {text!r} is not an integer") from exc


def parse(expression: str) -> CronExpression:
    """Parse a 5-field cron expression.

    Args:
        expression: The cron string, e.g. ``"*/15 * * * *"``.

    Returns:
        A :class:`CronExpression` ready for matching.

    Raises:
        CronParseError: If the expression does not have exactly five fields or
            any field is malformed or out of range.
    """
    tokens = expression.split()
    if len(tokens) != 5:
        raise CronParseError(f"expected 5 fields, got {len(tokens)}: {expression!r}")

    specs = [
        _parse_field(token, name, low, high)
        for token, (name, low, high) in zip(tokens, _FIELD_BOUNDS, strict=True)
    ]
    minute, hour, dom, month, dow = specs
    return CronExpression(
        raw=expression,
        minute=minute,
        hour=hour,
        dom=dom,
        month=month,
        dow=dow,
    )
