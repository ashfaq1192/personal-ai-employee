"""Sales Agent — Phase 2 custom agent for lead qualification and follow-up.

Specialization: inbound leads (LEAD_*.md) and lead-intent emails (EMAIL_*.md).

Workflow:
1. Claims LEAD_*.md or lead-intent EMAIL_*.md from Needs_Action via ClaimManager
2. Parses contact + BANT signals from the file
3. Runs LeadQualifier → score (hot/warm/cold) → Odoo CRM → welcome email → WA alert
4. Releases to Done/

Works alongside SocialMediaAgent via the shared vault.
Claim prefix:  LEAD_* → sales_agent
               EMAIL_* with lead_intent=true → sales_agent
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from src.core.config import Config
from src.core.logger import AuditLogger
from src.orchestrator.claim_manager import ClaimManager

log = logging.getLogger(__name__)

AGENT_NAME = "sales_agent"

# Keywords in email subject/body that signal a lead intent
_LEAD_INTENT_KEYWORDS = [
    "interested in", "pricing", "quote", "proposal", "demo request",
    "get started", "sign up", "partnership", "collaboration",
    "how much does", "can you help", "looking for", "need a solution",
]


class SalesAgent:
    """Deterministic sales agent — claims, qualifies, and closes lead tasks."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.vault = self.config.vault_path
        self.audit = AuditLogger(self.vault)
        self.claim_mgr = ClaimManager(self.vault)

    def _parse_fm(self, text: str) -> dict[str, str]:
        fm: dict[str, str] = {}
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            return fm
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"').strip("'")
        return fm

    def _has_lead_intent(self, text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in _LEAD_INTENT_KEYWORDS)

    def _qualify_lead_file(self, path: Path) -> dict:
        """Parse a LEAD_*.md or email file and run full qualification pipeline."""
        text = path.read_text(encoding="utf-8", errors="ignore")
        fm = self._parse_fm(text)

        from src.orchestrator.lead_qualifier import Lead, LeadQualifier

        # Extract fields — LEAD files have them in frontmatter; EMAIL files have less
        def _get(key: str, default: str = "") -> str:
            return fm.get(key, default).strip()

        budget_raw = _get("budget", "0").replace("$", "").replace(",", "")
        try:
            budget = float(budget_raw or 0)
        except ValueError:
            budget = 0.0

        lead = Lead(
            name=_get("name") or _get("contact_name", "Unknown"),
            email=_get("email") or _get("from", ""),
            company=_get("company", ""),
            phone=_get("phone", ""),
            budget=budget,
            is_decision_maker=_get("decision_maker", "no").lower() in ("yes", "true", "1"),
            timeline_days=int(_get("timeline_days", "90") or 90),
            notes=_get("notes") or _get("need", ""),
            source=_get("source", "inbound"),
        )

        qualifier = LeadQualifier(self.config)
        result = qualifier.qualify(lead)
        return result

    def process_file(self, file_path: Path) -> bool:
        """Claim and process a single task file. Returns True on success."""
        if not self.claim_mgr.claim(file_path, AGENT_NAME):
            log.info("SalesAgent: could not claim %s (already taken)", file_path.name)
            return False

        claimed = self.vault / "In_Progress" / AGENT_NAME / file_path.name
        try:
            result = self._qualify_lead_file(claimed)
            log.info(
                "SalesAgent: qualified lead from %s — score=%s",
                file_path.name, result.get("score", "?"),
            )
            self.audit.log(
                action_type="lead_processed",
                actor=AGENT_NAME,
                target=file_path.name,
                parameters=result,
                result="success",
            )
            self.claim_mgr.release(file_path.name, AGENT_NAME, "Done")
            return True
        except Exception as exc:
            log.exception("SalesAgent: processing failed for %s", file_path.name)
            self.audit.log(
                action_type="lead_processed",
                actor=AGENT_NAME,
                target=file_path.name,
                result="failure",
                error=str(exc)[:200],
            )
            self.claim_mgr.release(file_path.name, AGENT_NAME, "Needs_Action")
            return False

    def run_batch(self, max_tasks: int = 5) -> list[str]:
        """Scan Needs_Action and process all claimable lead/email-lead files."""
        na = self.vault / "Needs_Action"
        if not na.exists():
            return []

        processed: list[str] = []
        candidates = list(na.glob("LEAD_*.md")) + [
            f for f in na.glob("EMAIL_*.md")
            if self._has_lead_intent(f.read_text(encoding="utf-8", errors="ignore"))
        ]

        for path in candidates[:max_tasks]:
            if self.process_file(path):
                processed.append(path.name)

        return processed
