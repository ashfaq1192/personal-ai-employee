"""Social Media Engagement Metrics Collector — real API calls per platform."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v20.0"


# ─── Per-platform metric fetchers ─────────────────────────────────────────────

def _fetch_facebook_metrics(access_token: str, page_id: str, days: int) -> dict[str, Any]:
    """Fetch Page Insights from Facebook Graph API."""
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"{GRAPH_BASE}/{page_id}/insights",
                params={
                    "metric": "page_impressions,page_engaged_users,page_post_engagements,page_fan_adds",
                    "period": "week" if days <= 7 else "month",
                    "access_token": access_token,
                },
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            metrics: dict[str, Any] = {"posts": 0}
            for item in data:
                name = item.get("name", "")
                values = item.get("values", [{}])
                value = values[-1].get("value", 0) if values else 0
                if name == "page_impressions":
                    metrics["impressions"] = value
                elif name == "page_engaged_users":
                    metrics["engaged_users"] = value
                elif name == "page_post_engagements":
                    metrics["reactions"] = value
                elif name == "page_fan_adds":
                    metrics["new_followers"] = value

            # Count recent posts
            posts_resp = client.get(
                f"{GRAPH_BASE}/{page_id}/posts",
                params={"limit": 100, "since": _days_ago_ts(days), "access_token": access_token},
            )
            if posts_resp.is_success:
                metrics["posts"] = len(posts_resp.json().get("data", []))
            return metrics
    except Exception as exc:
        log.warning("Facebook metrics error: %s", exc)
        return {"error": str(exc)}


def _fetch_instagram_metrics(access_token: str, ig_user_id: str, days: int) -> dict[str, Any]:
    """Fetch Instagram Business Account insights."""
    try:
        period = "day"
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"{GRAPH_BASE}/{ig_user_id}/insights",
                params={
                    "metric": "impressions,reach,profile_views,follower_count",
                    "period": period,
                    "since": _days_ago_ts(days),
                    "until": _days_ago_ts(0),
                    "access_token": access_token,
                },
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            metrics: dict[str, Any] = {}
            for item in data:
                name = item.get("name", "")
                total = sum(v.get("value", 0) for v in item.get("values", []))
                metrics[name] = total

            # Count recent media
            media_resp = client.get(
                f"{GRAPH_BASE}/{ig_user_id}/media",
                params={
                    "fields": "id,timestamp",
                    "since": _days_ago_ts(days),
                    "access_token": access_token,
                },
            )
            if media_resp.is_success:
                metrics["posts"] = len(media_resp.json().get("data", []))
            return metrics
    except Exception as exc:
        log.warning("Instagram metrics error: %s", exc)
        return {"error": str(exc)}


def _fetch_twitter_metrics(
    api_key: str, api_secret: str, access_token: str, access_secret: str, days: int
) -> dict[str, Any]:
    """Fetch Twitter/X user tweet metrics via tweepy v2."""
    try:
        import tweepy

        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
        )
        # Get authenticated user ID
        me = client.get_me()
        if not me.data:
            return {"error": "Could not get user ID"}
        user_id = me.data.id

        start_time = datetime.fromtimestamp(
            _days_ago_ts(days), tz=timezone.utc
        ).isoformat()

        tweets = client.get_users_tweets(
            id=user_id,
            tweet_fields=["public_metrics"],
            start_time=start_time,
            max_results=100,
        )

        metrics: dict[str, Any] = {"tweets": 0, "likes": 0, "retweets": 0, "impressions": 0, "replies": 0}
        if tweets.data:
            metrics["tweets"] = len(tweets.data)
            for tweet in tweets.data:
                pm = tweet.public_metrics or {}
                metrics["likes"] += pm.get("like_count", 0)
                metrics["retweets"] += pm.get("retweet_count", 0)
                metrics["impressions"] += pm.get("impression_count", 0)
                metrics["replies"] += pm.get("reply_count", 0)
        return metrics
    except Exception as exc:
        log.warning("Twitter metrics error: %s", exc)
        return {"error": str(exc)}


def _fetch_linkedin_metrics(access_token: str, days: int) -> dict[str, Any]:
    """Fetch LinkedIn post engagement via UGC Posts API."""
    try:
        with httpx.Client(timeout=15) as client:
            # Get authenticated person URN
            me_resp = client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            me_resp.raise_for_status()
            person_urn = me_resp.json().get("sub", "")

            # Get recent shares
            shares_resp = client.get(
                "https://api.linkedin.com/v2/ugcPosts",
                params={"q": "authors", "authors": f"List({person_urn})", "count": 50},
                headers={"Authorization": f"Bearer {access_token}", "X-Restli-Protocol-Version": "2.0.0"},
            )

            metrics: dict[str, Any] = {"posts": 0, "impressions": 0, "likes": 0, "comments": 0, "shares": 0}
            if shares_resp.is_success:
                elements = shares_resp.json().get("elements", [])
                metrics["posts"] = len(elements)

                # Fetch stats for each post
                for elem in elements[:10]:  # limit API calls
                    ugc_urn = elem.get("id", "")
                    if not ugc_urn:
                        continue
                    stats_resp = client.get(
                        "https://api.linkedin.com/v2/organizationalEntityShareStatistics",
                        params={"q": "organizationalEntity", "shares": f"List({ugc_urn})"},
                        headers={"Authorization": f"Bearer {access_token}", "X-Restli-Protocol-Version": "2.0.0"},
                    )
                    if stats_resp.is_success:
                        for stat in stats_resp.json().get("elements", []):
                            ts = stat.get("totalShareStatistics", {})
                            metrics["impressions"] += ts.get("impressionCount", 0)
                            metrics["likes"] += ts.get("likeCount", 0)
                            metrics["comments"] += ts.get("commentCount", 0)
                            metrics["shares"] += ts.get("shareCount", 0)
            return metrics
    except Exception as exc:
        log.warning("LinkedIn metrics error: %s", exc)
        return {"error": str(exc)}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _days_ago_ts(days: int) -> int:
    """Return Unix timestamp for N days ago."""
    import time
    return int(time.time()) - days * 86400


# ─── Main entry point ─────────────────────────────────────────────────────────

def collect_platform_metrics(
    platform: str,
    days: int,
    *,
    # Token kwargs passed from config
    meta_access_token: str = "",
    facebook_page_id: str = "",
    ig_user_id: str = "",
    twitter_api_key: str = "",
    twitter_api_secret: str = "",
    twitter_access_token: str = "",
    twitter_access_secret: str = "",
    linkedin_access_token: str = "",
) -> dict[str, Any]:
    """Collect engagement metrics for a single platform.

    Returns a metrics dict. Keys vary per platform.
    Falls back to empty dict if credentials are missing.
    """
    if platform == "facebook":
        if not meta_access_token or not facebook_page_id:
            return {"error": "META_ACCESS_TOKEN and FACEBOOK_PAGE_ID required"}
        return _fetch_facebook_metrics(meta_access_token, facebook_page_id, days)

    if platform == "instagram":
        if not meta_access_token or not ig_user_id:
            return {"error": "META_ACCESS_TOKEN and IG_USER_ID required"}
        return _fetch_instagram_metrics(meta_access_token, ig_user_id, days)

    if platform == "twitter":
        if not all([twitter_api_key, twitter_api_secret, twitter_access_token, twitter_access_secret]):
            return {"error": "All TWITTER_* credentials required"}
        return _fetch_twitter_metrics(twitter_api_key, twitter_api_secret, twitter_access_token, twitter_access_secret, days)

    if platform == "linkedin":
        if not linkedin_access_token:
            return {"error": "LINKEDIN_ACCESS_TOKEN required"}
        return _fetch_linkedin_metrics(linkedin_access_token, days)

    return {"error": f"Unknown platform: {platform}"}


def generate_metrics_summary(
    vault_path: Path,
    *,
    days: int = 7,
    meta_access_token: str = "",
    facebook_page_id: str = "",
    ig_user_id: str = "",
    twitter_api_key: str = "",
    twitter_api_secret: str = "",
    twitter_access_token: str = "",
    twitter_access_secret: str = "",
    linkedin_access_token: str = "",
) -> str:
    """Collect metrics from all platforms and write /Briefings/YYYY-MM-DD_Social_Metrics.md."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    creds = dict(
        meta_access_token=meta_access_token,
        facebook_page_id=facebook_page_id,
        ig_user_id=ig_user_id,
        twitter_api_key=twitter_api_key,
        twitter_api_secret=twitter_api_secret,
        twitter_access_token=twitter_access_token,
        twitter_access_secret=twitter_access_secret,
        linkedin_access_token=linkedin_access_token,
    )

    platforms = ["linkedin", "facebook", "instagram", "twitter"]
    all_metrics: dict[str, dict[str, Any]] = {}
    for p in platforms:
        all_metrics[p] = collect_platform_metrics(p, days, **creds)
        log.info("Collected %s metrics: %s", p, all_metrics[p])

    def _row(label: str, value: Any) -> str:
        return f"| {label} | {value} |\n"

    def _section(platform: str, m: dict) -> str:
        lines = [f"## {platform.capitalize()}\n", "| Metric | Value |\n", "|--------|-------|\n"]
        if "error" in m:
            lines.append(f"| Status | ⚠️ {m['error']} |\n")
        else:
            for k, v in m.items():
                lines.append(_row(k.replace("_", " ").title(), v))
        return "".join(lines) + "\n"

    content = (
        f"---\n"
        f"generated: {now.isoformat()}\n"
        f"period: last {days} days\n"
        f"type: social_summary\n"
        f"---\n\n"
        f"# Social Media Metrics Summary\n\n"
    )
    for p in platforms:
        content += _section(p, all_metrics[p])

    briefings_dir = vault_path / "Briefings"
    briefings_dir.mkdir(parents=True, exist_ok=True)
    summary_path = briefings_dir / f"{date_str}_Social_Metrics.md"
    summary_path.write_text(content, encoding="utf-8")
    log.info("Social metrics summary written to %s", summary_path)
    return str(summary_path)
