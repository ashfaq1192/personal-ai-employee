"""Audit logger — appends structured JSON entries to vault /Logs/ directory."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


def _json_default(obj: Any) -> str:
    """JSON serializer for objects not natively serializable."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


class AuditLogger:
    """Appends JSON log entries to {vault_path}/Logs/YYYY-MM-DD.json."""

    def __init__(self, vault_path: Path) -> None:
        self.logs_dir = vault_path / "Logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _log_file(self, dt: datetime | None = None) -> Path:
        dt = dt or datetime.now(timezone.utc)
        return self.logs_dir / f"{dt.strftime('%Y-%m-%d')}.json"

    def log(
        self,
        action_type: str,
        actor: str,
        target: str | Path,
        *,
        parameters: dict[str, Any] | None = None,
        approval_status: str = "not_required",
        approved_by: str | None = None,
        result: str = "success",
        error: str | None = None,
        source_file: str | None = None,
    ) -> dict[str, Any]:
        """Append a single audit log entry. Returns the entry dict."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "actor": actor,
            "target": str(target),
            "parameters": parameters or {},
            "approval_status": approval_status,
            "approved_by": approved_by,
            "result": result,
            "error": error,
            "source_file": source_file,
        }

        log_file = self._log_file()
        # Read existing entries or start fresh
        entries: list[dict[str, Any]] = []
        if log_file.exists():
            try:
                entries = json.loads(log_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                entries = []

        entries.append(entry)
        log_file.write_text(
            json.dumps(entries, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8"
        )
        return entry

    def get_recent(self, count: int = 10) -> list[dict[str, Any]]:
        """Return the most recent N log entries across all log files."""
        all_entries: list[dict[str, Any]] = []
        log_files = sorted(self.logs_dir.glob("*.json"), reverse=True)
        for log_file in log_files:
            try:
                entries = json.loads(log_file.read_text(encoding="utf-8"))
                all_entries.extend(entries)
            except (json.JSONDecodeError, ValueError):
                continue
            if len(all_entries) >= count:
                break
        # Sort by timestamp descending and take top N
        all_entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return all_entries[:count]

    def cleanup_old_logs(self, retention_days: int = 90) -> int:
        """Delete log files older than retention_days. Returns count deleted."""
        cutoff = datetime.now(timezone.utc).date()
        deleted = 0
        for log_file in self.logs_dir.glob("*.json"):
            try:
                file_date = datetime.strptime(log_file.stem, "%Y-%m-%d").date()
                age_days = (cutoff - file_date).days
                if age_days > retention_days:
                    log_file.unlink()
                    deleted += 1
            except ValueError:
                continue
        return deleted
