"""Twitter/X API v2 client via tweepy."""

from __future__ import annotations

import logging
from typing import Any

from src.core.retry import with_retry

log = logging.getLogger(__name__)


class TwitterClient:
    """Posts to Twitter/X via API v2 using tweepy."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_secret: str,
        *,
        dry_run: bool = True,
    ) -> None:
        self._dry_run = dry_run
        self._api_key = api_key
        self._api_secret = api_secret
        self._access_token = access_token
        self._access_secret = access_secret
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        import tweepy

        self._client = tweepy.Client(
            consumer_key=self._api_key,
            consumer_secret=self._api_secret,
            access_token=self._access_token,
            access_token_secret=self._access_secret,
        )
        return self._client

    @with_retry(max_attempts=2, base_delay=3.0, max_delay=30.0)
    def post(self, text: str, *, media_path: str | None = None) -> dict[str, Any]:
        """Post a tweet (max 280 characters)."""
        if len(text) > 280:
            text = text[:277] + "..."

        if self._dry_run:
            log.info("[DRY_RUN] Would tweet: %s", text[:80])
            return {"status": "dry_run", "text": text[:80]}

        client = self._get_client()

        media_ids = None
        if media_path:
            import tweepy
            auth = tweepy.OAuth1UserHandler(
                self._api_key, self._api_secret,
                self._access_token, self._access_secret,
            )
            api = tweepy.API(auth)
            media = api.media_upload(media_path)
            media_ids = [media.media_id]

        response = client.create_tweet(text=text, media_ids=media_ids)
        tweet_id = response.data.get("id", "") if response.data else ""
        return {"status": "posted", "tweet_id": tweet_id}
