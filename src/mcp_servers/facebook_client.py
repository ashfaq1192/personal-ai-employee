"""Facebook Graph API client — Page posting."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.core.retry import with_retry

log = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v20.0"


class FacebookClient:
    """Posts to Facebook Pages via Graph API."""

    def __init__(self, access_token: str, *, dry_run: bool = True) -> None:
        self._user_token = access_token
        self._dry_run = dry_run
        self._page_tokens: dict[str, str] = {}

    def _get_page_token(self, page_id: str) -> str:
        """Exchange user token for a Page Access Token (cached per page)."""
        if page_id not in self._page_tokens:
            with httpx.Client() as client:
                resp = client.get(
                    f"{GRAPH_API_BASE}/{page_id}",
                    params={"fields": "access_token", "access_token": self._user_token},
                )
                resp.raise_for_status()
                self._page_tokens[page_id] = resp.json()["access_token"]
        return self._page_tokens[page_id]

    @with_retry(max_attempts=2, base_delay=3.0, max_delay=30.0)
    def post_to_page(
        self,
        page_id: str,
        message: str,
        *,
        image_url: str | None = None,
        link: str | None = None,
    ) -> dict[str, Any]:
        """Post to a Facebook Page."""
        if self._dry_run:
            log.info("[DRY_RUN] Would post to Facebook page %s: %s", page_id, message[:80])
            return {"status": "dry_run", "page_id": page_id}

        page_token = self._get_page_token(page_id)
        data: dict[str, str] = {
            "message": message,
            "access_token": page_token,
        }
        if link:
            data["link"] = link

        endpoint = f"{GRAPH_API_BASE}/{page_id}"
        if image_url:
            endpoint += "/photos"
            data["url"] = image_url
        else:
            endpoint += "/feed"

        with httpx.Client() as client:
            resp = client.post(endpoint, data=data)
            resp.raise_for_status()
            return {"status": "posted", "post_id": resp.json().get("id", "")}
