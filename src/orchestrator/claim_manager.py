"""Claim-by-move rule for multi-agent coordination.

Implements atomic file claiming: first agent to move a file from
Needs_Action to In_Progress/<agent>/ owns it.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.core.logger import AuditLogger

log = logging.getLogger(__name__)


class ClaimManager:
    """Manages file-based task claiming for multi-agent coordination."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = vault_path
        self.audit = AuditLogger(vault_path)
        self._in_progress = vault_path / "In_Progress"
        self._in_progress.mkdir(parents=True, exist_ok=True)

    def claim(self, item_path: Path, agent_name: str) -> bool:
        """Atomically claim a file by moving it to In_Progress/<agent>/.

        Args:
            item_path: Path to file in Needs_Action.
            agent_name: Name of claiming agent (e.g. 'local', 'cloud').

        Returns:
            True if claim succeeded, False if file already moved.
        """
        if not item_path.exists():
            log.warning("Cannot claim %s — file does not exist", item_path.name)
            return False

        agent_dir = self._in_progress / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)
        target = agent_dir / item_path.name

        if target.exists():
            log.warning("Cannot claim %s — already claimed by %s", item_path.name, agent_name)
            return False

        try:
            shutil.move(str(item_path), str(target))
            log.info("Agent '%s' claimed: %s", agent_name, item_path.name)
            self.audit.log(
                action_type="claim",
                actor=agent_name,
                target=item_path.name,
                parameters={"destination": str(target)},
                result="success",
            )
            return True
        except FileNotFoundError:
            # Another agent moved it first
            log.info("Claim race lost for %s by agent '%s'", item_path.name, agent_name)
            return False
        except Exception:
            log.exception("Failed to claim %s", item_path.name)
            return False

    def release(self, item_name: str, agent_name: str, destination: str = "Done") -> bool:
        """Release a claimed item by moving it to the destination folder.

        Args:
            item_name: Filename of the claimed item.
            agent_name: Name of the agent releasing the claim.
            destination: Target folder (default: 'Done').

        Returns:
            True if release succeeded.
        """
        source = self._in_progress / agent_name / item_name
        if not source.exists():
            log.warning("Cannot release %s — not claimed by %s", item_name, agent_name)
            return False

        dest_dir = self.vault_path / destination
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = dest_dir / item_name

        try:
            shutil.move(str(source), str(target))
            log.info("Agent '%s' released %s → %s", agent_name, item_name, destination)
            self.audit.log(
                action_type="release",
                actor=agent_name,
                target=item_name,
                parameters={"destination": destination},
                result="success",
            )
            return True
        except Exception:
            log.exception("Failed to release %s", item_name)
            return False

    def list_claims(self, agent_name: str | None = None) -> list[dict]:
        """List all currently claimed items, optionally filtered by agent."""
        claims = []
        if agent_name:
            agent_dir = self._in_progress / agent_name
            if agent_dir.exists():
                for f in agent_dir.iterdir():
                    if f.is_file():
                        claims.append({"agent": agent_name, "file": f.name})
        else:
            for agent_dir in self._in_progress.iterdir():
                if agent_dir.is_dir():
                    for f in agent_dir.iterdir():
                        if f.is_file():
                            claims.append({"agent": agent_dir.name, "file": f.name})
        return claims
