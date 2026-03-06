"""Self-Performance Review — weekly agent metrics + comparison to prior week.

Runs every Sunday alongside the CEO briefing.

Metrics tracked:
  - tasks_completed   : files moved to Done/ this week
  - emails_handled    : EMAIL_*.md in Done/ this week
  - social_posts      : SOCIAL_*.md in Done/ + Plans/ this week
  - followups_sent    : FOLLOWUP_*.md in Done/ this week
  - leads_qualified   : LEAD_*.md created in vault/Leads/ this week
  - meetings_scheduled: APPROVAL_meeting_*.md in Done/ this week
  - pdfs_processed    : EMAIL_*.md with PDF Attachments section this week

Persists metrics to vault/metrics_history.json for week-over-week comparison.
Writes vault/Performance_Reviews/Performance_Review_YYYY-MM-DD.md.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.core.config import Config
from src.core.logger import AuditLogger

log = logging.getLogger(__name__)

_METRICS_FILE = "metrics_history.json"
_REVIEWS_DIR  = "Performance_Reviews"


class PerformanceReview:
    """Counts weekly metrics and generates a performance review file."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.vault = self.config.vault_path
        self.audit = AuditLogger(self.vault)
        self._metrics_path = self.vault / _METRICS_FILE

    def _week_cutoff(self, weeks_ago: int = 0) -> datetime:
        """Return UTC datetime for the start of `weeks_ago` weeks back (Monday 00:00)."""
        now = datetime.now(timezone.utc)
        # Go to this week's Monday
        monday = now - timedelta(days=now.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        return monday - timedelta(weeks=weeks_ago)

    def _count_by_pattern(
        self, folder: str, glob: str, *, this_week: datetime, contains: str = ""
    ) -> int:
        """Count files in folder matching glob, modified after this_week."""
        path = self.vault / folder
        if not path.exists():
            return 0
        count = 0
        for f in path.glob(glob):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if mtime >= this_week:
                    if contains:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                        if contains not in text:
                            continue
                    count += 1
            except Exception:
                pass
        return count

    def collect_metrics(self, reference_monday: datetime | None = None) -> dict[str, int]:
        """Count metrics for the 7-day window starting at reference_monday."""
        week_start = reference_monday or self._week_cutoff(0)

        return {
            "tasks_completed":    self._count_by_pattern("Done", "*.md", this_week=week_start),
            "emails_handled":     self._count_by_pattern("Done", "EMAIL_*.md", this_week=week_start),
            "social_posts":       self._count_by_pattern("Done", "SOCIAL_*.md", this_week=week_start)
                                + self._count_by_pattern("Plans", "SOCIAL_*.md", this_week=week_start),
            "followups_sent":     self._count_by_pattern("Done", "FOLLOWUP_*.md", this_week=week_start),
            "leads_qualified":    self._count_by_pattern("Leads", "LEAD_*.md", this_week=week_start),
            "meetings_scheduled": self._count_by_pattern("Done", "APPROVAL_meeting_*.md", this_week=week_start),
            "pdfs_processed":     self._count_by_pattern(
                                    "Done", "EMAIL_*.md", this_week=week_start,
                                    contains="## PDF Attachments"
                                ),
        }

    def _load_history(self) -> list[dict]:
        if self._metrics_path.exists():
            try:
                return json.loads(self._metrics_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def _save_history(self, history: list[dict]) -> None:
        self._metrics_path.write_text(
            json.dumps(history[-52:], indent=2),  # keep 1 year
            encoding="utf-8",
        )

    def _delta(self, current: int, previous: int) -> str:
        if previous == 0:
            return "N/A (no prior data)"
        pct = ((current - previous) / previous) * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.0f}%"

    def generate(self) -> Path:
        """Run the full review cycle: collect → compare → write → persist."""
        now = datetime.now(timezone.utc)
        this_week = self._week_cutoff(0)
        last_week = self._week_cutoff(1)

        current = self.collect_metrics(this_week)
        history = self._load_history()

        # Find last week's entry
        previous: dict[str, int] = {}
        if history:
            prev_entry = history[-1]
            previous = prev_entry.get("metrics", {})

        # Persist this week
        history.append({
            "week_starting": this_week.strftime("%Y-%m-%d"),
            "generated": now.isoformat(),
            "metrics": current,
        })
        self._save_history(history)

        # Build report
        reviews_dir = self.vault / _REVIEWS_DIR
        reviews_dir.mkdir(parents=True, exist_ok=True)
        filename = f"Performance_Review_{now.strftime('%Y-%m-%d')}.md"
        path = reviews_dir / filename

        metric_labels = {
            "tasks_completed":    "Tasks Completed",
            "emails_handled":     "Emails Handled",
            "social_posts":       "Social Posts Published",
            "followups_sent":     "Follow-ups Sent",
            "leads_qualified":    "Leads Qualified",
            "meetings_scheduled": "Meetings Scheduled",
            "pdfs_processed":     "PDFs Processed",
        }

        rows = []
        for key, label in metric_labels.items():
            cur = current.get(key, 0)
            prev = previous.get(key, 0)
            change = self._delta(cur, prev)
            rows.append(f"| {label} | {prev} | {cur} | {change} |")

        best_metric = max(current, key=lambda k: current[k])
        best_label  = metric_labels.get(best_metric, best_metric)
        best_val    = current[best_metric]

        if previous:
            total_cur  = sum(current.values())
            total_prev = sum(previous.values())
            overall_pct = self._delta(total_cur, total_prev)
            summary_line = (
                f"Overall activity {overall_pct} vs last week. "
                f"Best metric: **{best_label}** ({best_val})."
            )
        else:
            summary_line = f"First week of tracking. Best metric: **{best_label}** ({best_val})."

        content = (
            f"---\n"
            f"type: performance_review\n"
            f"week_starting: {this_week.strftime('%Y-%m-%d')}\n"
            f"generated: {now.isoformat()}\n"
            f"---\n\n"
            f"# AI Employee Performance Review\n"
            f"**Week of**: {this_week.strftime('%B %d, %Y')}\n"
            f"**Generated**: {now.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"## Executive Summary\n\n"
            f"{summary_line}\n\n"
            f"## Weekly Metrics\n\n"
            f"| Metric | Last Week | This Week | Change |\n"
            f"|--------|-----------|-----------|--------|\n"
            + "\n".join(rows) + "\n\n"
            f"## Highlights\n\n"
            f"- Top performing area: **{best_label}** with **{best_val}** this week\n"
            f"- Total actions taken: **{sum(current.values())}**\n\n"
            f"## Recommendations\n\n"
        )

        # Auto-generate recommendations based on metrics
        recommendations = []
        if current.get("followups_sent", 0) == 0:
            recommendations.append("No follow-ups sent this week — check Done/ for stale outbound tasks.")
        if current.get("social_posts", 0) < 3:
            recommendations.append("Social media activity is low — consider triggering the content calendar.")
        if current.get("leads_qualified", 0) > 0 and current.get("followups_sent", 0) == 0:
            recommendations.append("Leads qualified but no follow-ups sent — review lead pipeline.")
        if not recommendations:
            recommendations.append("Performance looks healthy. Maintain current cadence.")

        content += "".join(f"- {r}\n" for r in recommendations)

        path.write_text(content, encoding="utf-8")
        log.info("Performance review written: %s", filename)

        self.audit.log(
            action_type="performance_review",
            actor="performance_review",
            target="weekly_review",
            parameters={"filename": filename, **{k: str(v) for k, v in current.items()}},
            result="success",
        )
        return path
