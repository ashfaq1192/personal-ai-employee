"""WhatsApp MCP Server — exposes whatsapp_send tool."""

from __future__ import annotations

import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.core.config import Config
from src.core.logger import AuditLogger
from src.core.rate_limiter import RateLimiter
from src.mcp_servers.whatsapp_client import WhatsAppClient

log = logging.getLogger(__name__)

server = Server("whatsapp-mcp")
config = Config()
audit = AuditLogger(config.vault_path)
rate_limiter = RateLimiter({"whatsapp": config.rate_limit_whatsapp})
wa_client = WhatsAppClient(
    access_token=config.whatsapp_access_token,
    phone_number_id=config.whatsapp_phone_number_id,
    dry_run=config.dry_run,
)


def _check_approval(to: str) -> bool:
    """FR-015a: verify APPROVAL_wa_reply_*.md exists for this recipient."""
    approved_dir = config.vault_path / "Approved"
    for f in approved_dir.glob("APPROVAL_wa_reply_*.md"):
        text = f.read_text(encoding="utf-8")
        if to in text and "whatsapp_reply" in text:
            return True
    return False


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="whatsapp_send",
            description=(
                "Send a WhatsApp message via the Business Cloud API. "
                "For scheduled/autonomous messages set is_scheduled=True. "
                "For replies to inbound messages an APPROVAL file must exist."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient phone number in E.164 format (e.g. +923001234567)",
                    },
                    "message": {
                        "type": "string",
                        "description": "Message body text",
                    },
                    "is_scheduled": {
                        "type": "boolean",
                        "description": "True = scheduled/autonomous send (bypasses HITL approval gate)",
                        "default": True,
                    },
                },
                "required": ["to", "message"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "whatsapp_send":
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    to = arguments["to"]
    message = arguments["message"]
    is_scheduled = arguments.get("is_scheduled", True)

    try:
        # FR-015a: approval gate (skip for scheduled outbound)
        if not is_scheduled and not _check_approval(to):
            audit.log(
                action_type="whatsapp_send",
                actor="whatsapp_mcp",
                target=to,
                parameters={"preview": message[:80]},
                result="failure",
                error="No approval found",
            )
            return [TextContent(
                type="text",
                text=f"Failed: No approval found for WhatsApp reply to {to}. "
                     "Create an APPROVAL_wa_reply_*.md in Approved/ first.",
            )]

        # Rate limit
        if not rate_limiter.check("whatsapp"):
            audit.log(
                action_type="whatsapp_send",
                actor="whatsapp_mcp",
                target=to,
                result="failure",
                error="Rate limit exceeded",
            )
            return [TextContent(
                type="text",
                text=f"Failed: Rate limit exceeded ({config.rate_limit_whatsapp} msgs/hour)",
            )]

        # DRY_RUN
        if config.dry_run:
            audit.log(
                action_type="whatsapp_send",
                actor="whatsapp_mcp",
                target=to,
                parameters={"preview": message[:80], "dry_run": True},
                result="success",
            )
            return [TextContent(type="text", text=f"[DRY_RUN] WhatsApp would be sent to {to}: {message[:80]}")]

        result = wa_client.send_message(to, message)
        audit.log(
            action_type="whatsapp_send",
            actor="whatsapp_mcp",
            target=to,
            parameters={"message_id": result.get("message_id", ""), "preview": message[:80]},
            approval_status="approved" if not is_scheduled else "not_required",
            result="success",
        )
        return [TextContent(
            type="text",
            text=f"WhatsApp sent to {to}. Message ID: {result.get('message_id', '')}",
        )]

    except Exception as exc:
        audit.log(
            action_type="whatsapp_send",
            actor="whatsapp_mcp",
            target=to,
            result="failure",
            error=str(exc)[:200],
        )
        return [TextContent(type="text", text=f"Failed: {exc}")]


async def main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
