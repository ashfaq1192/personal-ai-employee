# Architecture: Personal AI Employee (Digital FTE)

**Version:** 2.0 — Platinum Tier
**Updated:** 2026-02-27

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component Map](#2-component-map)
3. [Data Flows](#3-data-flows)
4. [Subsystem Reference](#4-subsystem-reference)
5. [Vault (Knowledge Base)](#5-vault-knowledge-base)
6. [Security Architecture](#6-security-architecture)
7. [Ralph Wiggum Pattern](#7-ralph-wiggum-pattern)
8. [Cloud / Local Split](#8-cloud--local-split)
9. [Key Design Decisions](#9-key-design-decisions)

---

## 1. System Overview

The Personal AI Employee is a **local-first autonomous agent** that runs on your machine 24/7 and manages personal and business affairs without constant human supervision. It replaces repetitive knowledge-work tasks by combining:

- **Perception** — Python watchers that detect events (new email, WhatsApp message, file drop)
- **Reasoning** — Claude Code as the AI brain, invoked via subprocess
- **Action** — MCP (Model Context Protocol) servers that execute real-world actions (send email, post to LinkedIn, create invoice)
- **Memory** — An Obsidian markdown vault as the persistent knowledge base and HITL dashboard
- **Persistence** — The Ralph Wiggum stop-hook pattern keeps Claude iterating until tasks are fully complete

```
╔══════════════════════════════════════════════════════════════════════╗
║                   PERSONAL AI EMPLOYEE — SYSTEM                     ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║   ┌─────────────┐   events    ┌──────────────────┐   reads/writes   ║
║   │  WATCHERS   │────────────▶│  ORCHESTRATOR    │◀────────────────▶║
║   │             │             │                  │  ┌─────────────┐ ║
║   │ Gmail       │             │  - Scheduler     │  │   OBSIDIAN  │ ║
║   │ WhatsApp    │             │  - HITL Approval │  │   VAULT     │ ║
║   │ Filesystem  │             │  - Ralph Loop    │  │             │ ║
║   └─────────────┘             │  - Health Mon.   │  │ Needs_Action│ ║
║                               └───────┬──────────┘  │ Pending_Ap. │ ║
║                                       │ invokes      │ Done        │ ║
║                               ┌───────▼──────────┐  │ Briefings   │ ║
║                               │  CLAUDE CODE     │  │ Logs        │ ║
║                               │  (reasoning)     │  └─────────────┘ ║
║                               │  + Ralph hook    │        ▲         ║
║                               └───────┬──────────┘        │         ║
║                                       │ calls              │         ║
║                               ┌───────▼──────────┐        │         ║
║                               │   MCP SERVERS    │────────┘         ║
║                               │                  │  audit + HITL    ║
║                               │ Email / WhatsApp │                  ║
║                               │ LinkedIn / FB    │                  ║
║                               │ Instagram        │                  ║
║                               │ Odoo ERP         │                  ║
║                               └──────────────────┘                  ║
╚══════════════════════════════════════════════════════════════════════╝
```

**Guiding principles:**
- Local-first: secrets and sensitive data never leave your machine
- Human-in-the-loop: every consequential action requires a human to approve via Obsidian
- Smallest viable diff: no action is taken beyond what is explicitly approved
- Audit trail: every action is logged to `vault/Logs/` in append-only markdown

---

## 2. Component Map

```
hackathon-0/
├── main.py                        # CLI entry point
├── ecosystem.config.js            # PM2 process definitions
├── src/
│   ├── core/
│   │   ├── config.py              # Config (VAULT_PATH, DEV_MODE, etc.)
│   │   ├── logger.py              # Append-only audit log writer
│   │   ├── retry.py               # Exponential backoff decorator
│   │   └── rate_limiter.py        # Token-bucket rate limiter
│   │
│   ├── watchers/
│   │   ├── base_watcher.py        # Abstract watcher with restart logic
│   │   ├── gmail_watcher.py       # Polls Gmail API → writes Needs_Action/
│   │   ├── whatsapp_watcher.py    # Playwright/Meta API → writes Needs_Action/
│   │   └── filesystem_watcher.py  # watchdog observer for file-drop inbox
│   │
│   ├── orchestrator/
│   │   ├── orchestrator.py        # Master process: starts all subsystems
│   │   ├── scheduler.py           # APScheduler (cron + interval tasks)
│   │   ├── approval_manager.py    # HITL: creates/expires approval files
│   │   ├── approval_watcher.py    # Watches Approved/ → dispatches MCP action
│   │   ├── claim_manager.py       # Cloud↔Local work-item coordination
│   │   ├── dashboard_updater.py   # Writes counts to Dashboard.md every 10m
│   │   ├── health_monitor.py      # Subprocess health + restart logic
│   │   ├── ralph_integration.py   # Ralph Wiggum batch processor
│   │   └── whatsapp_dispatcher.py # WhatsApp message routing
│   │
│   ├── mcp_servers/
│   │   ├── email_mcp.py           # MCP: send/draft/search email
│   │   ├── social_mcp.py          # MCP: LinkedIn / social posting
│   │   ├── whatsapp_mcp.py        # MCP: WhatsApp send
│   │   ├── odoo_mcp.py            # MCP: Odoo invoice/partner tools
│   │   ├── gmail_service.py       # Gmail API OAuth helper
│   │   ├── linkedin_client.py     # LinkedIn API client
│   │   ├── facebook_client.py     # Facebook Graph API client
│   │   ├── instagram_client.py    # Instagram Graph API client
│   │   ├── twitter_client.py      # Twitter/X API v2 client
│   │   ├── whatsapp_client.py     # Meta WhatsApp Cloud API client
│   │   ├── odoo_client.py         # Odoo JSON-RPC client
│   │   └── social_metrics.py      # Weekly social stats aggregator
│   │
│   ├── cli/
│   │   ├── init_vault.py          # Scaffold vault folders + templates
│   │   ├── trigger_reasoning.py   # Invoke Claude Code as subprocess
│   │   ├── web_dashboard.py       # HTTP dashboard (port 8080)
│   │   ├── status.py              # Print vault counts + process status
│   │   ├── gmail_auth.py          # OAuth2 flow for Gmail
│   │   └── view_logs.py           # Pretty-print audit logs
│   │
│   ├── skills/
│   │   ├── triage_email.md        # Claude skill: categorize + plan reply
│   │   ├── process_inbox.md       # Claude skill: work through Needs_Action
│   │   ├── generate_briefing.md   # Claude skill: CEO Monday briefing
│   │   ├── social_scheduler.md    # Claude skill: schedule social posts
│   │   └── ralph_vault_processor.md # Claude skill: batch process vault
│   │
│   ├── vault/
│   │   └── templates/             # Markdown templates for vault init
│   │
│   └── cloud/
│       ├── agent/cloud_agent.py   # Cloud-side agent (GCP VM)
│       ├── deploy/                # VM setup scripts (nginx, Odoo)
│       └── sync/vault_sync.sh     # Git-based vault sync Cloud↔Local
│
├── scripts/
│   ├── generate_ceo_briefing.py   # CEO Monday briefing generator
│   └── demo_e2e.py                # End-to-end demo scenario
│
├── .claude/
│   ├── settings.json              # Claude Code hooks (Ralph Wiggum Stop)
│   ├── skills/                    # Symlinks to src/skills/*.md
│   └── plugins/ralph-wiggum/      # Stop hook implementation
│       ├── stop_hook.py
│       └── plugin.json
│
└── vault/                         # Symlink → ~/AI_Employee_Vault/
    ├── Needs_Action/              # Inbox: watchers drop items here
    ├── Pending_Approval/          # HITL queue: Claude writes here
    ├── Approved/                  # Human drags/clicks here → action fires
    ├── Rejected/                  # Human rejects → no action
    ├── Done/                      # Completed items archive
    ├── Briefings/                 # CEO briefings + social metrics reports
    ├── Accounting/                # Ledger + transaction history
    ├── Plans/                     # Claude-generated action plans
    ├── Logs/                      # Append-only audit logs
    ├── Inbox/                     # Raw file-drop inbox
    ├── media/                     # Images/attachments for social posts
    ├── Dashboard.md               # Live counts (auto-updated every 10m)
    └── Business_Goals.md          # Revenue targets + project deadlines
```

---

## 3. Data Flows

### 3.1 Email Triage Flow

```
Gmail API
    │
    ▼ (poll every 60s)
gmail_watcher.py
    │  writes
    ▼
vault/Needs_Action/EMAIL_<id>.md
    │
    ▼ (watchdog event)
orchestrator._NeedsActionHandler
    │  calls
    ▼
trigger_reasoning.py --skill triage-email
    │  invokes
    ▼
claude --print "Run the triage-email skill..."
    │  (Claude reads EMAIL_<id>.md, thinks, writes plan)
    ▼
vault/Plans/PLAN_<id>.md          (AI draft + recommended action)
vault/Pending_Approval/APPROVAL_<id>.md  (waits for human)
    │
    ▼ (human approves via dashboard or Obsidian folder move)
approval_watcher.py detects file in Approved/
    │  calls
    ▼
email_mcp.py → Gmail API → reply sent
    │
    ▼
vault/Done/DONE_<id>.md           (audit record)
vault/Logs/<date>.md              (append-only log entry)
```

### 3.2 Social Media Post Flow

```
Human (web dashboard) OR scheduler (Sunday 23:00)
    │
    ▼
POST /api/linkedin/post  (or /facebook/post, /instagram/post)
    │
    ▼
web_dashboard.py → linkedin_client.py / facebook_client.py / instagram_client.py
    │  calls real API
    ▼
Platform API → post published
    │
    ▼
audit.log("social_post", ...)     (audit record)
vault/Briefings/<date>_Social_Metrics.md  (weekly aggregated)
```

### 3.3 CEO Briefing Flow (Scheduled — Sunday 23:00)

```
APScheduler cron: "0 23 sun"
    │
    ▼
orchestrator._trigger_weekly_briefing()
    │  runs
    ▼
scripts/generate_ceo_briefing.py
    │  reads
    ├── vault/Business_Goals.md    (targets, thresholds)
    ├── vault/Accounting/ledger.md (transactions this week)
    ├── vault/Done/*.md            (completed tasks this week)
    └── vault/Briefings/*_Social_Metrics.md (social stats)
    │  writes
    ▼
vault/Briefings/YYYY-MM-DD_Monday_Briefing.md
```

### 3.4 HITL Approval Flow (File-Based)

```
Claude (reasoning) writes approval request:
vault/Pending_Approval/APPROVAL_<action>_<id>.md
    │
    │  ← Human sees it in Obsidian or web dashboard
    │
    ├── Human moves to vault/Approved/   → action executes
    └── Human moves to vault/Rejected/  → action cancelled
                                         (auto-expires in 24h)
```

### 3.5 Ralph Wiggum Persistence Loop

```
Needs_Action has N > threshold items
    │
    ▼
orchestrator._check_ralph_batch() (every 2 min)
    │
    ▼
ralph_integration.start_ralph_loop(prompt, max_iterations=10)
    │  loop:
    │    claude --print "<process Needs_Action prompt>"
    │        │
    │        ├── Claude works → outputs TASK_COMPLETE → loop exits ✓
    │        │
    │        └── Claude exits without TASK_COMPLETE
    │                 │
    │                 ▼
    │            .claude/plugins/ralph-wiggum/stop_hook.py (Stop hook)
    │                 │  checks: Needs_Action empty? TASK_COMPLETE in output?
    │                 ├── YES → allow exit → loop exits ✓
    │                 └── NO  → {"decision":"block"} → Claude re-prompted
    │
    ▼ (max_iterations safety limit)
audit log: "max_iterations_reached"
```

---

## 4. Subsystem Reference

### 4.1 Watchers

| Watcher | Trigger | Output |
|---------|---------|--------|
| `gmail_watcher.py` | Gmail API poll (60s interval) | `Needs_Action/EMAIL_<id>.md` |
| `whatsapp_watcher.py` | Meta WhatsApp Cloud API webhook | `Needs_Action/WHATSAPP_<id>.md` |
| `filesystem_watcher.py` | watchdog `FileCreatedEvent` on `Inbox/` | `Needs_Action/<filename>` |

All watchers inherit from `base_watcher.py` which provides:
- Graceful shutdown via `threading.Event`
- Exception isolation (watcher crash does not kill orchestrator)
- Configurable poll interval

### 4.2 MCP Servers

| Server | Tools | Auth |
|--------|-------|------|
| `email_mcp.py` | `send_email`, `draft_email`, `search_emails` | Gmail OAuth2 (`token.json`) |
| `social_mcp.py` | `post_linkedin`, `post_facebook`, `post_instagram`, `post_twitter` | Per-platform tokens (`.env`) |
| `whatsapp_mcp.py` | `send_whatsapp_message` | Meta Cloud API token (`.env`) |
| `odoo_mcp.py` | `create_invoice`, `list_partners`, `get_financial_summary` | Odoo JSON-RPC (`.env`) |

All MCP servers are registered in `~/.config/claude-code/mcp.json` for Claude Code to discover.

### 4.3 Orchestrator Scheduled Tasks

| Job Name | Schedule | Function |
|----------|----------|----------|
| `check_expired_approvals` | every 5 min | Expire approvals older than 24h |
| `update_dashboard` | every 10 min | Rewrite `Dashboard.md` with counts |
| `log_cleanup` | daily 02:00 | Remove audit logs older than 90 days |
| `weekly_briefing` | Sunday 23:00 | Generate Monday CEO briefing |
| `ralph_batch_check` | every 2 min | Start Ralph loop if Needs_Action > threshold |

### 4.4 Web Dashboard

Single-file HTTP server (`web_dashboard.py`, port 8080) with a dark-theme React-style UI.

**Tabs:** Email | WhatsApp | Social | Odoo | Approvals | Audit Log | CEO Briefing

**API endpoints (GET):**

| Endpoint | Returns |
|----------|---------|
| `/api/status` | Vault counts, PM2 processes, mode |
| `/api/emails` | Items in Needs_Action |
| `/api/whatsapp` | WhatsApp items in Needs_Action |
| `/api/plans` | Items in Plans/ |
| `/api/pending` | Items in Pending_Approval |
| `/api/logs` | Last 40 audit log entries |
| `/api/briefings` | CEO briefings (newest first) |

**API endpoints (POST):**

| Endpoint | Action |
|----------|--------|
| `/api/gmail/pull` | Pull new Gmail messages now |
| `/api/email/reply` | Send email reply |
| `/api/linkedin/post` | Post to LinkedIn |
| `/api/facebook/post` | Post to Facebook Page |
| `/api/instagram/post` | Post to Instagram (media + caption) |
| `/api/odoo/summary` | Fetch Odoo financial summary |
| `/api/briefing/generate` | Generate CEO briefing now |
| `/api/approve` | Move approval file to Approved/ |
| `/api/reject` | Move approval file to Rejected/ |

---

## 5. Vault (Knowledge Base)

The Obsidian vault is the **system of record** for all state. It acts as:
- **Inbox** — watchers write here, Claude reads here
- **HITL dashboard** — humans approve/reject via folder moves or web UI
- **Audit archive** — every action is logged in `Logs/`
- **CEO dashboard** — `Dashboard.md` and `Briefings/` are always readable

```
~/AI_Employee_Vault/
├── Needs_Action/          # Unprocessed items — Claude's to-do list
├── Pending_Approval/      # Awaiting human decision (auto-expires 24h)
├── Approved/              # Human said yes → action will fire
├── Rejected/              # Human said no → archived
├── Done/                  # Completed items (kept for briefing generation)
├── Plans/                 # Claude reasoning artifacts
├── Briefings/             # Monday briefings + social metrics reports
├── Accounting/
│   ├── ledger.md          # Transaction log (income/expense rows)
│   └── pending/           # Unreconciled items
├── Logs/
│   └── YYYY-MM-DD.md      # Append-only daily audit log
├── Inbox/                 # File-drop trigger folder
├── media/                 # Attachments for social posts
├── Dashboard.md           # Real-time summary (updated every 10m)
├── Business_Goals.md      # Revenue targets, metrics, active projects
└── Company_Handbook.md    # Agent persona, response style, rules
```

---

## 6. Security Architecture

### 6.1 Credential Management

- All secrets stored in `.env` (gitignored)
- `.env` is never synced to cloud vault (`vault_sync.sh` excludes it)
- Banking credentials use OS keychain or dedicated secrets manager
- OAuth tokens (`token.json`) are local-only, not in vault
- API keys are short-lived; rotated monthly via `.env` update

### 6.2 DEV_MODE / DRY_RUN

```
DEV_MODE=true  →  DRY_RUN=true  (always; defense-in-depth)
DEV_MODE=false →  DRY_RUN depends on DRY_RUN env var
```

In dry-run mode:
- MCP servers log the action but do not call external APIs
- Approval files are created but marked `[DRY RUN]`
- Claude is still invoked (reasoning happens, no side effects)

### 6.3 HITL as Security Boundary

The HITL approval workflow is the primary security boundary:

```
Claude can only:
  - READ vault files
  - WRITE to Plans/ and Pending_Approval/

Claude cannot:
  - Send email (MCP requires approval first)
  - Post to social media (MCP called by approval_watcher after human OK)
  - Move money / create invoices without approval
```

The only exceptions are read-only operations (search, summarize, classify).

### 6.4 Audit Logging

Every action is logged to `vault/Logs/YYYY-MM-DD.md`:

```markdown
| 2026-02-27 07:14:22 | email_send | approval_watcher | user@acme.com | approved | human |
```

Logs include: timestamp, action type, actor, target, result, approval status, approved_by.

---

## 7. Ralph Wiggum Pattern

The "Ralph Wiggum" pattern solves the **lazy agent** problem — Claude's natural tendency to stop after producing a plan, even when execution is still needed.

### How it works

Claude Code has a **Stop hook** mechanism: a script that runs whenever Claude tries to exit. If the script outputs `{"decision": "block"}`, Claude is re-prompted instead of exiting.

```
.claude/settings.json:
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "python3 .claude/plugins/ralph-wiggum/stop_hook.py"
      }]
    }]
  }
}
```

The stop hook (`stop_hook.py`) checks:
1. Does the last assistant output contain `TASK_COMPLETE`? → allow exit
2. Is `vault/Needs_Action/` empty? → allow exit
3. Otherwise → block exit, Claude continues

### Two completion strategies

| Strategy | How | Best for |
|----------|-----|----------|
| Promise-based | Claude outputs `TASK_COMPLETE` | Simple batch tasks |
| File-movement | Needs_Action empties naturally | Vault-based workflows |

### Safety

- `max_iterations` cap (default 10) prevents infinite loops
- `ralph_state.json` tracks iteration count + status for observability
- Each iteration is independently logged to audit trail

---

## 8. Cloud / Local Split

For Platinum-tier 24/7 operation, the system splits across two agents:

```
┌─────────────────────────────┐     Git sync      ┌─────────────────────────────┐
│      CLOUD AGENT (GCP)      │◀─────────────────▶│      LOCAL AGENT            │
│                             │   vault/          │                             │
│  Owns:                      │   (markdown only) │  Owns:                      │
│  - Email triage             │                   │  - Human approvals          │
│  - Social scheduling        │                   │  - WhatsApp session         │
│  - CEO briefing drafts      │                   │  - Banking credentials      │
│  - Odoo read/reporting      │                   │  - Final send/post actions  │
│                             │                   │  - Payment execution        │
│  24/7 always-on (GCP VM)    │                   │  - Local Obsidian vault     │
└─────────────────────────────┘                   └─────────────────────────────┘
```

**Sync mechanism:** `src/cloud/sync/vault_sync.sh` — Git push/pull on vault repo.

**Coordination:** `claim_manager.py` implements claim-by-move — an agent claims a work item by renaming it with a `CLAIMED_<agent-id>_` prefix, preventing double-processing.

**Security rule:** Vault sync includes only markdown/state. Secrets (`.env`, OAuth tokens, WhatsApp sessions) never sync. The cloud agent never holds banking credentials or payment tokens.

---

## 9. Key Design Decisions

### D1: File-based HITL over database
**Decision:** Use Obsidian folder moves (file rename) as the HITL approval mechanism, not a database or API call.
**Rationale:** Zero-dependency (works with any file manager), human-readable, auditable, works offline, and integrates naturally with Obsidian's workflow.
**Trade-off:** Slower than a database poll; mitigated by watchdog filesystem events (sub-second response).

### D2: Python-primary MCP servers (not Node.js)
**Decision:** All MCP servers are Python, even though the MCP ecosystem has many Node.js examples.
**Rationale:** Consistent stack, better integration with existing Python libraries (Gmail API, Odoo XML-RPC, Playwright), single virtualenv to manage.
**Trade-off:** Some MCP SDK features are more mature in Node.js.

### D3: Subprocess-based Claude invocation
**Decision:** Claude Code is invoked as a subprocess (`claude --print <prompt>`) rather than via Anthropic API directly.
**Rationale:** Claude Code brings its own tool-use, hook system, and skill loading — features not available via bare API. Also means the same Claude Code session that a human uses locally is the one that runs autonomously.
**Trade-off:** Subprocess startup latency (~2s); mitigated by batching with Ralph loop.

### D4: Vault as system of record (not a database)
**Decision:** All state — inbox items, approvals, plans, audit logs — lives in Obsidian markdown files.
**Rationale:** Local-first, human-readable, versionable with Git, works without a database server, and Obsidian provides a beautiful free GUI for free.
**Trade-off:** No structured query capability; mitigated by consistent filename conventions and frontmatter.

### D5: APScheduler over cron
**Decision:** Use APScheduler (in-process) for scheduling instead of system cron.
**Rationale:** No system-level setup required, portable across macOS/Linux/WSL2, configurable at runtime, and logs via Python's standard logging.
**Trade-off:** Jobs stop if the orchestrator process dies; mitigated by PM2 with auto-restart.

### D6: DEV_MODE implies DRY_RUN
**Decision:** `DEV_MODE=true` always forces `DRY_RUN=true`, regardless of the `DRY_RUN` env var.
**Rationale:** Defense-in-depth. A developer running locally should never accidentally send a real email or post to social media, even if they forget to set `DRY_RUN`.
**Trade-off:** Must explicitly set `DEV_MODE=false` to go live.
