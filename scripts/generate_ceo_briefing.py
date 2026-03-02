#!/usr/bin/env python3
"""CEO Monday Morning Briefing generator.

Reads vault data (Business_Goals.md, Accounting/ledger.md, Done/, Logs/)
and writes a fully formatted briefing to vault/Briefings/YYYY-MM-DD_Monday_Briefing.md.

Usage:
    uv run python scripts/generate_ceo_briefing.py
    uv run python scripts/generate_ceo_briefing.py --date 2026-03-03
    uv run python scripts/generate_ceo_briefing.py --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import Config
from src.core.logger import AuditLogger


# ─── Vault readers ────────────────────────────────────────────────────────────

def _read_goals(vault: Path) -> dict:
    """Parse Business_Goals.md into a structured dict."""
    gf = vault / "Business_Goals.md"
    if not gf.exists():
        return {}
    text = gf.read_text(encoding="utf-8")

    goals: dict = {}

    # Revenue target
    m = re.search(r"Monthly (?:Target|goal)[:\s]*\$?([\d,]+)", text, re.IGNORECASE)
    if m:
        goals["monthly_target"] = float(m.group(1).replace(",", ""))

    # Current MTD
    m = re.search(r"Current MTD[:\s]*\$?([\d,]+)", text, re.IGNORECASE)
    if m:
        goals["current_mtd"] = float(m.group(1).replace(",", ""))

    # Active projects
    projects = re.findall(r"- \[[ x]\] (.+?)(?:\n|$)", text)
    goals["projects"] = projects

    # Alert thresholds (key metrics table)
    rows = re.findall(r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", text)
    metrics = []
    for row in rows:
        label, target, alert = (c.strip() for c in row)
        if label.lower() in ("metric", "---", "") or label.startswith("-"):
            continue
        metrics.append({"metric": label, "target": target, "alert": alert})
    goals["metrics"] = metrics

    return goals


def _read_ledger(vault: Path, period_start: date, period_end: date) -> dict:
    """Parse Accounting/ledger.md for transactions in the given period."""
    lf = vault / "Accounting" / "ledger.md"
    if not lf.exists():
        return {"income": 0.0, "expenses": 0.0, "transactions": []}

    text = lf.read_text(encoding="utf-8")
    transactions: list[dict] = []

    for line in text.splitlines():
        # Markdown table row: | date | type | amount | description | category |
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 5:
            continue
        date_str, txn_type, amount_str, description, category = (
            parts[0], parts[1], parts[2], parts[3], parts[4]
        )
        try:
            txn_date = date.fromisoformat(date_str)
        except ValueError:
            continue
        if not (period_start <= txn_date <= period_end):
            continue
        amount_str = amount_str.replace("$", "").replace(",", "").strip()
        try:
            amount = float(amount_str)
        except ValueError:
            continue
        transactions.append({
            "date": txn_date,
            "type": txn_type,
            "amount": abs(amount),
            "description": description,
            "category": category,
        })

    income = sum(t["amount"] for t in transactions if t["type"] == "income")
    expenses = sum(t["amount"] for t in transactions if t["type"] == "expense")

    # Detect subscriptions (recurring software expenses)
    SUBSCRIPTION_PATTERNS = {
        "figma": "Figma",
        "notion": "Notion",
        "slack": "Slack",
        "adobe": "Adobe",
        "netflix": "Netflix",
        "spotify": "Spotify",
        "github": "GitHub",
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "aws": "AWS",
        "google": "Google Cloud",
        "zoom": "Zoom",
        "dropbox": "Dropbox",
        "subscription": "Subscription",
    }
    subscriptions = []
    for t in transactions:
        if t["type"] == "expense":
            desc_lower = t["description"].lower()
            for pattern, name in SUBSCRIPTION_PATTERNS.items():
                if pattern in desc_lower:
                    subscriptions.append({"name": name, "amount": t["amount"], "date": t["date"]})
                    break

    return {
        "income": income,
        "expenses": expenses,
        "net": income - expenses,
        "transactions": transactions,
        "subscriptions": subscriptions,
    }


def _read_done_tasks(vault: Path, period_start: date, period_end: date) -> list[dict]:
    """Read Done/ folder for tasks completed in the period."""
    done_dir = vault / "Done"
    if not done_dir.exists():
        return []

    tasks = []
    for f in sorted(done_dir.glob("*.md")):
        mtime = date.fromtimestamp(f.stat().st_mtime)
        if not (period_start <= mtime <= period_end):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        # Parse frontmatter for title/description
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else f.stem

        # Try to find expected vs actual duration from frontmatter
        created_m = re.search(r"created[:\s]+(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        created_date = date.fromisoformat(created_m.group(1)) if created_m else None
        duration_days = (mtime - created_date).days if created_date else None

        tasks.append({
            "filename": f.name,
            "title": title,
            "completed_date": mtime,
            "created_date": created_date,
            "duration_days": duration_days,
        })
    return tasks


def _read_social_metrics(vault: Path) -> str:
    """Get latest social media briefing summary."""
    briefings_dir = vault / "Briefings"
    if not briefings_dir.exists():
        return ""
    social_files = sorted(briefings_dir.glob("*_Social_Metrics.md"))
    if not social_files:
        return ""
    latest = social_files[-1]
    text = latest.read_text(encoding="utf-8", errors="ignore")
    # Extract just first 500 chars of content after frontmatter
    body = re.sub(r"^---.*?---\s*", "", text, flags=re.DOTALL).strip()
    return body[:500] if body else ""


def _read_upcoming_deadlines(vault: Path, today: date) -> list[dict]:
    """Find upcoming deadlines from Business_Goals.md projects."""
    gf = vault / "Business_Goals.md"
    if not gf.exists():
        return []
    text = gf.read_text(encoding="utf-8")
    deadlines = []
    # Match: - [ ] Task name (due: YYYY-MM-DD)
    for m in re.finditer(r"- \[[ x]\] (.+?)(?:\(due:\s*(\d{4}-\d{2}-\d{2})\))?(?:\n|$)", text):
        task = m.group(1).strip()
        due_str = m.group(2)
        if not due_str:
            continue
        due = date.fromisoformat(due_str)
        days_left = (due - today).days
        if 0 <= days_left <= 14:  # next 2 weeks
            deadlines.append({"task": task, "due": due, "days_left": days_left})
    return sorted(deadlines, key=lambda x: x["days_left"])


# ─── Briefing renderer ────────────────────────────────────────────────────────

def _render_briefing(
    period_start: date,
    period_end: date,
    goals: dict,
    ledger: dict,
    done_tasks: list[dict],
    social_snippet: str,
    deadlines: list[dict],
    generated_at: datetime,
) -> str:
    """Build the full markdown briefing document."""

    monthly_target = goals.get("monthly_target", 0)
    current_mtd = goals.get("current_mtd", 0) + ledger.get("income", 0)
    pct = (current_mtd / monthly_target * 100) if monthly_target else 0
    trend = "On track" if pct >= 40 else ("Ahead" if pct >= 60 else "Behind")

    week_income = ledger.get("income", 0)
    week_expenses = ledger.get("expenses", 0)
    week_net = ledger.get("net", 0)

    # Executive summary
    if week_income > 0 and len(done_tasks) > 0:
        summary = f"Active week — ${week_income:,.2f} earned, {len(done_tasks)} tasks completed."
    elif week_income > 0:
        summary = f"Revenue positive week — ${week_income:,.2f} earned."
    elif len(done_tasks) > 0:
        summary = f"Productive week — {len(done_tasks)} tasks completed; no income recorded."
    else:
        summary = "Quiet week — no income or completed tasks recorded in vault."

    # Build completed tasks section
    completed_md = ""
    bottlenecks_rows = ""
    for t in done_tasks:
        completed_md += f"- [x] {t['title']} *(completed {t['completed_date']})*\n"
        if t["duration_days"] and t["duration_days"] > 3:
            expected = max(1, t["duration_days"] // 2)
            bottlenecks_rows += (
                f"| {t['title'][:40]} | {expected}d | {t['duration_days']}d"
                f" | +{t['duration_days'] - expected}d |\n"
            )
    if not completed_md:
        completed_md = "_No tasks moved to /Done this week._\n"

    bottlenecks_md = ""
    if bottlenecks_rows:
        bottlenecks_md = (
            "| Task | Expected | Actual | Delay |\n"
            "|------|----------|--------|-------|\n"
            + bottlenecks_rows
        )
    else:
        bottlenecks_md = "_No bottlenecks detected — all tasks completed on time._\n"

    # Subscriptions / cost optimization
    subs_md = ""
    for s in ledger.get("subscriptions", []):
        subs_md += f"- **{s['name']}**: ${s['amount']:.2f}/mo — review usage\n"
    if not subs_md:
        subs_md = "_No subscription charges detected this week._\n"

    # Deadlines section
    deadlines_md = ""
    for d in deadlines:
        urgency = "⚠️ " if d["days_left"] <= 3 else ""
        deadlines_md += f"- {urgency}**{d['task']}**: due {d['due']} ({d['days_left']} days)\n"
    if not deadlines_md:
        deadlines_md = "_No deadlines in the next 14 days._\n"

    # Metrics section
    metrics_md = ""
    for m in goals.get("metrics", []):
        metrics_md += f"| {m['metric']} | {m['target']} | {m['alert']} | — |\n"
    if metrics_md:
        metrics_md = (
            "| Metric | Target | Alert Threshold | Status |\n"
            "|--------|--------|-----------------|--------|\n"
            + metrics_md
        )

    doc = f"""---
generated: {generated_at.isoformat()}
period: {period_start} to {period_end}
type: weekly_briefing
---

# Monday Morning CEO Briefing
**Period:** {period_start.strftime("%b %d")} – {period_end.strftime("%b %d, %Y")}

## Executive Summary
{summary}

## Revenue
- **This Week**: ${week_income:,.2f}
- **Expenses**: ${week_expenses:,.2f}
- **Net**: ${week_net:,.2f}
- **MTD**: ${current_mtd:,.2f} ({pct:.0f}% of ${monthly_target:,.0f} target)
- **Trend**: {trend}

## Completed Tasks
{completed_md.rstrip()}

## Bottlenecks
{bottlenecks_md.rstrip()}

## Key Metrics
{metrics_md.rstrip() if metrics_md else "_No metrics configured in Business_Goals.md_"}

## Proactive Suggestions

### Cost Optimization
{subs_md.rstrip()}

### Upcoming Deadlines
{deadlines_md.rstrip()}

{f"### Social Media Snapshot{chr(10)}{social_snippet}{chr(10)}" if social_snippet else ""}
---
*Generated by AI Employee — {generated_at.strftime("%Y-%m-%d %H:%M UTC")}*
"""
    return doc.strip()


# ─── Main ─────────────────────────────────────────────────────────────────────

def generate_briefing(
    vault: Path,
    target_date: date | None = None,
    dry_run: bool = False,
) -> Path:
    """Generate the CEO briefing and write it to vault/Briefings/."""
    today = target_date or date.today()
    # Briefing covers the previous 7 days
    period_end = today - timedelta(days=1)
    period_start = period_end - timedelta(days=6)
    generated_at = datetime.now(timezone.utc)

    print(f"Generating CEO briefing for period {period_start} – {period_end}...")

    goals = _read_goals(vault)
    ledger = _read_ledger(vault, period_start, period_end)
    done_tasks = _read_done_tasks(vault, period_start, period_end)
    social = _read_social_metrics(vault)
    deadlines = _read_upcoming_deadlines(vault, today)

    content = _render_briefing(
        period_start=period_start,
        period_end=period_end,
        goals=goals,
        ledger=ledger,
        done_tasks=done_tasks,
        social_snippet=social,
        deadlines=deadlines,
        generated_at=generated_at,
    )

    briefing_dir = vault / "Briefings"
    briefing_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{today.strftime('%Y-%m-%d')}_Monday_Briefing.md"
    out_path = briefing_dir / filename

    if dry_run:
        print(f"\n[DRY RUN] Would write to: {out_path}\n")
        print(content)
        return out_path

    out_path.write_text(content, encoding="utf-8")
    print(f"Briefing written: {out_path}")

    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CEO Monday Morning Briefing")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print briefing without writing to vault",
    )
    parser.add_argument(
        "--vault",
        type=str,
        default=None,
        help="Override vault path",
    )
    args = parser.parse_args()

    config = Config()
    vault_path = Path(args.vault).expanduser() if args.vault else config.vault_path
    target_date = date.fromisoformat(args.date) if args.date else None

    out = generate_briefing(vault_path, target_date=target_date, dry_run=args.dry_run)

    if not args.dry_run:
        audit = AuditLogger(vault_path)
        audit.log(
            action_type="ceo_briefing",
            actor="generate_ceo_briefing",
            target=str(out),
            parameters={"period_end": str(target_date or date.today())},
            result="success",
        )


if __name__ == "__main__":
    main()
