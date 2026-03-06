"""Content Calendar — plans and schedules a full week of social posts.

Runs every Sunday at 08:00 (triggered by orchestrator cron).

Workflow:
1. Generate 7 post ideas (one per day Mon–Sun) using topic rotation
2. Map each post to the best platform (LinkedIn Mon/Wed/Fri, Twitter daily,
   Facebook Tue/Thu, Instagram Sat/Sun)
3. Write the plan to vault/Content_Calendar.md
4. Schedule each post via scheduler.schedule_at() at optimal times

Platform timing (UTC):
  LinkedIn  — 08:00 (professional hours)
  Twitter   — 12:00 (peak engagement)
  Facebook  — 15:00 (afternoon)
  Instagram — 18:00 (evening)

Topic rotation:
  Week rotates through: insight → tip → story → question → behind-the-scenes → announcement → recap
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.core.config import Config
from src.core.logger import AuditLogger

log = logging.getLogger(__name__)

# Post topics rotate through the week
_TOPICS = [
    ("Monday",    "linkedin", "industry_insight",     8),
    ("Tuesday",   "facebook", "practical_tip",        15),
    ("Wednesday", "twitter",  "thought_leadership",   12),
    ("Thursday",  "linkedin", "success_story",        8),
    ("Friday",    "twitter",  "community_question",   12),
    ("Saturday",  "instagram","behind_the_scenes",    18),
    ("Sunday",    "facebook", "weekly_recap",         15),
]

_TOPIC_PROMPTS: dict[str, str] = {
    "industry_insight":   "Share a key insight or trend in your industry that your audience should know about.",
    "practical_tip":      "Share a practical tip or shortcut that saves time or improves productivity.",
    "thought_leadership": "Share your opinion or prediction about where your industry is heading.",
    "success_story":      "Briefly tell a story of a challenge overcome or a win achieved recently.",
    "community_question": "Ask your audience an engaging question to spark discussion.",
    "behind_the_scenes":  "Give a peek behind the scenes of how you work or what you're building.",
    "weekly_recap":       "Recap the most valuable things shared this week and what's coming next.",
}

_PLATFORM_CHAR_LIMITS: dict[str, int] = {
    "linkedin": 3000,
    "twitter": 280,
    "facebook": 2000,
    "instagram": 2200,
}


class ContentCalendar:
    """Generates and schedules a weekly social media content plan."""

    def __init__(self, config: Config | None = None, scheduler=None) -> None:
        self.config = config or Config()
        self.audit = AuditLogger(self.config.vault_path)
        self.vault = self.config.vault_path
        self._scheduler = scheduler  # Scheduler instance (may be None in standalone use)

    def _next_weekday(self, weekday_name: str) -> datetime:
        """Return the next occurrence of the named weekday (Mon=0 … Sun=6) from today."""
        names = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        target = names.index(weekday_name.lower())
        today = datetime.now(timezone.utc)
        days_ahead = (target - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # schedule for next week not today
        return (today + timedelta(days=days_ahead)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    def _generate_post_text(self, day: str, platform: str, topic_key: str) -> str:
        """Generate placeholder post text. In production, Claude writes this."""
        prompt = _TOPIC_PROMPTS.get(topic_key, "Share something valuable with your audience.")
        limit = _PLATFORM_CHAR_LIMITS.get(platform, 500)
        hashtags = {
            "linkedin": "#AI #Productivity #Innovation",
            "twitter": "#AI #Tech #BuildInPublic",
            "facebook": "#Business #Growth #AI",
            "instagram": "#AI #BehindTheScenes #Innovation",
        }.get(platform, "")
        # Template placeholder — agent will fill in real content at post time
        text = (
            f"[{day} | {platform.title()} | Topic: {topic_key.replace('_', ' ').title()}]\n\n"
            f"{prompt}\n\n"
            f"[AGENT: expand this into a compelling {platform} post, max {limit} chars]\n\n"
            f"{hashtags}"
        )
        return text[:limit]

    def _write_calendar_file(self, posts: list[dict]) -> Path:
        """Write the weekly content plan to vault/Content_Calendar.md."""
        plans_dir = self.vault / "Plans"
        plans_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        week_start = now.strftime("%Y-%m-%d")
        filename = f"Content_Calendar_{week_start}.md"
        path = plans_dir / filename

        lines = [
            f"---",
            f"type: content_calendar",
            f"week_starting: {week_start}",
            f"generated: {now.isoformat()}",
            f"posts: {len(posts)}",
            f"---",
            f"",
            f"# Content Calendar — Week of {week_start}",
            f"",
            f"| Day | Platform | Topic | Time (UTC) | Status |",
            f"|-----|----------|-------|------------|--------|",
        ]
        for p in posts:
            lines.append(
                f"| {p['day']} | {p['platform'].title()} | {p['topic'].replace('_',' ').title()} "
                f"| {p['post_time'].strftime('%H:%M')} | Scheduled |"
            )
        lines += ["", "---", ""]
        for p in posts:
            lines += [
                f"## {p['day']} — {p['platform'].title()}",
                f"**Topic**: {p['topic'].replace('_',' ').title()}  ",
                f"**Time**: {p['post_time'].isoformat()}",
                f"",
                f"```",
                p["text"],
                f"```",
                f"",
            ]

        path.write_text("\n".join(lines), encoding="utf-8")
        log.info("Content calendar written: %s (%d posts)", filename, len(posts))
        return path

    def _dispatch_post(self, platform: str, text: str) -> None:
        """Dispatch a single social post (called by scheduler at post time)."""
        if self.config.dev_mode or self.config.dry_run:
            log.info("[DRY_RUN] Would post to %s: %s…", platform, text[:80])
            return
        try:
            if platform == "linkedin":
                from src.mcp_servers.linkedin_client import LinkedInClient
                LinkedInClient(self.config).post(text=text)
            elif platform == "twitter":
                from src.mcp_servers.twitter_client import TwitterClient
                TwitterClient(
                    api_key=self.config.twitter_api_key,
                    api_secret=self.config.twitter_api_secret,
                    access_token=self.config.twitter_access_token,
                    access_secret=self.config.twitter_access_secret,
                    dry_run=False,
                ).post(text=text)
            elif platform == "facebook":
                from src.mcp_servers.facebook_client import FacebookClient
                FacebookClient(self.config).post_to_page(
                    page_id=self.config.facebook_page_id, message=text
                )
            elif platform == "instagram":
                from src.mcp_servers.instagram_client import InstagramClient
                InstagramClient(self.config).post(
                    ig_user_id=self.config.ig_user_id,
                    image_url="",
                    caption=text,
                )
            log.info("Scheduled post published to %s", platform)
        except Exception:
            log.exception("Scheduled post to %s failed", platform)

    def generate_and_schedule(self) -> Path:
        """Generate this week's content plan, write it, and schedule all posts."""
        posts = []
        for day, platform, topic, hour_utc in _TOPICS:
            post_time = self._next_weekday(day).replace(hour=hour_utc)
            text = self._generate_post_text(day, platform, topic)
            posts.append({
                "day": day,
                "platform": platform,
                "topic": topic,
                "post_time": post_time,
                "text": text,
            })

            # Schedule via the injected scheduler (if available)
            if self._scheduler is not None:
                job_id = f"content_{day.lower()}_{platform}"
                captured_platform = platform
                captured_text = text
                self._scheduler.schedule_at(
                    name=job_id,
                    func=lambda p=captured_platform, t=captured_text: self._dispatch_post(p, t),
                    run_time=post_time,
                )
                log.info("Scheduled %s post for %s at %s", platform, day, post_time.isoformat())

        calendar_path = self._write_calendar_file(posts)

        self.audit.log(
            action_type="content_calendar_generated",
            actor="content_calendar",
            target="social_media",
            parameters={"posts": len(posts), "file": calendar_path.name},
        )
        return calendar_path
