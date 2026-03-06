"""Social Media Manager — Phase 2 Custom Agent.

This is the transition from Phase 1 (general Claude Code agent) to Phase 2
(custom, deterministic, deployable agent) as described by Madam Wania Kazmi.

Key differences from Phase 1:
- Deterministic: fixed workflow, no free-form reasoning
- Specialized: only handles social media tasks
- Deployable: runs as an independent service, not dependent on Claude Code
- Cost-optimized: uses a smaller model for routine tasks
- Non-vendor-locked: model is configurable via model_config.yaml

Workflow:
1. Receive a content brief (topic, platform, tone)
2. Generate platform-specific post using Claude API
3. Apply platform constraints (char limits, hashtag rules)
4. Request approval via vault
5. Post on approval
6. Track metrics
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal

import anthropic

from src.core.config import Config

log = logging.getLogger(__name__)

Platform = Literal["twitter", "linkedin", "facebook", "instagram"]


@dataclass
class ContentBrief:
    topic: str
    platform: Platform
    tone: str = "professional"
    target_audience: str = "general"
    include_hashtags: bool = True
    custom_instructions: str = ""


@dataclass
class GeneratedPost:
    platform: Platform
    text: str
    hashtags: list[str]
    char_count: int
    approved: bool = False


# Platform constraints — deterministic rules
PLATFORM_RULES: dict[Platform, dict] = {
    "twitter": {"max_chars": 280, "max_hashtags": 3},
    "linkedin": {"max_chars": 3000, "max_hashtags": 5},
    "facebook": {"max_chars": 63206, "max_hashtags": 10},
    "instagram": {"max_chars": 2200, "max_hashtags": 30},
}

# Deterministic system prompt per platform — no free-form reasoning
SYSTEM_PROMPTS: dict[Platform, str] = {
    "twitter": (
        "You are a Twitter/X copywriter. Write punchy, engaging tweets under 240 characters "
        "(leave room for hashtags). Use simple language. One clear point per tweet. "
        "Never use more than 3 hashtags. Output ONLY the tweet text, no explanation."
    ),
    "linkedin": (
        "You are a LinkedIn content strategist. Write professional, value-driven posts. "
        "Start with a hook on line 1. Use short paragraphs. End with a question or CTA. "
        "Include relevant hashtags at the end. Output ONLY the post text, no explanation."
    ),
    "facebook": (
        "You are a Facebook community manager. Write conversational, engaging posts. "
        "Be friendly and relatable. Use emojis sparingly. Ask a question to drive comments. "
        "Output ONLY the post text, no explanation."
    ),
    "instagram": (
        "You are an Instagram content creator. Write engaging captions that complement an image. "
        "Start with a strong hook. Tell a micro-story. Use line breaks for readability. "
        "End with a CTA. Add relevant hashtags at the end. Output ONLY the caption, no explanation."
    ),
}


class SocialMediaAgent:
    """Phase 2 custom agent — deterministic social media content workflow.

    Uses the Anthropic SDK directly (not Claude Code) so it can be deployed
    independently and is not tied to the Claude Code session.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )
        # Model can be swapped via model_config.yaml / MODEL_PROFILE env
        self._model = os.environ.get("SOCIAL_AGENT_MODEL", "claude-haiku-4-5-20251001")

    def generate(self, brief: ContentBrief) -> GeneratedPost:
        """Generate a social media post from a content brief.

        This is deterministic: same brief → consistent format every time.
        """
        rules = PLATFORM_RULES[brief.platform]
        system = SYSTEM_PROMPTS[brief.platform]

        user_prompt = (
            f"Write a {brief.platform} post about: {brief.topic}\n"
            f"Tone: {brief.tone}\n"
            f"Target audience: {brief.target_audience}\n"
        )
        if brief.include_hashtags:
            user_prompt += f"Include up to {rules['max_hashtags']} relevant hashtags.\n"
        if brief.custom_instructions:
            user_prompt += f"Additional instructions: {brief.custom_instructions}\n"
        user_prompt += f"Keep under {rules['max_chars']} characters total."

        if self.config.dev_mode:
            log.info("[DEV_MODE] Would generate %s post for: %s", brief.platform, brief.topic[:50])
            return GeneratedPost(
                platform=brief.platform,
                text=f"[DEV_MODE] Sample {brief.platform} post about: {brief.topic}",
                hashtags=["#ai", "#demo"],
                char_count=50,
            )

        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text.strip()

        # Extract hashtags
        import re
        hashtags = re.findall(r"#\w+", text)
        hashtags = hashtags[:rules["max_hashtags"]]

        # Enforce character limit
        if len(text) > rules["max_chars"]:
            text = text[:rules["max_chars"] - 3] + "..."

        post = GeneratedPost(
            platform=brief.platform,
            text=text,
            hashtags=hashtags,
            char_count=len(text),
        )
        log.info("Generated %s post (%d chars, %d hashtags)", brief.platform, post.char_count, len(post.hashtags))
        return post

    def generate_for_all_platforms(self, topic: str, tone: str = "professional") -> dict[Platform, GeneratedPost]:
        """Generate a post for all platforms from a single topic.

        This is the agent's main task loop — one topic in, four posts out.
        """
        results: dict[Platform, GeneratedPost] = {}
        for platform in ("twitter", "linkedin", "facebook", "instagram"):
            brief = ContentBrief(topic=topic, platform=platform, tone=tone)
            results[platform] = self.generate(brief)
        return results

    def request_approval_and_post(self, post: GeneratedPost) -> dict:
        """Write the post to vault for approval, then post on approval signal.

        This uses the same file-based HITL approval flow as the rest of the system,
        keeping the Phase 2 agent consistent with Phase 1 infrastructure.
        """
        from datetime import datetime, timezone
        vault = self.config.vault_path
        pending_dir = vault / "Needs_Action"
        pending_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
        filename = f"SOCIAL_{post.platform.upper()}_{ts}.md"
        path = pending_dir / filename

        path.write_text(
            f"---\n"
            f"type: social_post\n"
            f"platform: {post.platform}\n"
            f"char_count: {post.char_count}\n"
            f"created: {datetime.now(timezone.utc).isoformat()}\n"
            f"status: pending_approval\n"
            f"action: {post.platform}_post\n"
            f"---\n\n"
            f"## Post Content\n\n"
            f"{post.text}\n\n"
            f"## Hashtags\n{' '.join(post.hashtags)}\n\n"
            f"## Reply Body\n\n"
            f"{post.text}\n",
            encoding="utf-8",
        )
        log.info("Post queued for approval: %s", filename)
        return {"status": "pending_approval", "file": filename}


def run_demo(topic: str = "AI is transforming how we work") -> None:
    """Demo: generate posts for all platforms and print them."""
    agent = SocialMediaAgent()
    print(f"\nGenerating posts for: '{topic}'\n{'='*60}")
    results = agent.generate_for_all_platforms(topic)
    for platform, post in results.items():
        print(f"\n[{platform.upper()}] ({post.char_count} chars)")
        print("-" * 40)
        print(post.text)
    print("\nDone.")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    topic = " ".join(sys.argv[1:]) or "AI is transforming how we work"
    run_demo(topic)
