"""CLI: View audit logs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.core.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(description="View AI Employee audit logs")
    parser.add_argument(
        "--date",
        type=str,
        default="today",
        help="Date to view (YYYY-MM-DD or 'today')",
    )
    parser.add_argument(
        "--action-type",
        type=str,
        default=None,
        help="Filter by action type",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=None,
        help="Show last N entries",
    )
    args = parser.parse_args()

    config = Config()
    logs_dir = config.vault_path / "Logs"

    if not logs_dir.exists():
        print("No logs directory found.")
        return

    # Resolve date
    if args.date == "today":
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        date_str = args.date

    log_file = logs_dir / f"{date_str}.json"
    if not log_file.exists():
        print(f"No log file for {date_str}")
        return

    entries = json.loads(log_file.read_text(encoding="utf-8"))

    # Filter
    if args.action_type:
        entries = [e for e in entries if e.get("action_type") == args.action_type]

    # Limit
    if args.last:
        entries = entries[-args.last :]

    # Display
    if not entries:
        print("No matching log entries.")
        return

    print(f"{'Timestamp':<26} {'Action':<18} {'Actor':<20} {'Target':<30} {'Result':<10}")
    print("-" * 106)
    for entry in entries:
        ts = entry.get("timestamp", "")[:25]
        action = entry.get("action_type", "")[:17]
        actor = entry.get("actor", "")[:19]
        target = entry.get("target", "")[:29]
        result = entry.get("result", "")[:9]
        print(f"{ts:<26} {action:<18} {actor:<20} {target:<30} {result:<10}")

    print(f"\n{len(entries)} entries shown.")


if __name__ == "__main__":
    main()
