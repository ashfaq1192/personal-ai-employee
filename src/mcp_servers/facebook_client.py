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
        image_bytes: bytes | None = None,
        image_filename: str | None = None,
        link: str | None = None,
    ) -> dict[str, Any]:
        """Post to a Facebook Page.

        image_bytes takes priority over image_url.  Pass image_bytes + image_filename
        to upload a local file directly (no public URL required).
        """
        if self._dry_run:
            log.info("[DRY_RUN] Would post to Facebook page %s: %s", page_id, message[:80])
            return {"status": "dry_run", "page_id": page_id}

        page_token = self._get_page_token(page_id)

        with httpx.Client() as client:
            if image_bytes:
                # Binary photo upload — no public URL needed
                resp = client.post(
                    f"{GRAPH_API_BASE}/{page_id}/photos",
                    data={"message": message, "access_token": page_token},
                    files={"source": (image_filename or "image.jpg", image_bytes)},
                )
            elif image_url:
                # Public URL photo upload
                resp = client.post(
                    f"{GRAPH_API_BASE}/{page_id}/photos",
                    data={"url": image_url, "message": message, "access_token": page_token},
                )
            else:
                # Text-only feed post
                data: dict[str, str] = {"message": message, "access_token": page_token}
                if link:
                    data["link"] = link
                resp = client.post(f"{GRAPH_API_BASE}/{page_id}/feed", data=data)

            resp.raise_for_status()
            return {"status": "posted", "post_id": resp.json().get("id", "")}
