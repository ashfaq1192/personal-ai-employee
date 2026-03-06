"""Health Monitor — tracks subprocess health, restarts dead processes."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.core.logger import AuditLogger

log = logging.getLogger(__name__)


class HealthMonitor:
    """Monitors subprocess PIDs and restarts on failure."""

    def __init__(
        self,
        vault_path: Path,
        *,
        check_interval: int = 30,
    ) -> None:
        self.vault_path = vault_path
        self.check_interval = check_interval
        self.audit = AuditLogger(vault_path)
        self._processes: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        process: subprocess.Popen,
        restart_fn: Callable[[], subprocess.Popen],
        *,
        max_age_seconds: int = 0,
    ) -> None:
        """Register a subprocess for health monitoring.

        Args:
            max_age_seconds: If > 0, kill and restart the process if it runs
                             longer than this (stuck-process detection).
                             0 means no age limit.
        """
        self._processes[name] = {
            "process": process,
            "restart_fn": restart_fn,
            "restarts": 0,
            "started_at": time.monotonic(),
            "max_age_seconds": max_age_seconds,
        }
        log.info("Registered process '%s' (PID %d)", name, process.pid)

    def check_health(self) -> dict[str, str]:
        """Check all registered processes. Returns status dict."""
        statuses: dict[str, str] = {}
        for name, info in self._processes.items():
            proc: subprocess.Popen = info["process"]
            if proc.poll() is None:
                # Process is alive — check if it's stuck (running too long)
                max_age = info.get("max_age_seconds", 0)
                if max_age > 0:
                    age = time.monotonic() - info["started_at"]
                    if age > max_age:
                        log.warning(
                            "Process '%s' (PID %d) has been running for %.0fs (max %ds) — killing stuck process",
                            name, proc.pid, age, max_age,
                        )
                        proc.kill()
                        proc.wait(timeout=5)
                        statuses[name] = "stuck"
                        self._create_alert(name, proc.pid, reason="stuck")
                        try:
                            new_proc = info["restart_fn"]()
                            info["process"] = new_proc
                            info["restarts"] += 1
                            info["started_at"] = time.monotonic()
                            statuses[name] = "restarted_after_stuck"
                            log.info("Process '%s' restarted after being stuck (new PID %d)", name, new_proc.pid)
                        except Exception as exc:
                            statuses[name] = "restart_failed"
                            log.error("Failed to restart stuck '%s': %s", name, exc)
                        continue
                statuses[name] = "running"
            else:
                statuses[name] = "dead"
                log.warning("Process '%s' (PID %d) is dead. Restarting...", name, proc.pid)

                # Create alert
                self._create_alert(name, proc.pid)

                # Restart
                try:
                    new_proc = info["restart_fn"]()
                    info["process"] = new_proc
                    info["restarts"] += 1
                    statuses[name] = "restarted"
                    log.info(
                        "Process '%s' restarted (new PID %d, restart #%d)",
                        name,
                        new_proc.pid,
                        info["restarts"],
                    )
                    self.audit.log(
                        action_type="system",
                        actor="health_monitor",
                        target=name,
                        parameters={
                            "event": "restart",
                            "old_pid": proc.pid,
                            "new_pid": new_proc.pid,
                            "restart_count": info["restarts"],
                        },
                    )
                except Exception as exc:
                    statuses[name] = "restart_failed"
                    log.error("Failed to restart '%s': %s", name, exc)

        return statuses

    def _create_alert(self, name: str, pid: int, reason: str = "crashed") -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
        alert_path = self.vault_path / "Needs_Action" / f"ALERT_{reason}_{name}_{ts}.md"
        alert_path.parent.mkdir(parents=True, exist_ok=True)
        alert_path.write_text(
            f"---\ntype: alert\nid: ALERT_{reason}_{name}_{ts}\n"
            f"from: system\nsubject: Process {name} {reason} (PID {pid})\n"
            f"received: {datetime.now(timezone.utc).isoformat()}\n"
            f"priority: high\nstatus: pending\nplan_ref: null\n---\n\n"
            f"## Alert\nProcess `{name}` (PID {pid}) {reason} and was restarted.\n",
            encoding="utf-8",
        )

    def stop_all(self) -> None:
        """Stop all monitored processes."""
        for name, info in self._processes.items():
            proc: subprocess.Popen = info["process"]
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                log.info("Stopped process '%s' (PID %d)", name, proc.pid)
