"""Odoo JSON-RPC client for Odoo 19+ Community Edition."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from src.core.retry import with_retry

log = logging.getLogger(__name__)


class OdooClient:
    """Connects to Odoo 19+ via JSON-RPC (/jsonrpc)."""

    def __init__(
        self,
        url: str,
        db: str,
        username: str,
        password: str,
        *,
        pending_dir: Path | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._db = db
        self._username = username
        self._password = password
        self._uid: int | None = None
        self._pending_dir = pending_dir  # for queueing when offline

    def _jsonrpc(self, service: str, method: str, args: list) -> Any:
        """Execute a JSON-RPC call."""
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": service, "method": method, "args": args},
            "id": 1,
        }
        try:
            with httpx.Client(verify=True, timeout=30) as client:
                resp = client.post(f"{self._url}/jsonrpc", json=payload)
                resp.raise_for_status()
                result = resp.json()
                if "error" in result:
                    raise RuntimeError(result["error"].get("message", "Unknown Odoo error"))
                return result.get("result")
        except httpx.ConnectError as exc:
            if self._pending_dir:
                self._queue_action(service, method, args)
            raise ConnectionError(f"Odoo unreachable at {self._url}: {exc}") from exc

    def _queue_action(self, service: str, method: str, args: list) -> None:
        """Queue an action locally when Odoo is unreachable."""
        if not self._pending_dir:
            return
        self._pending_dir.mkdir(parents=True, exist_ok=True)
        import time
        filename = f"odoo_pending_{int(time.time())}.json"
        path = self._pending_dir / filename
        path.write_text(
            json.dumps({"service": service, "method": method, "args": args}, indent=2),
            encoding="utf-8",
        )
        log.info("Queued Odoo action to %s", path)

    @with_retry(max_attempts=2, base_delay=3.0, max_delay=15.0, exceptions=(ConnectionError,))
    def authenticate(self) -> int:
        """Authenticate and return UID."""
        self._uid = self._jsonrpc("common", "authenticate", [self._db, self._username, self._password, {}])
        if not self._uid:
            raise RuntimeError("Odoo authentication failed")
        log.info("Authenticated to Odoo as UID %d", self._uid)
        return self._uid

    def _ensure_auth(self) -> int:
        if self._uid is None:
            return self.authenticate()
        return self._uid

    def search_read(
        self, model: str, domain: list, fields: list[str], *, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Search and read records."""
        uid = self._ensure_auth()
        return self._jsonrpc(
            "object", "execute_kw",
            [self._db, uid, self._password, model, "search_read", [domain], {"fields": fields, "limit": limit}],
        )

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Create a record. Returns the new record ID."""
        uid = self._ensure_auth()
        return self._jsonrpc(
            "object", "execute_kw",
            [self._db, uid, self._password, model, "create", [values]],
        )

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> bool:
        """Update records."""
        uid = self._ensure_auth()
        return self._jsonrpc(
            "object", "execute_kw",
            [self._db, uid, self._password, model, "write", [ids, values]],
        )

    def replay_pending(self) -> list[dict[str, Any]]:
        """Replay queued actions from /Accounting/pending/ when Odoo is back online.

        Returns list of results for each replayed action.
        """
        if not self._pending_dir or not self._pending_dir.exists():
            return []

        results = []
        for pending_file in sorted(self._pending_dir.glob("odoo_pending_*.json")):
            try:
                data = json.loads(pending_file.read_text(encoding="utf-8"))
                result = self._jsonrpc(data["service"], data["method"], data["args"])
                results.append({"file": pending_file.name, "status": "replayed", "result": result})
                pending_file.unlink()
                log.info("Replayed pending Odoo action from %s", pending_file.name)
            except Exception as exc:
                results.append({"file": pending_file.name, "status": "failed", "error": str(exc)})
                log.warning("Failed to replay %s: %s", pending_file.name, exc)
        return results
