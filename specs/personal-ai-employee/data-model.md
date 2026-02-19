# Data Model: Personal AI Employee

**Date**: 2026-02-08 | **Spec**: `specs/personal-ai-employee/spec.md`

## Entities

### 1. Action Item (Markdown file in `/Needs_Action/`)

```yaml
---
type: email | whatsapp | file_drop | alert | review
id: <unique_id>               # EMAIL_<gmail_id>, WHATSAPP_<contact>_<ts>, FILE_<name>
from: <sender>                 # Email address, WhatsApp contact name, or "system"
subject: <subject_line>        # Email subject, message preview, or file name
received: <ISO8601>            # Timestamp of detection
priority: high | low           # high = known contact or keyword match; low = triage needed
status: pending | in_progress | done | rejected
plan_ref: <path_to_plan>      # Set when Claude creates a plan (null initially)
---

## Content
<raw content or summary>

## Suggested Actions
- [ ] <action 1>
- [ ] <action 2>
```

**Identity**: `id` field is globally unique. For email: Gmail message ID. For WhatsApp: `<contact>_<ISO8601>`. For files: `FILE_<filename>_<timestamp>`.

**State Transitions**:
```
pending → in_progress (Claude picks it up)
in_progress → done (plan executed successfully)
in_progress → rejected (user rejected the plan)
pending → review (Claude cannot classify)
```

### 2. Plan (Markdown file in `/Plans/`)

```yaml
---
id: PLAN_<subject_slug>
created: <ISO8601>
source: <path_to_action_item>
status: pending_approval | approved | in_progress | completed | failed
requires_approval: true | false
approval_ref: <path_to_approval_file>  # null if no approval needed
---

## Objective
<what needs to be done>

## Steps
- [x] <completed step>
- [ ] <pending step>
- [ ] <step requiring approval> → See /Pending_Approval/<file>

## Result
<outcome after execution>
```

**State Transitions**:
```
pending_approval → approved (user approves)
pending_approval → failed (user rejects or expires)
approved → in_progress (orchestrator starts execution)
in_progress → completed (all steps done)
in_progress → failed (error during execution)
```

### 3. Approval Request (Markdown file in `/Pending_Approval/`)

```yaml
---
type: approval_request
action: email_send | payment | social_post | invoice | bulk_action
id: APPROVAL_<action>_<target>_<date>
amount: <number>               # Financial amount (null if non-financial)
recipient: <target>            # Email address, payment recipient, social platform
reason: <why_this_action>
plan_ref: <path_to_plan>
created: <ISO8601>
expires: <ISO8601>             # Default: created + 24 hours
status: pending | approved | rejected | expired
---

## Action Details
<human-readable description of the action>

## To Approve
Move this file to /Approved folder.

## To Reject
Move this file to /Rejected folder.
```

**State Transitions**:
```
pending → approved (user moves to /Approved/)
pending → rejected (user moves to /Rejected/)
pending → expired (orchestrator detects past expires timestamp)
```

### 4. Audit Log Entry (JSON in `/Logs/YYYY-MM-DD.json`)

```json
{
  "timestamp": "2026-01-07T10:30:00Z",
  "action_type": "email_send | payment | social_post | file_move | approval | watcher_event | system",
  "actor": "claude_code | gmail_watcher | whatsapp_watcher | fs_watcher | orchestrator | human",
  "target": "<recipient or file path>",
  "parameters": {
    "subject": "<if email>",
    "amount": "<if payment>",
    "platform": "<if social>"
  },
  "approval_status": "auto_approved | approved | rejected | not_required",
  "approved_by": "human | auto | null",
  "result": "success | failure | queued",
  "error": "<error message if failure, null otherwise>",
  "source_file": "<path to originating action item>"
}
```

**Retention**: 90 days. Files older than 90 days are archived or deleted by a scheduled cleanup job.

### 5. CEO Briefing (Markdown in `/Briefings/`)

```yaml
---
generated: <ISO8601>
period: <start_date> to <end_date>
type: weekly_briefing | social_summary
---

# Monday Morning CEO Briefing

## Executive Summary
<1-2 sentence overview>

## Revenue
- **This Week**: $<amount>
- **MTD**: $<amount> (<percent>% of $<target> target)
- **Trend**: On track | Behind | Ahead

## Completed Tasks
- [x] <task 1>
- [x] <task 2>

## Bottlenecks
| Task | Expected | Actual | Delay |
|------|----------|--------|-------|
| <task> | <days> | <days> | +<days> |

## Proactive Suggestions
### Cost Optimization
- **<service>**: <issue>. Cost: $<amount>/month.
  - [ACTION] <suggested action>

### Upcoming Deadlines
- <deadline 1>: <days remaining>
```

### 6. Company Handbook Configuration (Markdown at vault root)

```yaml
---
last_updated: <ISO8601>
version: <semver>
---

# Company Handbook

## Communication Rules
- Tone: professional | friendly | formal
- Signature: "<AI-generated. Reviewed by [Name]>"

## Known Contacts
| Name | Email | WhatsApp | Auto-Approve |
|------|-------|----------|--------------|
| Client A | a@email.com | +1234567890 | email_reply |
| Client B | b@email.com | null | none |

## Approval Thresholds
| Action | Auto-Approve Limit | Always Require Approval |
|--------|-------------------|------------------------|
| Email reply | Known contacts | New contacts, bulk |
| Payment | < $50 recurring | > $100, new payees |
| Social post | Scheduled posts | Replies, DMs |
| File ops | Create, read | Delete, move outside vault |

## Rate Limits
- Emails: 10/hour
- Payments: 3/hour
- Social posts: 5/hour

## Approval Expiry
- Default: 24 hours
- Urgent payments: 4 hours
- Social posts: 48 hours

## WhatsApp Keywords
- urgent, asap, invoice, payment, help, deadline, contract
```

### 7. Dashboard (Markdown at vault root)

```yaml
---
last_updated: <ISO8601>
owner: local  # Single-writer: only local agent updates this
---

# AI Employee Dashboard

## Status
- 🟢 Gmail Watcher: Running
- 🟢 WhatsApp Watcher: Running
- 🟢 File Watcher: Running
- 🟢 Orchestrator: Running

## Pending Items
| Folder | Count |
|--------|-------|
| /Needs_Action/ | <n> |
| /Pending_Approval/ | <n> |
| /In_Progress/ | <n> |

## Recent Activity
| Time | Action | Target | Result |
|------|--------|--------|--------|
| <time> | <action> | <target> | ✅/❌ |

## Financials (MTD)
- Revenue: $<amount>
- Expenses: $<amount>
- Pending Invoices: <n>
```

## Entity Relationships

```
Action Item ──creates──→ Plan
Plan ──may create──→ Approval Request
Approval Request ──triggers──→ MCP Action (via Orchestrator)
MCP Action ──produces──→ Audit Log Entry
Audit Log Entry ──summarized in──→ Dashboard
Multiple Audit Logs ──analyzed in──→ CEO Briefing
Company Handbook ──configures──→ All Watchers + Approval Thresholds
Business Goals ──compared against──→ CEO Briefing metrics
```

## File Naming Conventions

| Entity | Pattern | Example |
|--------|---------|---------|
| Email action | `EMAIL_<gmail_id>.md` | `EMAIL_18d5a7b2c3f.md` |
| WhatsApp action | `WHATSAPP_<contact>_<ts>.md` | `WHATSAPP_client_a_2026-02-08T10-30.md` |
| File drop action | `FILE_<filename>.md` | `FILE_report.pdf.md` |
| Plan | `PLAN_<subject_slug>.md` | `PLAN_invoice_client_a.md` |
| Approval | `APPROVAL_<action>_<target>_<date>.md` | `APPROVAL_payment_client_a_2026-02-08.md` |
| Alert | `ALERT_<type>_<ts>.md` | `ALERT_auth_expired_2026-02-08.md` |
| Review | `REVIEW_<subject>.md` | `REVIEW_unclear_request_client_b.md` |
| Briefing | `YYYY-MM-DD_Monday_Briefing.md` | `2026-02-10_Monday_Briefing.md` |
| Log | `YYYY-MM-DD.json` | `2026-02-08.json` |
