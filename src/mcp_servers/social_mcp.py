"""Social Media MCP Server — LinkedIn, Facebook, Instagram, Twitter/X."""

from __future__ import annotations

import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.core.config import Config
from src.core.logger import AuditLogger
from src.core.rate_limiter import RateLimiter
from src.mcp_servers.facebook_client import FacebookClient
from src.mcp_servers.instagram_client import InstagramClient
from src.mcp_servers.linkedin_client import LinkedInClient
from src.mcp_servers.twitter_client import TwitterClient

log = logging.getLogger(__name__)

server = Server("social-mcp")
config = Config()
audit = AuditLogger(config.vault_path)
rate_limiter = RateLimiter({"social": config.rate_limit_social})


def _check_approval(action: str) -> bool:
    """Defense-in-depth: verify approval for non-scheduled posts (FR-015a)."""
    approved_dir = config.vault_path / "Approved"
    for f in approved_dir.glob("APPROVAL_*.md"):
        text = f.read_text(encoding="utf-8")
        if action in text:
            return True
    return False


def _rate_and_approval_check(is_scheduled: bool) -> str | None:
    """Common check for all social posting tools. Returns error message or None."""
    if not is_scheduled and not _check_approval("social_post"):
        return "Failed: Non-scheduled posts require approval"
    if not rate_limiter.check("social"):
        return "Failed: Rate limit exceeded (5 posts/hour)"
    return None


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="post_linkedin",
            description="Post content to LinkedIn (personal or organization page).",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Post content text"},
                    "image_path": {"type": "string", "description": "Path to image file (optional)"},
                    "org_id": {"type": "string", "description": "LinkedIn organization ID (optional)"},
                    "is_scheduled": {"type": "boolean", "default": True},
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="post_facebook",
            description="Post content to a Facebook Page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Facebook Page ID"},
                    "message": {"type": "string", "description": "Post content text"},
                    "image_url": {"type": "string", "description": "URL to image (optional)"},
                    "link": {"type": "string", "description": "Link to share (optional)"},
                    "is_scheduled": {"type": "boolean", "default": True},
                },
                "required": ["page_id", "message"],
            },
        ),
        Tool(
            name="post_instagram",
            description="Post content to Instagram (Business/Creator account required).",
            inputSchema={
                "type": "object",
                "properties": {
                    "ig_user_id": {"type": "string", "description": "Instagram Business user ID"},
                    "image_url": {"type": "string", "description": "Publicly accessible image URL (required)"},
                    "caption": {"type": "string", "description": "Post caption"},
                    "is_scheduled": {"type": "boolean", "default": True},
                },
                "required": ["ig_user_id", "image_url", "caption"],
            },
        ),
        Tool(
            name="post_twitter",
            description="Post a tweet to Twitter/X (280 char limit).",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Tweet text (max 280 chars)", "maxLength": 280},
                    "media_path": {"type": "string", "description": "Path to media file (optional)"},
                    "is_scheduled": {"type": "boolean", "default": True},
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="get_social_metrics",
            description="Get engagement metrics for recent posts on a platform.",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "enum": ["linkedin", "facebook", "instagram", "twitter"]},
                    "days": {"type": "integer", "default": 7},
                },
                "required": ["platform"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "post_linkedin":
            err = _rate_and_approval_check(arguments.get("is_scheduled", True))
            if err:
                return [TextContent(type="text", text=err)]

            client = LinkedInClient(config.linkedin_access_token, dry_run=config.dry_run)
            result = client.post(arguments["text"], image_path=arguments.get("image_path"), org_id=arguments.get("org_id"))
            audit.log(action_type="social_post", actor="social_mcp", target="linkedin", parameters={"text": arguments["text"][:100]}, result="success")
            return [TextContent(type="text", text=f"LinkedIn: {json.dumps(result)}")]

        elif name == "post_facebook":
            err = _rate_and_approval_check(arguments.get("is_scheduled", True))
            if err:
                return [TextContent(type="text", text=err)]

            client = FacebookClient(config.meta_access_token, dry_run=config.dry_run)
            result = client.post_to_page(arguments["page_id"], arguments["message"], image_url=arguments.get("image_url"), link=arguments.get("link"))
            audit.log(action_type="social_post", actor="social_mcp", target="facebook", parameters={"page_id": arguments["page_id"]}, result="success")
            return [TextContent(type="text", text=f"Facebook: {json.dumps(result)}")]

        elif name == "post_instagram":
            err = _rate_and_approval_check(arguments.get("is_scheduled", True))
            if err:
                return [TextContent(type="text", text=err)]

            client = InstagramClient(config.meta_access_token, config.facebook_page_id, dry_run=config.dry_run)
            result = client.post(arguments["ig_user_id"], arguments["image_url"], arguments["caption"])
            audit.log(action_type="social_post", actor="social_mcp", target="instagram", parameters={"caption": arguments["caption"][:100]}, result="success")
            return [TextContent(type="text", text=f"Instagram: {json.dumps(result)}")]

        elif name == "post_twitter":
            err = _rate_and_approval_check(arguments.get("is_scheduled", True))
            if err:
                return [TextContent(type="text", text=err)]

            client = TwitterClient(
                config.twitter_api_key, config.twitter_api_secret,
                config.twitter_access_token, config.twitter_access_secret,
                dry_run=config.dry_run,
            )
            result = client.post(arguments["text"], media_path=arguments.get("media_path"))
            audit.log(action_type="social_post", actor="social_mcp", target="twitter", parameters={"text": arguments["text"][:100]}, result="success")
            return [TextContent(type="text", text=f"Twitter: {json.dumps(result)}")]

        elif name == "get_social_metrics":
            platform = arguments["platform"]
            days = arguments.get("days", 7)
            from src.mcp_servers.social_metrics import collect_platform_metrics
            metrics = collect_platform_metrics(
                platform,
                days,
                meta_access_token=config.meta_access_token,
                facebook_page_id=config.facebook_page_id,
                ig_user_id=config.ig_user_id,
                twitter_api_key=config.twitter_api_key,
                twitter_api_secret=config.twitter_api_secret,
                twitter_access_token=config.twitter_access_token,
                twitter_access_secret=config.twitter_access_secret,
                linkedin_access_token=config.linkedin_access_token,
            )
            return [TextContent(type="text", text=json.dumps({"platform": platform, "days": days, "metrics": metrics}, indent=2))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as exc:
        audit.log(action_type=name, actor="social_mcp", target=arguments.get("platform", "unknown"), result="failure", error=str(exc)[:200])
        return [TextContent(type="text", text=f"Failed: {exc}")]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
