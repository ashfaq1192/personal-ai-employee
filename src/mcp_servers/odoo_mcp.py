"""Odoo MCP Server — create_invoice, search_invoices, get_financial_summary."""

from __future__ import annotations

import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.core.config import Config
from src.core.logger import AuditLogger
from src.mcp_servers.odoo_client import OdooClient

log = logging.getLogger(__name__)

server = Server("odoo-mcp")
config = Config()
audit = AuditLogger(config.vault_path)


def _get_client() -> OdooClient:
    return OdooClient(
        url=config.odoo_url,
        db=config.odoo_db,
        username=config.odoo_username,
        password=config.odoo_password,
        pending_dir=config.vault_path / "Accounting" / "pending",
    )


def _check_approval(action: str) -> bool:
    """Defense-in-depth: verify approval for invoice creation (FR-015a)."""
    approved_dir = config.vault_path / "Approved"
    for f in approved_dir.glob("APPROVAL_*.md"):
        text = f.read_text(encoding="utf-8")
        if action in text:
            return True
    return False


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="create_invoice",
            description="Create a DRAFT invoice in Odoo (never auto-posts). Requires HITL approval.",
            inputSchema={
                "type": "object",
                "properties": {
                    "partner_name": {"type": "string", "description": "Client/partner name"},
                    "partner_email": {"type": "string", "description": "Client email"},
                    "invoice_lines": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "quantity": {"type": "number"},
                                "unit_price": {"type": "number"},
                            },
                            "required": ["description", "quantity", "unit_price"],
                        },
                    },
                    "currency": {"type": "string", "default": "USD"},
                },
                "required": ["partner_name", "invoice_lines"],
            },
        ),
        Tool(
            name="search_invoices",
            description="Search invoices in Odoo by partner, status, or date range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "partner_name": {"type": "string"},
                    "status": {"type": "string", "enum": ["draft", "posted", "cancel"]},
                    "date_from": {"type": "string", "format": "date"},
                    "date_to": {"type": "string", "format": "date"},
                },
            },
        ),
        Tool(
            name="get_financial_summary",
            description="Get financial summary (revenue, expenses, outstanding) for a period.",
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {"type": "string", "enum": ["week", "month", "quarter", "year"]},
                },
                "required": ["period"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "create_invoice":
            # FR-015a: Require approval
            if not _check_approval("invoice"):
                audit.log(
                    action_type="invoice_create",
                    actor="odoo_mcp",
                    target=arguments.get("partner_name", ""),
                    result="failure",
                    error="No approval found",
                )
                return [TextContent(type="text", text="Failed: Invoice creation requires approval. Create an approval request first.")]

            if config.dry_run:
                audit.log(
                    action_type="invoice_create",
                    actor="odoo_mcp",
                    target=arguments.get("partner_name", ""),
                    parameters={"dry_run": True},
                    result="success",
                )
                return [TextContent(type="text", text=f"[DRY_RUN] Invoice would be created for {arguments['partner_name']}")]

            client = _get_client()
            # Find or create partner
            partners = client.search_read(
                "res.partner",
                [["name", "=", arguments["partner_name"]]],
                ["id", "name"],
            )
            if partners:
                partner_id = partners[0]["id"]
            else:
                partner_id = client.create("res.partner", {
                    "name": arguments["partner_name"],
                    "email": arguments.get("partner_email", ""),
                })

            # Create invoice lines
            lines = []
            for line in arguments["invoice_lines"]:
                lines.append((0, 0, {
                    "name": line["description"],
                    "quantity": line["quantity"],
                    "price_unit": line["unit_price"],
                }))

            invoice_id = client.create("account.move", {
                "move_type": "out_invoice",
                "partner_id": partner_id,
                "invoice_line_ids": lines,
                "state": "draft",
            })

            audit.log(
                action_type="invoice_create",
                actor="odoo_mcp",
                target=arguments["partner_name"],
                parameters={"invoice_id": invoice_id},
                approval_status="approved",
                result="success",
            )
            return [TextContent(type="text", text=f"Draft invoice created. ID: {invoice_id}")]

        elif name == "search_invoices":
            if config.dev_mode:
                return [TextContent(type="text", text="[DEV_MODE] Odoo search not available")]

            client = _get_client()
            domain: list = [["move_type", "=", "out_invoice"]]
            if arguments.get("partner_name"):
                domain.append(["partner_id.name", "ilike", arguments["partner_name"]])
            if arguments.get("status"):
                domain.append(["state", "=", arguments["status"]])
            if arguments.get("date_from"):
                domain.append(["invoice_date", ">=", arguments["date_from"]])
            if arguments.get("date_to"):
                domain.append(["invoice_date", "<=", arguments["date_to"]])

            results = client.search_read(
                "account.move", domain,
                ["name", "partner_id", "amount_total", "state", "invoice_date"],
            )
            return [TextContent(type="text", text=json.dumps(results, indent=2, default=str))]

        elif name == "get_financial_summary":
            if config.dev_mode:
                return [TextContent(type="text", text="[DEV_MODE] Financial summary not available")]

            period = arguments["period"]
            from datetime import date, timedelta
            today = date.today()
            if period == "week":
                date_from = today - timedelta(days=7)
            elif period == "month":
                date_from = today.replace(day=1)
            elif period == "quarter":
                q_start_month = ((today.month - 1) // 3) * 3 + 1
                date_from = today.replace(month=q_start_month, day=1)
            else:  # year
                date_from = today.replace(month=1, day=1)

            date_from_str = date_from.isoformat()
            date_to_str = today.isoformat()

            client = _get_client()

            # Revenue: posted customer invoices
            revenue_records = client.search_read(
                "account.move",
                [
                    ["move_type", "in", ["out_invoice", "out_refund"]],
                    ["state", "=", "posted"],
                    ["invoice_date", ">=", date_from_str],
                    ["invoice_date", "<=", date_to_str],
                ],
                ["amount_total", "move_type"],
            )
            revenue = sum(
                r["amount_total"] * (-1 if r["move_type"] == "out_refund" else 1)
                for r in revenue_records
            )

            # Expenses: posted vendor bills
            expense_records = client.search_read(
                "account.move",
                [
                    ["move_type", "in", ["in_invoice", "in_refund"]],
                    ["state", "=", "posted"],
                    ["invoice_date", ">=", date_from_str],
                    ["invoice_date", "<=", date_to_str],
                ],
                ["amount_total", "move_type"],
            )
            expenses = sum(
                r["amount_total"] * (-1 if r["move_type"] == "in_refund" else 1)
                for r in expense_records
            )

            # Outstanding receivables
            outstanding_records = client.search_read(
                "account.move",
                [
                    ["move_type", "in", ["out_invoice"]],
                    ["state", "=", "posted"],
                    ["payment_state", "!=", "paid"],
                ],
                ["amount_residual"],
            )
            outstanding = sum(r["amount_residual"] for r in outstanding_records)

            summary = {
                "period": period,
                "date_from": date_from_str,
                "date_to": date_to_str,
                "revenue": round(revenue, 2),
                "expenses": round(expenses, 2),
                "net_profit": round(revenue - expenses, 2),
                "outstanding_receivables": round(outstanding, 2),
                "invoice_count": len(revenue_records),
                "expense_count": len(expense_records),
            }
            audit.log(
                action_type="financial_summary",
                actor="odoo_mcp",
                target=period,
                result="success",
            )
            return [TextContent(type="text", text=json.dumps(summary, indent=2))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except ConnectionError as exc:
        return [TextContent(type="text", text=f"Odoo offline — action queued locally. Error: {exc}")]
    except Exception as exc:
        audit.log(action_type=name, actor="odoo_mcp", target="", result="failure", error=str(exc)[:200])
        return [TextContent(type="text", text=f"Failed: {exc}")]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
