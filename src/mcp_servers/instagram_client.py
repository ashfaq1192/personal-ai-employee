"""Instagram Content Publishing API client."""

from __future__ import annotations

import logging
import time
from typing import Any

_CONTAINER_POLL_INTERVAL = 3  # seconds between status checks
_CONTAINER_MAX_WAIT = 60      # seconds before giving up

import httpx

from src.core.retry import with_retry

log = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v20.0"


class InstagramClient:
    """Posts to Instagram via Content Publishing API (Business/Creator accounts)."""

    def __init__(self, access_token: str, page_id: str, *, dry_run: bool = True) -> None:
        self._user_token = access_token
        self._page_id = page_id
        self._dry_run = dry_run
        self._page_token: str | None = None

    def _get_page_token(self) -> str:
        """Exchange user token for a Page Access Token (cached)."""
        if self._page_token is None:
            with httpx.Client() as client:
                resp = client.get(
                    f"{GRAPH_API_BASE}/{self._page_id}",
                    params={"fields": "access_token", "access_token": self._user_token},
                )
                resp.raise_for_status()
                self._page_token = resp.json()["access_token"]
        return self._page_token

    @with_retry(max_attempts=2, base_delay=5.0, max_delay=30.0)
    def post(
        self,
        ig_user_id: str,
        image_url: str,
        caption: str,
    ) -> dict[str, Any]:
        """Two-step publish: create container → publish."""
        if self._dry_run:
            log.info("[DRY_RUN] Would post to Instagram %s: %s", ig_user_id, caption[:80])
            return {"status": "dry_run", "ig_user_id": ig_user_id}

        page_token = self._get_page_token()
        with httpx.Client() as client:
            # Step 1: Create media container
            resp = client.post(
                f"{GRAPH_API_BASE}/{ig_user_id}/media",
                data={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": page_token,
                },
            )
            resp.raise_for_status()
            container_id = resp.json()["id"]

            # Poll until container is FINISHED (replaces fragile fixed sleep)
            waited = 0
            while waited < _CONTAINER_MAX_WAIT:
                status_resp = client.get(
                    f"{GRAPH_API_BASE}/{container_id}",
                    params={"fields": "status_code", "access_token": page_token},
                )
                if status_resp.is_success:
                    status_code = status_resp.json().get("status_code", "")
                    if status_code == "FINISHED":
                        break
                    if status_code == "ERROR":
                        raise RuntimeError("Instagram media container processing failed")
                time.sleep(_CONTAINER_POLL_INTERVAL)
                waited += _CONTAINER_POLL_INTERVAL

            # Step 2: Publish
            resp = client.post(
                f"{GRAPH_API_BASE}/{ig_user_id}/media_publish",
                data={
                    "creation_id": container_id,
                    "access_token": page_token,
                },
            )
            resp.raise_for_status()
            return {"status": "posted", "media_id": resp.json().get("id", "")}
