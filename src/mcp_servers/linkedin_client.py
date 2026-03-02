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

    def _register_image_upload(self, author: str) -> tuple[str, str]:
        """Register an image upload slot. Returns (upload_url, asset_urn)."""
        with httpx.Client() as client:
            resp = client.post(
                f"{LINKEDIN_API_BASE}/assets?action=registerUpload",
                headers=self._headers,
                json={
                    "registerUploadRequest": {
                        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                        "owner": author,
                        "serviceRelationships": [
                            {
                                "relationshipType": "OWNER",
                                "identifier": "urn:li:userGeneratedContent",
                            }
                        ],
                    }
                },
            )
            resp.raise_for_status()
            value = resp.json()["value"]
            upload_url: str = value["uploadMechanism"][
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
            ]["uploadUrl"]
            asset_urn: str = value["asset"]
            return upload_url, asset_urn

    def _upload_image_bytes(self, upload_url: str, image_bytes: bytes) -> None:
        """PUT binary image data to the pre-signed LinkedIn upload URL."""
        with httpx.Client() as client:
            resp = client.put(
                upload_url,
                content=image_bytes,
                headers={"Authorization": f"Bearer {self._token}"},
            )
            resp.raise_for_status()

    @with_retry(max_attempts=2, base_delay=3.0, max_delay=30.0)
    def post(
        self,
        text: str,
        *,
        image_bytes: bytes | None = None,
        image_filename: str | None = None,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        """Publish a post to LinkedIn, optionally with an attached image.

        Pass image_bytes + image_filename to include an image.
        """
        if self._dry_run:
            log.info("[DRY_RUN] Would post to LinkedIn: %s", text[:80])
            return {"status": "dry_run", "text": text[:80]}

        author = f"urn:li:organization:{org_id}" if org_id else self._get_person_urn()

        asset_urn: str | None = None
        if image_bytes:
            upload_url, asset_urn = self._register_image_upload(author)
            self._upload_image_bytes(upload_url, image_bytes)

        body: dict[str, Any] = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE" if asset_urn else "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        if asset_urn:
            body["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                {
                    "status": "READY",
                    "description": {"text": text[:200]},
                    "media": asset_urn,
                }
            ]

        with httpx.Client() as client:
            resp = client.post(
                f"{LINKEDIN_API_BASE}/ugcPosts",
                headers=self._headers,
                json=body,
            )
            resp.raise_for_status()
            return {"status": "posted", "id": resp.headers.get("x-restli-id", "")}
