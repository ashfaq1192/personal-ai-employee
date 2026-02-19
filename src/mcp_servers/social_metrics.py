"""Social Media Engagement Metrics Collector."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


def generate_metrics_summary(
    vault_path: Path,
    *,
    days: int = 7,
) -> str:
    """Generate a social media metrics summary .md in /Briefings/.

    Currently a scaffold — real metrics require API calls per platform.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    content = (
        f"---\n"
        f"generated: {now.isoformat()}\n"
        f"period: last {days} days\n"
        f"type: social_summary\n"
        f"---\n\n"
        f"# Social Media Metrics Summary\n\n"
        f"## LinkedIn\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Posts | 0 |\n"
        f"| Impressions | 0 |\n"
        f"| Likes | 0 |\n"
        f"| Comments | 0 |\n\n"
        f"## Facebook\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Posts | 0 |\n"
        f"| Reach | 0 |\n"
        f"| Reactions | 0 |\n\n"
        f"## Instagram\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Posts | 0 |\n"
        f"| Impressions | 0 |\n"
        f"| Likes | 0 |\n\n"
        f"## Twitter/X\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Tweets | 0 |\n"
        f"| Impressions | 0 |\n"
        f"| Likes | 0 |\n\n"
        f"> Connect platform API keys in `.env` to enable real metrics.\n"
    )

    briefings_dir = vault_path / "Briefings"
    briefings_dir.mkdir(parents=True, exist_ok=True)
    summary_path = briefings_dir / f"{date_str}_Social_Metrics.md"
    summary_path.write_text(content, encoding="utf-8")
    log.info("Social metrics summary written to %s", summary_path)
    return str(summary_path)
