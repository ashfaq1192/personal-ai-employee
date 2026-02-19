"""Email MCP Server — exposes send_email, draft_email, search_email tools."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.core.config import Config
from src.core.logger import AuditLogger
from src.core.rate_limiter import RateLimiter
from src.mcp_servers.gmail_service import GmailService

log = logging.getLogger(__name__)

server = Server("email-mcp")
config = Config()
audit = AuditLogger(config.vault_path)
rate_limiter = RateLimiter({"email": config.rate_limit_emails})
gmail = GmailService(config.gmail_credentials_path)


def _check_approval(action: str, recipient: str) -> bool:
    """Defense-in-depth: verify approval exists or action is auto-approved (FR-015a)."""
    approved_dir = config.vault_path / "Approved"
    # Check for matching approval file
    for f in approved_dir.glob("APPROVAL_*.md"):
        text = f.read_text(encoding="utf-8")
        if recipient in text and action in text:
            return True

    # Check auto-approve in Company_Handbook.md
    handbook = config.vault_path / "Company_Handbook.md"
    if handbook.exists():
        content = handbook.read_text(encoding="utf-8")
        if recipient.lower() in content.lower() and "email_reply" in content.lower():
            return True

    return False


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="send_email",
            description="Send an email via Gmail API. Requires prior HITL approval for new contacts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Email body (plain text or HTML)"},
                    "attachment": {"type": "string", "description": "Path to attachment file (optional)"},
                    "reply_to_id": {"type": "string", "description": "Gmail message ID to reply to (optional)"},
                },
                "required": ["to", "subject", "body"],
            },
        ),
        Tool(
            name="draft_email",
            description="Create a draft email in Gmail (does not send).",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "attachment": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        ),
        Tool(
            name="search_email",
            description="Search Gmail inbox with a query string.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Gmail search query"},
                    "max_results": {"type": "integer", "default": 10, "maximum": 50},
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "send_email":
            to = arguments["to"]
            subject = arguments["subject"]
            body = arguments["body"]

            # FR-015a: Validate approval
            if not _check_approval("email_send", to):
                audit.log(
                    action_type="email_send",
                    actor="email_mcp",
                    target=to,
                    parameters={"subject": subject},
                    result="failure",
                    error="No approval found",
                )
                return [TextContent(type="text", text=f"Failed: No approval found for sending to {to}. Create an approval request first.")]

            # Rate limit
            if not rate_limiter.check("email"):
                audit.log(
                    action_type="email_send",
                    actor="email_mcp",
                    target=to,
                    result="failure",
                    error="Rate limit exceeded",
                )
                return [TextContent(type="text", text="Failed: Rate limit exceeded (10 emails/hour)")]

            # DRY_RUN check
            if config.dry_run:
                audit.log(
                    action_type="email_send",
                    actor="email_mcp",
                    target=to,
                    parameters={"subject": subject, "dry_run": True},
                    result="success",
                )
                return [TextContent(type="text", text=f"[DRY_RUN] Email would be sent to {to}: {subject}")]

            result = gmail.send_email(
                to, subject, body,
                attachment=arguments.get("attachment"),
                reply_to_id=arguments.get("reply_to_id"),
            )
            audit.log(
                action_type="email_send",
                actor="email_mcp",
                target=to,
                parameters={"subject": subject, "message_id": result["message_id"]},
                approval_status="approved",
                result="success",
            )
            return [TextContent(type="text", text=f"Email sent to {to}. Message ID: {result['message_id']}")]

        elif name == "draft_email":
            if config.dry_run:
                return [TextContent(type="text", text=f"[DRY_RUN] Draft would be created for {arguments['to']}")]
            result = gmail.draft_email(
                arguments["to"], arguments["subject"], arguments["body"],
                attachment=arguments.get("attachment"),
            )
            audit.log(
                action_type="email_draft",
                actor="email_mcp",
                target=arguments["to"],
                parameters={"subject": arguments["subject"]},
                result="success",
            )
            return [TextContent(type="text", text=f"Draft created. Draft ID: {result['draft_id']}")]

        elif name == "search_email":
            if config.dev_mode:
                return [TextContent(type="text", text="[DEV_MODE] Search not available in dev mode")]
            results = gmail.search_email(
                arguments["query"],
                max_results=arguments.get("max_results", 10),
            )
            return [TextContent(type="text", text=json.dumps(results, indent=2))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as exc:
        audit.log(
            action_type=name,
            actor="email_mcp",
            target=arguments.get("to", ""),
            result="failure",
            error=str(exc)[:200],
        )
        return [TextContent(type="text", text=f"Failed: {exc}")]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
