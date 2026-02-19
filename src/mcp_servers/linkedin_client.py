"""LinkedIn API client — Posts API v2 integration."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.core.retry import with_retry

log = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"


class LinkedInClient:
    """LinkedIn posting via Posts API v2."""

    def __init__(self, access_token: str, *, dry_run: bool = True) -> None:
        self._token = access_token
        self._dry_run = dry_run
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def _get_person_urn(self) -> str:
        """Get the authenticated user's URN."""
        with httpx.Client() as client:
            resp = client.get(f"{LINKEDIN_API_BASE}/userinfo", headers=self._headers)
            resp.raise_for_status()
            return f"urn:li:person:{resp.json()['sub']}"

    @with_retry(max_attempts=2, base_delay=3.0, max_delay=30.0)
    def post(self, text: str, *, image_path: str | None = None, org_id: str | None = None) -> dict[str, Any]:
        """Publish a post to LinkedIn."""
        if self._dry_run:
            log.info("[DRY_RUN] Would post to LinkedIn: %s", text[:80])
            return {"status": "dry_run", "text": text[:80]}

        author = f"urn:li:organization:{org_id}" if org_id else self._get_person_urn()

        body: dict[str, Any] = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        with httpx.Client() as client:
            resp = client.post(
                f"{LINKEDIN_API_BASE}/ugcPosts",
                headers=self._headers,
                json=body,
            )
            resp.raise_for_status()
            return {"status": "posted", "id": resp.headers.get("x-restli-id", "")}
