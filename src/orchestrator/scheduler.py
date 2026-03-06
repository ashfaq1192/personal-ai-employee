"""APScheduler-based task scheduling."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)


class Scheduler:
    """Wraps APScheduler BackgroundScheduler for cron-like and interval tasks."""

    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler(daemon=True)

    def add_scheduled_task(
        self, name: str, func: Callable, cron_expr: str
    ) -> None:
        """Add a cron-scheduled task. cron_expr format: 'minute hour day_of_week'."""
        parts = cron_expr.split()
        kwargs = {}
        if len(parts) >= 1:
            kwargs["minute"] = parts[0]
        if len(parts) >= 2:
            kwargs["hour"] = parts[1]
        if len(parts) >= 3:
            kwargs["day_of_week"] = parts[2]

        self._scheduler.add_job(
            func,
            trigger=CronTrigger(**kwargs),
            id=name,
            name=name,
            replace_existing=True,
        )
        log.info("Scheduled task '%s' with cron: %s", name, cron_expr)

    def add_interval_task(
        self, name: str, func: Callable, seconds: int
    ) -> None:
        """Add an interval-based task."""
        self._scheduler.add_job(
            func,
            trigger=IntervalTrigger(seconds=seconds),
            id=name,
            name=name,
            replace_existing=True,
        )
        log.info("Scheduled task '%s' every %ds", name, seconds)

    def schedule_once_after(self, name: str, func: Callable, delay_seconds: int) -> None:
        """Schedule a one-time task to run after delay_seconds from now.

        The agent can call this at runtime to schedule its own future work.
        Example: agent says 'send follow-up in 2 hours' → schedule_once_after(..., 7200)
        """
        run_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        self._scheduler.add_job(
            func,
            trigger=DateTrigger(run_date=run_at),
            id=name,
            name=name,
            replace_existing=True,
        )
        log.info("One-time task '%s' scheduled in %ds (at %s)", name, delay_seconds, run_at.isoformat())

    def schedule_at(self, name: str, func: Callable, run_time: datetime) -> None:
        """Schedule a one-time task at a specific datetime (must be timezone-aware)."""
        self._scheduler.add_job(
            func,
            trigger=DateTrigger(run_date=run_time),
            id=name,
            name=name,
            replace_existing=True,
        )
        log.info("One-time task '%s' scheduled at %s", name, run_time.isoformat())

    def cancel_task(self, name: str) -> bool:
        """Cancel a scheduled task by name. Returns True if found and removed."""
        try:
            self._scheduler.remove_job(name)
            log.info("Cancelled task '%s'", name)
            return True
        except Exception:
            return False

    def list_tasks(self) -> list[dict]:
        """Return all currently scheduled tasks with their next run times."""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in self._scheduler.get_jobs()
        ]

    def start(self) -> None:
        self._scheduler.start()
        log.info("Scheduler started with %d jobs", len(self._scheduler.get_jobs()))

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")
