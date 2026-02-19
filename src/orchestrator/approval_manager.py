"""Approval Manager — file-based HITL approval workflow."""

from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from src.core.logger import AuditLogger

log = logging.getLogger(__name__)


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    """Parse YAML frontmatter from a markdown file."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.+?)\n---", text, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except Exception:
        return {}


def _load_expiry_overrides(vault_path: Path) -> dict[str, int]:
    """Load approval expiry overrides from Company_Handbook.md."""
    handbook = vault_path / "Company_Handbook.md"
    overrides: dict[str, int] = {}
    if not handbook.exists():
        return overrides

    text = handbook.read_text(encoding="utf-8")
    # Parse "## Approval Expiry" section
    in_section = False
    for line in text.splitlines():
        if "## Approval Expiry" in line:
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            stripped = line.strip().lstrip("- ").strip()
            if ":" in stripped:
                key, val = stripped.split(":", 1)
                key = key.strip().lower()
                val = val.strip().lower()
                # Parse hours from "24 hours", "4 hours", "48 hours"
                hours_match = re.search(r"(\d+)\s*hour", val)
                if hours_match:
                    if "default" in key:
                        overrides["default"] = int(hours_match.group(1))
                    elif "payment" in key:
                        overrides["payment"] = int(hours_match.group(1))
                    elif "social" in key:
                        overrides["social_post"] = int(hours_match.group(1))
    return overrides


class ApprovalManager:
    """Manages the file-based HITL approval workflow."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = vault_path
        self.pending_dir = vault_path / "Pending_Approval"
        self.approved_dir = vault_path / "Approved"
        self.rejected_dir = vault_path / "Rejected"
        self.done_dir = vault_path / "Done"
        self.audit = AuditLogger(vault_path)
        self._expiry_overrides = _load_expiry_overrides(vault_path)

        for d in [self.pending_dir, self.approved_dir, self.rejected_dir, self.done_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _get_expiry_hours(self, action_type: str) -> int:
        """Get expiry hours for an action type, with overrides from Handbook."""
        return self._expiry_overrides.get(
            action_type,
            self._expiry_overrides.get("default", 24),
        )

    def create_approval(
        self,
        action: str,
        *,
        amount: float | None = None,
        recipient: str = "",
        reason: str = "",
        plan_ref: str = "",
        parameters: dict[str, Any] | None = None,
    ) -> Path:
        """Create an approval request file in /Pending_Approval/."""
        now = datetime.now(timezone.utc)
        expiry_hours = self._get_expiry_hours(action)
        expires = now + timedelta(hours=expiry_hours)

        date_str = now.strftime("%Y-%m-%d")
        target = re.sub(r"[^\w]", "_", recipient)[:30]
        filename = f"APPROVAL_{action}_{target}_{date_str}.md"
        path = self.pending_dir / filename

        # Avoid collisions
        counter = 1
        while path.exists():
            filename = f"APPROVAL_{action}_{target}_{date_str}_{counter}.md"
            path = self.pending_dir / filename
            counter += 1

        content = (
            f"---\n"
            f"type: approval_request\n"
            f"action: {action}\n"
            f"id: {path.stem}\n"
            f"amount: {amount}\n"
            f"recipient: {recipient}\n"
            f"reason: {reason}\n"
            f"plan_ref: {plan_ref}\n"
            f"created: {now.isoformat()}\n"
            f"expires: {expires.isoformat()}\n"
            f"status: pending\n"
            f"---\n\n"
            f"## Action Details\n"
            f"**Action**: {action}\n"
            f"**Recipient**: {recipient}\n"
        )
        if amount is not None:
            content += f"**Amount**: ${amount:.2f}\n"
        content += (
            f"**Reason**: {reason}\n\n"
            f"## To Approve\n"
            f"Move this file to /Approved/ folder.\n\n"
            f"## To Reject\n"
            f"Move this file to /Rejected/ folder.\n"
        )

        path.write_text(content, encoding="utf-8")

        self.audit.log(
            action_type="approval",
            actor="approval_manager",
            target=str(path),
            parameters={"action": action, "recipient": recipient, "amount": amount},
            approval_status="pending",
        )

        return path

    def check_expired(self) -> list[Path]:
        """Move expired approval requests to /Rejected/."""
        now = datetime.now(timezone.utc)
        expired: list[Path] = []

        for f in self.pending_dir.glob("APPROVAL_*.md"):
            fm = _parse_frontmatter(f)
            expires_str = fm.get("expires", "")
            if not expires_str:
                continue
            try:
                expires_dt = datetime.fromisoformat(str(expires_str))
                if now > expires_dt:
                    # Move to rejected with note
                    text = f.read_text(encoding="utf-8")
                    text = text.replace("status: pending", "status: expired")
                    text += "\n\n> Auto-rejected: expired\n"
                    dest = self.rejected_dir / f.name
                    dest.write_text(text, encoding="utf-8")
                    f.unlink()
                    expired.append(dest)

                    self.audit.log(
                        action_type="approval",
                        actor="approval_manager",
                        target=str(dest),
                        parameters={"event": "expired"},
                        approval_status="expired",
                    )
            except (ValueError, TypeError):
                continue

        return expired

    def process_approved(self, filepath: Path) -> dict[str, Any]:
        """Read approved file and return action parameters."""
        fm = _parse_frontmatter(filepath)
        return fm

    def process_rejected(self, filepath: Path) -> None:
        """Handle rejected approval — move to Done."""
        dest = self.done_dir / filepath.name
        shutil.move(str(filepath), str(dest))

        self.audit.log(
            action_type="approval",
            actor="approval_manager",
            target=str(dest),
            approval_status="rejected",
        )
