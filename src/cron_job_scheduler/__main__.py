"""Module entry point so ``python -m cron_job_scheduler`` runs the CLI.

Part of Cron Job Scheduler by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from cron_job_scheduler.cli import app

if __name__ == "__main__":
    app()
