#!/usr/bin/env python3
"""Claude Code Notification hook — fires terminal + OS notifications.

Called by Claude Code on the 'Notification' hook event.
JSON payload arrives on stdin:
  {
    "hook_event_name": "Notification",
    "session_id": "...",
    "cwd": "...",
    "message": "the notification text"
  }
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime


def _notify_wsl(title: str, message: str) -> None:
    """Show a Windows toast notification from WSL2 via PowerShell."""
    script = (
        f"[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null;"
        f"[System.Windows.Forms.MessageBox]::Show('{message}', '{title}')"
    )
    subprocess.Popen(
        ["powershell.exe", "-WindowStyle", "Hidden", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _notify_linux(title: str, message: str) -> None:
    """Use notify-send on Linux desktop."""
    subprocess.Popen(
        ["notify-send", "-t", "5000", title, message],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _log_to_file(title: str, message: str, vault_path: str) -> None:
    """Append notification to a log file in the vault."""
    log_dir = os.path.join(vault_path, "Logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "notifications.log")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {title}: {message}\n")


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        sys.exit(0)

    message = data.get("message", "Claude Code notification")
    title = "AI Employee"
    vault_path = os.environ.get("VAULT_PATH", os.path.expanduser("~/AI_Employee_Vault"))

    # Always print to terminal (visible in tmux logs window)
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] NOTIFY | {title}: {message}", flush=True)

    # Log to vault
    try:
        _log_to_file(title, message, vault_path)
    except Exception:
        pass

    # OS notification: WSL2
    try:
        if "microsoft" in open("/proc/version").read().lower():
            _notify_wsl(title, message)
            sys.exit(0)
    except Exception:
        pass

    # OS notification: Linux native
    try:
        _notify_linux(title, message)
    except Exception:
        pass


if __name__ == "__main__":
    main()
