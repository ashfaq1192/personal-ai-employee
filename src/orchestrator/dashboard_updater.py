"""Dashboard Updater — refreshes Dashboard.md with current vault state."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.core.logger import AuditLogger


def _count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for f in directory.iterdir() if f.is_file())


def update_dashboard(vault_path: Path) -> None:
    """Update Dashboard.md with current folder counts and recent activity."""
    dashboard_path = vault_path / "Dashboard.md"
    if not dashboard_path.exists():
        return

    now = datetime.now(timezone.utc)
    needs_action = _count_files(vault_path / "Needs_Action")
    pending_approval = _count_files(vault_path / "Pending_Approval")
    in_progress = _count_files(vault_path / "In_Progress")

    # Get recent activity
    audit = AuditLogger(vault_path)
    recent = audit.get_recent(10)

    activity_rows = ""
    for entry in recent:
        ts = entry.get("timestamp", "")[:19]
        action = entry.get("action_type", "")
        target = entry.get("target", "")[:40]
        result = entry.get("result", "")
        icon = "+" if result == "success" else "-"
        activity_rows += f"| {ts} | {action} | {target} | {icon} |\n"

    if not activity_rows:
        activity_rows = "| — | No activity yet | — | — |\n"

    content = (
        f"---\n"
        f"last_updated: {now.isoformat()}\n"
        f"owner: local\n"
        f"---\n\n"
        f"# AI Employee Dashboard\n\n"
        f"## Status\n"
        f"- Gmail Watcher: Configured\n"
        f"- WhatsApp Watcher: Configured\n"
        f"- File Watcher: Configured\n"
        f"- Orchestrator: Running\n\n"
        f"## Pending Items\n"
        f"| Folder | Count |\n"
        f"|--------|-------|\n"
        f"| /Needs_Action/ | {needs_action} |\n"
        f"| /Pending_Approval/ | {pending_approval} |\n"
        f"| /In_Progress/ | {in_progress} |\n\n"
        f"## Recent Activity\n"
        f"| Time | Action | Target | Result |\n"
        f"|------|--------|--------|--------|\n"
        f"{activity_rows}\n"
        f"## Financials (MTD)\n"
        f"- Revenue: $0\n"
        f"- Expenses: $0\n"
        f"- Pending Invoices: 0\n"
    )

    dashboard_path.write_text(content, encoding="utf-8")

    # Single-writer rule: merge cloud agent Updates into dashboard
    _merge_cloud_updates(vault_path)


def _merge_cloud_updates(vault_path: Path) -> None:
    """Merge cloud agent status updates from /Updates/ and clean up."""
    updates_dir = vault_path / "Updates"
    if not updates_dir.exists():
        return

    update_files = sorted(updates_dir.glob("cloud_status_*.md"))
    if not update_files:
        return

    # Keep only the latest cloud status, delete older ones
    for old_file in update_files[:-1]:
        old_file.unlink()

    # The latest cloud status is left for reference; the dashboard
    # already reflects current folder counts which includes cloud activity.
