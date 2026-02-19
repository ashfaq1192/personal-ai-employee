"""APScheduler-based task scheduling."""

from __future__ import annotations

import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
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

    def start(self) -> None:
        self._scheduler.start()
        log.info("Scheduler started with %d jobs", len(self._scheduler.get_jobs()))

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")
