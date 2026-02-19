"""Generate sample week data in a vault for testing the CEO Briefing flow.

Usage:
    uv run python tests/fixtures/generate_sample_week.py [--vault-path /path/to/vault]

Creates sample action items, done files, accounting entries, business goals,
and social media metrics so the briefing skill has realistic data to work with.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def generate_sample_week(vault_path: Path) -> None:
    """Populate a vault with one week of sample data."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # Ensure directories exist
    for folder in [
        "Done", "Needs_Action", "Accounting", "Briefings",
        "Logs", "Pending_Approval",
    ]:
        (vault_path / folder).mkdir(parents=True, exist_ok=True)

    # --- Business_Goals.md ---
    goals = vault_path / "Business_Goals.md"
    goals.write_text(
        "---\n"
        "last_updated: " + now.strftime("%Y-%m-%d") + "\n"
        "---\n\n"
        "# Business Goals\n\n"
        "## Revenue Target\n"
        "- Monthly Target: $15,000\n"
        "- Current MTD: $11,200\n\n"
        "## Key Metrics\n"
        "| Metric | Target | Alert Threshold |\n"
        "|--------|--------|-----------------|\n"
        "| MRR | $15,000 | < $10,000 |\n"
        "| New Clients | 5 | < 2 |\n"
        "| Churn Rate | < 3% | > 5% |\n"
        "| Email Response Time | < 4hr | > 8hr |\n\n"
        "## Active Projects\n"
        "- [ ] Website redesign (due: " + (now + timedelta(days=5)).strftime("%Y-%m-%d") + ")\n"
        "- [ ] Q1 marketing campaign\n"
        "- [x] Client onboarding automation\n",
        encoding="utf-8",
    )

    # --- Done files (completed tasks this week) ---
    done_items = [
        {
            "title": "Reply to Acme Corp inquiry",
            "type": "email_reply",
            "created": (week_ago + timedelta(days=1)).isoformat(),
            "completed": (week_ago + timedelta(days=1, hours=2)).isoformat(),
            "expected_hours": 1,
        },
        {
            "title": "Post LinkedIn company update",
            "type": "social_post",
            "created": (week_ago + timedelta(days=2)).isoformat(),
            "completed": (week_ago + timedelta(days=2, hours=0, minutes=30)).isoformat(),
            "expected_hours": 0.5,
        },
        {
            "title": "Create invoice INV-2026-042 for Beta LLC",
            "type": "invoice",
            "created": (week_ago + timedelta(days=3)).isoformat(),
            "completed": (week_ago + timedelta(days=3, hours=1)).isoformat(),
            "expected_hours": 1,
        },
        {
            "title": "Schedule Instagram posts for next week",
            "type": "social_post",
            "created": (week_ago + timedelta(days=4)).isoformat(),
            "completed": (week_ago + timedelta(days=5, hours=3)).isoformat(),
            "expected_hours": 2,
        },
        {
            "title": "Process expense report from contractor",
            "type": "accounting",
            "created": (week_ago + timedelta(days=5)).isoformat(),
            "completed": (week_ago + timedelta(days=6, hours=8)).isoformat(),
            "expected_hours": 4,
        },
    ]

    for i, item in enumerate(done_items, 1):
        filename = f"DONE_{week_ago.strftime('%Y%m%d')}_{i:02d}_{item['type']}.md"
        content = (
            "---\n"
            f"title: \"{item['title']}\"\n"
            f"type: {item['type']}\n"
            f"created: {item['created']}\n"
            f"completed: {item['completed']}\n"
            f"expected_hours: {item['expected_hours']}\n"
            "status: done\n"
            "---\n\n"
            f"# {item['title']}\n\n"
            "Task completed successfully.\n"
        )
        (vault_path / "Done" / filename).write_text(content, encoding="utf-8")

    # --- Accounting entries ---
    accounting_entries = [
        {"date": (week_ago + timedelta(days=1)).strftime("%Y-%m-%d"), "type": "income", "amount": 3500, "description": "Acme Corp - Monthly retainer", "category": "consulting"},
        {"date": (week_ago + timedelta(days=2)).strftime("%Y-%m-%d"), "type": "income", "amount": 2200, "description": "Beta LLC - Project milestone", "category": "project"},
        {"date": (week_ago + timedelta(days=3)).strftime("%Y-%m-%d"), "type": "expense", "amount": -149, "description": "Figma subscription", "category": "software"},
        {"date": (week_ago + timedelta(days=4)).strftime("%Y-%m-%d"), "type": "expense", "amount": -29, "description": "Notion subscription", "category": "software"},
        {"date": (week_ago + timedelta(days=5)).strftime("%Y-%m-%d"), "type": "income", "amount": 5500, "description": "Gamma Inc - Setup fee", "category": "consulting"},
    ]

    ledger = vault_path / "Accounting" / "ledger.md"
    lines = [
        "---\n",
        f"last_updated: {now.strftime('%Y-%m-%d')}\n",
        "---\n\n",
        "# Accounting Ledger\n\n",
        "| Date | Type | Amount | Description | Category |\n",
        "|------|------|--------|-------------|----------|\n",
    ]
    for entry in accounting_entries:
        sign = f"${entry['amount']:,.2f}" if entry["amount"] >= 0 else f"-${abs(entry['amount']):,.2f}"
        lines.append(
            f"| {entry['date']} | {entry['type']} | {sign} | {entry['description']} | {entry['category']} |\n"
        )
    ledger.write_text("".join(lines), encoding="utf-8")

    # --- Social media metrics summary ---
    metrics_file = vault_path / "Briefings" / f"{week_ago.strftime('%Y-%m-%d')}_Social_Metrics.md"
    metrics_file.write_text(
        "---\n"
        f"generated: {week_ago.isoformat()}\n"
        "period: last 7 days\n"
        "type: social_summary\n"
        "---\n\n"
        "# Social Media Metrics Summary\n\n"
        "## LinkedIn\n"
        "| Metric | Value |\n"
        "|--------|-------|\n"
        "| Posts | 3 |\n"
        "| Impressions | 1,245 |\n"
        "| Likes | 47 |\n"
        "| Comments | 12 |\n\n"
        "## Facebook\n"
        "| Metric | Value |\n"
        "|--------|-------|\n"
        "| Posts | 2 |\n"
        "| Reach | 890 |\n"
        "| Reactions | 34 |\n\n"
        "## Instagram\n"
        "| Metric | Value |\n"
        "|--------|-------|\n"
        "| Posts | 4 |\n"
        "| Impressions | 2,130 |\n"
        "| Likes | 156 |\n\n"
        "## Twitter/X\n"
        "| Metric | Value |\n"
        "|--------|-------|\n"
        "| Tweets | 5 |\n"
        "| Impressions | 3,400 |\n"
        "| Likes | 89 |\n",
        encoding="utf-8",
    )

    # --- Audit logs ---
    log_file = vault_path / "Logs" / f"{now.strftime('%Y-%m-%d')}.json"
    logs = []
    for i, item in enumerate(done_items):
        logs.append({
            "timestamp": item["completed"],
            "action_type": item["type"],
            "actor": "orchestrator",
            "target": item["title"],
            "result": "success",
        })
    log_file.write_text(
        "\n".join(json.dumps(entry) for entry in logs) + "\n",
        encoding="utf-8",
    )

    print(f"Sample week data generated in {vault_path}")
    print(f"  - Business_Goals.md")
    print(f"  - {len(done_items)} Done items")
    print(f"  - {len(accounting_entries)} Accounting entries")
    print(f"  - Social metrics summary")
    print(f"  - Audit logs")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample week data for briefing testing")
    parser.add_argument(
        "--vault-path",
        type=str,
        default=None,
        help="Path to vault (default: from .env VAULT_PATH)",
    )
    args = parser.parse_args()

    if args.vault_path:
        vault_path = Path(args.vault_path).expanduser()
    else:
        from src.core.config import Config
        vault_path = Config().vault_path

    vault_path.mkdir(parents=True, exist_ok=True)
    generate_sample_week(vault_path)


if __name__ == "__main__":
    main()
