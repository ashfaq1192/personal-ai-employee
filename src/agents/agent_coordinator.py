"""Agent Coordinator — routes Needs_Action tasks to specialized Phase 2 agents.

Routing rules (file prefix → agent):
  LEAD_*          → SalesAgent
  EMAIL_* with lead keywords → SalesAgent
  SOCIAL_*        → SocialMediaAgent (via ContentBrief)
  FOLLOWUP_*      → SalesAgent (it's an outbound email task)
  WHATSAPP_*      → general orchestrator (Claude reasoning)
  *               → general orchestrator (Claude reasoning)

Each agent uses ClaimManager to atomically claim files from Needs_Action/.
The coordinator runs in a thread from the orchestrator and polls every 60s.

Multi-agent architecture (Madam Wania's Phase 2 model):
  General Agent (Claude Code)     ← orchestrates complex reasoning
      │
      ├── SalesAgent               ← deterministic, specialized, deployable
      │     LEAD_*, EMAIL_*(lead), FOLLOWUP_*
      │
      └── SocialMediaAgent         ← deterministic, specialized, deployable
            SOCIAL_*
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from src.core.config import Config
from src.core.logger import AuditLogger

log = logging.getLogger(__name__)

_SOCIAL_PREFIXES = ("SOCIAL_",)
_SALES_PREFIXES  = ("LEAD_", "FOLLOWUP_")
_LEAD_KEYWORDS   = [
    "interested in", "pricing", "quote", "proposal", "demo request",
    "partnership", "looking for", "need a solution", "how much",
]


class AgentCoordinator:
    """Polls Needs_Action and dispatches tasks to the right specialized agent."""

    def __init__(self, config: Config | None = None, poll_interval: int = 60) -> None:
        self.config = config or Config()
        self.vault = self.config.vault_path
        self.audit = AuditLogger(self.vault)
        self._poll_interval = poll_interval
        self._running = False
        self._thread: threading.Thread | None = None

    def _route(self, path: Path) -> str:
        """Determine which agent should handle this file."""
        name = path.name
        if any(name.startswith(p) for p in _SALES_PREFIXES):
            return "sales"
        if any(name.startswith(p) for p in _SOCIAL_PREFIXES):
            return "social"
        if name.startswith("EMAIL_"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
                if any(kw in text for kw in _LEAD_KEYWORDS):
                    return "sales"
            except Exception:
                pass
        return "general"

    def _dispatch_sales(self, path: Path) -> None:
        try:
            from src.agents.sales_agent import SalesAgent
            agent = SalesAgent(self.config)
            agent.process_file(path)
        except Exception:
            log.exception("SalesAgent dispatch failed for %s", path.name)

    def _dispatch_social(self, path: Path) -> None:
        try:
            from src.agents.social_media_agent import SocialMediaAgent, ContentBrief
            import re
            text = path.read_text(encoding="utf-8", errors="ignore")
            # Extract topic from file content
            m = re.search(r"topic[:\s]+(.+)", text, re.IGNORECASE)
            topic = m.group(1).strip()[:120] if m else "AI and productivity"
            m_plat = re.search(r"platform[:\s]+(\w+)", text, re.IGNORECASE)
            platform = m_plat.group(1).lower() if m_plat else "linkedin"
            if platform not in ("twitter", "linkedin", "facebook", "instagram"):
                platform = "linkedin"

            brief = ContentBrief(topic=topic, platform=platform)  # type: ignore[arg-type]
            agent = SocialMediaAgent(self.config)
            post = agent.generate(brief)
            log.info(
                "SocialAgent generated %s post (%d chars): %s…",
                platform, post.char_count, post.text[:60],
            )
            # Write to approval queue
            from datetime import datetime, timezone
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
            approved_dir = self.vault / "Pending_Approval"
            approved_dir.mkdir(parents=True, exist_ok=True)
            (approved_dir / f"APPROVAL_social_{platform}_{ts}.md").write_text(
                f"---\ntype: social_post\naction: {platform}_post\n"
                f"platform: {platform}\nrequested_by: social_media_agent\n"
                f"created: {datetime.now(timezone.utc).isoformat()}\n---\n\n"
                f"## Reply Body\n\n{post.text}\n",
                encoding="utf-8",
            )
            # Move source file to Done
            done = self.vault / "Done"
            done.mkdir(parents=True, exist_ok=True)
            path.rename(done / path.name)
        except Exception:
            log.exception("SocialAgent dispatch failed for %s", path.name)

    def _poll(self) -> None:
        """One poll cycle — scan Needs_Action and dispatch."""
        na = self.vault / "Needs_Action"
        if not na.exists():
            return
        for f in list(na.glob("*.md")):
            route = self._route(f)
            if route == "sales":
                log.info("Coordinator → SalesAgent: %s", f.name)
                self._dispatch_sales(f)
            elif route == "social":
                log.info("Coordinator → SocialAgent: %s", f.name)
                self._dispatch_social(f)
            # "general" falls through to Claude Code orchestrator

    def run_once(self) -> None:
        """Run a single dispatch cycle (useful for testing or on-demand)."""
        self._poll()

    def start(self) -> None:
        """Start the coordinator in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="agent-coordinator")
        self._thread.start()
        log.info("AgentCoordinator started (poll_interval=%ds)", self._poll_interval)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("AgentCoordinator stopped")

    def _loop(self) -> None:
        while self._running:
            try:
                self._poll()
            except Exception:
                log.exception("AgentCoordinator poll error")
            time.sleep(self._poll_interval)
