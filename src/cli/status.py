"""CLI: System status overview for AI Employee."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.core.config import Config
from src.core.logger import AuditLogger


def _check_process(name: str) -> str:
    """Check if a process is running via PM2."""
    try:
        result = subprocess.run(
            ["pm2", "jlist"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            processes = json.loads(result.stdout)
            for proc in processes:
                if proc.get("name") == name:
                    status = proc.get("pm2_env", {}).get("status", "unknown")
                    return status
        return "not found"
    except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return "pm2 unavailable"


def _count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for f in directory.iterdir() if f.is_file())


def main() -> None:
    config = Config()
    vault = config.vault_path
    audit = AuditLogger(vault)

    print("=" * 50)
    print("  AI Employee — System Status")
    print("=" * 50)
    print()

    # Mode
    if config.dev_mode:
        print(f"  Mode:     DEV_MODE (no external reads/writes)")
    elif config.dry_run:
        print(f"  Mode:     DRY_RUN (reads OK, writes logged-only)")
    else:
        print(f"  Mode:     PRODUCTION")

    print(f"  Vault:    {vault}")
    vault_exists = vault.exists()
    print(f"  Vault OK: {'Yes' if vault_exists else 'No — run init_vault'}")
    print()

    # Process status
    print("  Processes:")
    for name in ["orchestrator", "cloud-agent"]:
        status = _check_process(name)
        icon = "+" if status == "online" else "-"
        print(f"    [{icon}] {name}: {status}")
    print()

    # Vault folder counts
    if vault_exists:
        print("  Vault Folders:")
        folders = [
            "Needs_Action", "Pending_Approval", "Approved", "Rejected",
            "In_Progress", "Done", "Logs", "Briefings", "Accounting",
        ]
        for folder in folders:
            count = _count_files(vault / folder)
            print(f"    {folder + '/':.<25} {count} files")
        print()

    # Recent errors
    recent = audit.get_recent(20)
    errors = [e for e in recent if e.get("result") == "failure"]
    if errors:
        print(f"  Recent Errors ({len(errors)}):")
        for err in errors[:5]:
            ts = err.get("timestamp", "")[:19]
            action = err.get("action_type", "")
            error_msg = err.get("error", "unknown")[:60]
            print(f"    [{ts}] {action}: {error_msg}")
    else:
        print("  Recent Errors: None")
    print()

    # GCP VM status (if configured)
    try:
        result = subprocess.run(
            ["gcloud", "compute", "instances", "describe", "ai-employee-vm",
             "--zone=us-central1-a", "--format=get(status)"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            print(f"  GCP VM:   {result.stdout.strip()}")
        else:
            print("  GCP VM:   Not configured")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("  GCP VM:   gcloud not available")

    print()
    print("=" * 50)


if __name__ == "__main__":
    main()
