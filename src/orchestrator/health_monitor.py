"""Health Monitor — tracks subprocess health, restarts dead processes."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
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
    ) -> None:
        """Register a subprocess for health monitoring."""
        self._processes[name] = {
            "process": process,
            "restart_fn": restart_fn,
            "restarts": 0,
        }
        log.info("Registered process '%s' (PID %d)", name, process.pid)

    def check_health(self) -> dict[str, str]:
        """Check all registered processes. Returns status dict."""
        statuses: dict[str, str] = {}
        for name, info in self._processes.items():
            proc: subprocess.Popen = info["process"]
            if proc.poll() is None:
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

    def _create_alert(self, name: str, pid: int) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
        alert_path = self.vault_path / "Needs_Action" / f"ALERT_crash_{name}_{ts}.md"
        alert_path.write_text(
            f"---\ntype: alert\nid: ALERT_crash_{name}_{ts}\n"
            f"from: system\nsubject: Process {name} crashed (PID {pid})\n"
            f"received: {datetime.now(timezone.utc).isoformat()}\n"
            f"priority: high\nstatus: pending\nplan_ref: null\n---\n\n"
            f"## Alert\nProcess `{name}` (PID {pid}) crashed and was restarted.\n",
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
