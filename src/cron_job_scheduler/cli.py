"""Command-line interface for Cron Job Scheduler.

``cron-job-scheduler demo`` shows the next few run times for a sample
expression and a tiny in-memory scheduler — fully offline, no services.
``cron-job-scheduler next`` and ``cron-job-scheduler matches`` expose the
core API for any expression you pass.

Part of Cron Job Scheduler by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from cron_job_scheduler import __version__
from cron_job_scheduler.parser import CronParseError
from cron_job_scheduler.schedule import Scheduler, matches, upcoming

app = typer.Typer(add_completion=False, help="Cron Job Scheduler — by Viprasol Tech.")
console = Console()

_FMT = "%Y-%m-%d %H:%M %a"


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"cron-job-scheduler [bold cyan]{__version__}[/] — by Viprasol Tech")


@app.command()
def next(
    expression: str = typer.Argument(..., help="A 5-field cron expression."),
    count: int = typer.Option(5, help="How many upcoming run times to show."),
    after: str = typer.Option("", help="Reference time 'YYYY-MM-DD HH:MM' (default: now)."),
) -> None:
    """Show the next ``count`` run times for an expression."""
    start = datetime.now() if not after else datetime.strptime(after, "%Y-%m-%d %H:%M")
    try:
        runs = upcoming(expression, start, count)
    except CronParseError as exc:
        console.print(f"[red]invalid cron:[/] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title=f"Next {count} runs for {expression!r}")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("When", style="green")
    for i, run in enumerate(runs, 1):
        table.add_row(str(i), run.strftime(_FMT))
    console.print(table)


@app.command(name="matches")
def matches_cmd(
    expression: str = typer.Argument(..., help="A 5-field cron expression."),
    when: str = typer.Argument(..., help="Datetime 'YYYY-MM-DD HH:MM' to test."),
) -> None:
    """Report whether a datetime satisfies an expression."""
    dt = datetime.strptime(when, "%Y-%m-%d %H:%M")
    try:
        ok = matches(expression, dt)
    except CronParseError as exc:
        console.print(f"[red]invalid cron:[/] {exc}")
        raise typer.Exit(code=1) from exc
    mark = "[green]MATCH[/]" if ok else "[yellow]no match[/]"
    console.print(f"{dt.strftime(_FMT)}  {mark}  for {expression!r}")


@app.command()
def demo() -> None:
    """Run an offline demo: parse expressions and drive a small scheduler."""
    ref = datetime(2025, 1, 1, 8, 0)
    console.print(f"[bold]Reference time:[/] {ref.strftime(_FMT)}\n")

    examples = {
        "*/15 * * * *": "every 15 minutes",
        "0 9 * * 1-5": "weekdays at 09:00",
        "30 2 1 * *": "02:30 on the 1st of each month",
    }
    for expr, label in examples.items():
        runs = upcoming(expr, ref, 3)
        rendered = ", ".join(r.strftime("%m-%d %H:%M %a") for r in runs)
        console.print(f"[cyan]{expr:<14}[/] [dim]({label})[/]\n  next 3: {rendered}")

    console.print("\n[bold]In-memory scheduler[/]")
    log: list[str] = []
    sched = Scheduler()
    sched.register("backup", "0 9 * * 1-5", lambda: log.append("backup ran"))
    sched.register("heartbeat", "*/15 * * * *", lambda: log.append("heartbeat ran"))

    tick = datetime(2025, 1, 6, 9, 0)  # a Monday at 09:00
    ran = sched.run_due(tick)
    console.print(f"  at {tick.strftime(_FMT)} due jobs: {ran or 'none'}")
    console.print(f"  action log: {log}")


if __name__ == "__main__":
    app()
