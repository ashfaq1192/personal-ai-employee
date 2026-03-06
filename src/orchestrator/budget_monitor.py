"""Budget Alert System — monitors Odoo expenses and alerts on threshold breaches.

Runs daily at 07:00 (before the work day starts).

Config: vault/budget_config.json
  {
    "thresholds": {
      "total_monthly":    10000,
      "services":          3000,
      "software":          1000,
      "marketing":         2000
    },
    "alert_channel": "whatsapp",
    "currency": "USD"
  }

If budget_config.json doesn't exist, creates a default one on first run.
Alerts via WhatsApp (and optionally email) when any category exceeds its limit.
Weekly spend summary is returned as text for inclusion in the CEO briefing.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.core.config import Config
from src.core.logger import AuditLogger

log = logging.getLogger(__name__)

_BUDGET_CONFIG_FILE = "budget_config.json"
_DEFAULT_BUDGET = {
    "thresholds": {
        "total_monthly":  10000,
        "services":        3000,
        "software":        1000,
        "marketing":       2000,
        "travel":          1500,
    },
    "alert_channel": "whatsapp",
    "currency": "USD",
}


class BudgetMonitor:
    """Checks Odoo spend vs budget thresholds and fires alerts on breaches."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.vault = self.config.vault_path
        self.audit = AuditLogger(self.vault)
        self._budget_cfg_path = self.vault / _BUDGET_CONFIG_FILE

    def _load_budget_config(self) -> dict:
        if self._budget_cfg_path.exists():
            try:
                return json.loads(self._budget_cfg_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Write default and return it
        self._budget_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        self._budget_cfg_path.write_text(
            json.dumps(_DEFAULT_BUDGET, indent=2), encoding="utf-8"
        )
        log.info("Created default budget_config.json at %s", self._budget_cfg_path)
        return _DEFAULT_BUDGET

    def _fetch_odoo_spend(self) -> dict[str, float]:
        """Query Odoo for this month's posted invoices/expenses grouped by category.

        Returns dict: {category_name: total_amount}
        Falls back to empty dict if Odoo not configured.
        """
        if not self.config.odoo_url:
            log.debug("Odoo not configured — skipping budget fetch")
            return {}
        try:
            from src.mcp_servers.odoo_client import OdooClient
            client = OdooClient(
                url=self.config.odoo_url,
                db=self.config.odoo_db,
                username=self.config.odoo_username,
                password=self.config.odoo_password,
            )
            # Get this month's posted vendor bills (purchase invoices)
            now = datetime.now(timezone.utc)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            bills = client.search_read(
                "account.move",
                [
                    ["move_type", "=", "in_invoice"],
                    ["state", "=", "posted"],
                    ["invoice_date", ">=", month_start.strftime("%Y-%m-%d")],
                ],
                ["invoice_line_ids", "amount_total", "invoice_date"],
                limit=200,
            )
            total = sum(b.get("amount_total", 0) for b in bills)
            return {"total_monthly": total}
        except Exception as exc:
            log.warning("Odoo budget fetch failed: %s", exc)
            return {}

    def _send_alert(self, message: str) -> None:
        """Send budget alert via WhatsApp."""
        if self.config.dev_mode or self.config.dry_run:
            log.info("[DRY_RUN] Budget alert: %s", message[:200])
            return
        try:
            from src.mcp_servers.whatsapp_client import WhatsAppClient
            wa = WhatsAppClient(
                access_token=self.config.whatsapp_access_token,
                phone_number_id=self.config.whatsapp_phone_number_id,
                dry_run=False,
            )
            wa.send_message(to=self.config.whatsapp_phone_number_id, body=message)
        except Exception:
            log.exception("Budget alert delivery failed")

    def check_and_alert(self) -> list[str]:
        """Run the budget check. Returns list of breached categories."""
        cfg = self._load_budget_config()
        thresholds = cfg.get("thresholds", {})
        currency = cfg.get("currency", "USD")

        spend = self._fetch_odoo_spend()
        if not spend:
            log.debug("No spend data — budget check skipped")
            return []

        breaches: list[str] = []
        alert_lines: list[str] = []

        for category, limit in thresholds.items():
            actual = spend.get(category, 0.0)
            if actual >= limit:
                pct = int((actual / limit) * 100)
                breaches.append(category)
                alert_lines.append(
                    f"  • {category.replace('_', ' ').title()}: "
                    f"{currency} {actual:,.0f} / {currency} {limit:,.0f} ({pct}% of budget)"
                )
                log.warning(
                    "Budget breach: %s = %.0f (limit %.0f, %d%%)",
                    category, actual, limit, pct,
                )

        if breaches:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            alert_msg = (
                f"*Budget Alert — {now}*\n\n"
                f"The following categories have hit or exceeded budget:\n\n"
                + "\n".join(alert_lines) +
                f"\n\nPlease review spending in Odoo."
            )
            self._send_alert(alert_msg)
            self.audit.log(
                action_type="budget_alert",
                actor="budget_monitor",
                target="odoo",
                parameters={"breaches": breaches, "spend": spend},
                result="alert_sent",
            )

        return breaches

    def weekly_summary(self) -> str:
        """Return a short spend summary string for inclusion in the CEO briefing."""
        cfg = self._load_budget_config()
        currency = cfg.get("currency", "USD")
        spend = self._fetch_odoo_spend()

        if not spend:
            return "*Budget data unavailable — Odoo not configured or unreachable.*"

        thresholds = cfg.get("thresholds", {})
        lines = []
        for cat, amount in spend.items():
            limit = thresholds.get(cat, 0)
            pct = int((amount / limit) * 100) if limit else 0
            status = "OVER" if amount >= limit and limit else "OK"
            lines.append(
                f"  - {cat.replace('_', ' ').title()}: {currency} {amount:,.0f}"
                + (f" / {currency} {limit:,.0f} [{status}]" if limit else "")
            )

        return "**Spend This Month:**\n" + "\n".join(lines) if lines else "No spend data."
