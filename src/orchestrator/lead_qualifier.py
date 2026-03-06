"""Lead Qualifier — scores inbound leads and triggers Odoo + notifications.

Workflow:
1. A lead comes in (via WhatsApp, email, or web form trigger file in Needs_Action)
2. LeadQualifier scores it: warm / hot / cold
3. Creates an Odoo CRM lead record
4. Sends a welcome email to the lead
5. Sends a WhatsApp notification to the sales team
6. Updates the vault with the lead record

Scoring criteria:
    hot  — budget confirmed + decision maker + urgent timeline (<30 days)
    warm — 2 of the 3 above criteria
    cold — 0-1 criteria
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from src.core.config import Config
from src.core.logger import AuditLogger

log = logging.getLogger(__name__)

LeadScore = Literal["hot", "warm", "cold"]


@dataclass
class Lead:
    name: str
    email: str
    company: str = ""
    phone: str = ""
    budget: float = 0.0
    is_decision_maker: bool = False
    timeline_days: int = 90
    source: str = "inbound"
    notes: str = ""
    score: LeadScore = "cold"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LeadQualifier:
    """Qualifies leads, creates Odoo records, and sends notifications."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.audit = AuditLogger(self.config.vault_path)

    def score(self, lead: Lead) -> LeadScore:
        """Score a lead based on BANT criteria (Budget, Authority, Need, Timeline)."""
        criteria_met = 0
        if lead.budget >= 1000:
            criteria_met += 1
        if lead.is_decision_maker:
            criteria_met += 1
        if lead.timeline_days <= 30:
            criteria_met += 1

        if criteria_met >= 3:
            return "hot"
        elif criteria_met >= 2:
            return "warm"
        else:
            return "cold"

    def qualify(self, lead: Lead) -> dict:
        """Full qualification pipeline: score → Odoo → email → WhatsApp → vault."""
        lead.score = self.score(lead)
        log.info(
            "Lead qualified: %s <%s> — score=%s (budget=%.0f, dm=%s, timeline=%dd)",
            lead.name, lead.email, lead.score,
            lead.budget, lead.is_decision_maker, lead.timeline_days,
        )

        results: dict = {"lead": lead.name, "score": lead.score}

        # 1. Create Odoo CRM lead
        odoo_id = self._create_odoo_lead(lead)
        results["odoo_id"] = odoo_id

        # 2. Send welcome email
        results["email_sent"] = self._send_welcome_email(lead)

        # 3. WhatsApp notification to sales team
        results["whatsapp_sent"] = self._notify_sales_whatsapp(lead)

        # 4. Write lead record to vault
        self._write_vault_record(lead, odoo_id)

        self.audit.log(
            action_type="lead_qualified",
            actor="lead_qualifier",
            target=lead.email,
            parameters={
                "name": lead.name,
                "score": lead.score,
                "budget": lead.budget,
                "odoo_id": str(odoo_id),
            },
            result="success",
        )
        return results

    def _create_odoo_lead(self, lead: Lead) -> int | None:
        if self.config.dev_mode:
            log.info("[DEV_MODE] Would create Odoo lead for %s", lead.name)
            return None

        if not self.config.odoo_url:
            log.warning("Odoo not configured — skipping CRM record")
            return None

        try:
            from src.mcp_servers.odoo_client import OdooClient
            client = OdooClient(
                url=self.config.odoo_url,
                db=self.config.odoo_db,
                username=self.config.odoo_username,
                password=self.config.odoo_password,
            )
            odoo_id = client.create("crm.lead", {
                "name": f"{lead.company or lead.name} — Inbound Lead",
                "contact_name": lead.name,
                "email_from": lead.email,
                "phone": lead.phone,
                "partner_name": lead.company,
                "expected_revenue": lead.budget,
                "description": lead.notes,
                "source_id": False,
                "tag_ids": [],
                "priority": "2" if lead.score == "hot" else ("1" if lead.score == "warm" else "0"),
            })
            log.info("Created Odoo CRM lead id=%d for %s", odoo_id, lead.name)
            return odoo_id
        except Exception:
            log.exception("Failed to create Odoo lead for %s", lead.name)
            return None

    def _send_welcome_email(self, lead: Lead) -> bool:
        if self.config.dev_mode:
            log.info("[DEV_MODE] Would send welcome email to %s", lead.email)
            return True

        score_msg = {
            "hot": "We're very excited to connect — your timeline and requirements are a great fit.",
            "warm": "We'd love to explore how we can help you achieve your goals.",
            "cold": "Thank you for reaching out. We'd love to learn more about your needs.",
        }[lead.score]

        body = (
            f"Hi {lead.name.split()[0]},\n\n"
            f"Thank you for your interest! {score_msg}\n\n"
            f"One of our team members will be in touch within "
            f"{'24 hours' if lead.score == 'hot' else '48 hours'}.\n\n"
            f"Best regards,\nAI Employee\n"
        )
        try:
            from src.mcp_servers.gmail_service import GmailService
            svc = GmailService(self.config.gmail_credentials_path)
            svc.send_email(
                to=lead.email,
                subject="Thanks for reaching out!",
                body=body,
            )
            return True
        except Exception:
            log.exception("Failed to send welcome email to %s", lead.email)
            return False

    def _notify_sales_whatsapp(self, lead: Lead) -> bool:
        if self.config.dev_mode:
            log.info("[DEV_MODE] Would send WhatsApp alert for lead %s", lead.name)
            return True

        if not self.config.whatsapp_phone_number_id:
            return False

        score_emoji = {"hot": "🔥", "warm": "🌤", "cold": "❄"}[lead.score]
        msg = (
            f"{score_emoji} *New {lead.score.upper()} Lead*\n\n"
            f"*Name:* {lead.name}\n"
            f"*Company:* {lead.company or '—'}\n"
            f"*Email:* {lead.email}\n"
            f"*Budget:* ${lead.budget:,.0f}\n"
            f"*Timeline:* {lead.timeline_days} days\n"
            f"*Decision Maker:* {'Yes' if lead.is_decision_maker else 'No'}\n\n"
            f"{'⚡ Follow up within 24h!' if lead.score == 'hot' else ''}"
        )
        try:
            from src.mcp_servers.whatsapp_client import WhatsAppClient
            wa = WhatsAppClient(self.config)
            wa.send_message(to=self.config.whatsapp_phone_number_id, body=msg.strip())
            return True
        except Exception:
            log.exception("Failed to send WhatsApp lead notification")
            return False

    def _write_vault_record(self, lead: Lead, odoo_id: int | None) -> Path:
        """Write lead record to vault/Leads/."""
        leads_dir = self.config.vault_path / "Leads"
        leads_dir.mkdir(parents=True, exist_ok=True)
        ts = lead.created_at.strftime("%Y-%m-%dT%H-%M")
        filename = f"LEAD_{ts}_{lead.name.replace(' ', '_')}.md"
        path = leads_dir / filename
        content = (
            f"---\n"
            f"type: lead\n"
            f"name: {lead.name}\n"
            f"email: {lead.email}\n"
            f"company: {lead.company}\n"
            f"score: {lead.score}\n"
            f"budget: {lead.budget}\n"
            f"timeline_days: {lead.timeline_days}\n"
            f"decision_maker: {lead.is_decision_maker}\n"
            f"odoo_id: {odoo_id or 'null'}\n"
            f"created: {lead.created_at.isoformat()}\n"
            f"status: new\n"
            f"---\n\n"
            f"# Lead: {lead.name}\n\n"
            f"**Score**: {lead.score.upper()}\n"
            f"**Company**: {lead.company or '—'}\n"
            f"**Budget**: ${lead.budget:,.0f}\n"
            f"**Timeline**: {lead.timeline_days} days\n"
            f"**Decision Maker**: {'Yes' if lead.is_decision_maker else 'No'}\n\n"
            f"## Notes\n{lead.notes or '_No notes._'}\n\n"
            f"## Actions\n"
            f"- [ ] Initial contact email sent\n"
            f"- [ ] Follow-up scheduled\n"
            f"- [ ] Discovery call booked\n"
        )
        path.write_text(content, encoding="utf-8")
        log.info("Vault lead record written: %s", path.name)
        return path

    def qualify_from_file(self, trigger_file: Path) -> dict | None:
        """Parse a lead trigger file from Needs_Action/ and qualify it."""
        import re
        try:
            text = trigger_file.read_text(encoding="utf-8")
        except Exception:
            log.exception("Cannot read lead file: %s", trigger_file)
            return None

        def extract(key: str, default: str = "") -> str:
            m = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
            return m.group(1).strip() if m else default

        lead = Lead(
            name=extract("name", "Unknown"),
            email=extract("email"),
            company=extract("company"),
            phone=extract("phone"),
            budget=float(extract("budget", "0").replace("$", "").replace(",", "") or 0),
            is_decision_maker=extract("decision_maker", "no").lower() in ("yes", "true", "1"),
            timeline_days=int(extract("timeline_days", "90") or 90),
            source=extract("source", "inbound"),
            notes=extract("notes"),
        )
        return self.qualify(lead)
