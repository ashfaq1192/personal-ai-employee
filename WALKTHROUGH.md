# Personal AI Employee — Demo Walkthrough & Judge Q&A

> Reference document for demo day. Open this alongside Obsidian.

---

## What This System Does (One Sentence)

An autonomous AI employee that monitors your Gmail and WhatsApp 24/7, reasons about every message using Claude Code, creates action plans in Obsidian, and executes approved actions (send email, post to LinkedIn, generate invoices) — all without you writing a single line of code per task.

---

## Architecture: The 5 Layers

```
  EXTERNAL WORLD
  ┌────────────┐   ┌─────────────┐   ┌──────────────┐
  │   Gmail    │   │  WhatsApp   │   │  File Drop   │
  └─────┬──────┘   └──────┬──────┘   └──────┬───────┘
        │  polls           │  scans           │  monitors
        ▼                  ▼                  ▼
  ┌──────────────────────────────────────────────────┐
  │  LAYER 1 — PERCEPTION (Watchers)                 │
  │  gmail_watcher.py  whatsapp_watcher.py           │
  │  filesystem_watcher.py                           │
  │  All extend base_watcher.py (poll → write .md)  │
  └────────────────────┬─────────────────────────────┘
                       │ writes EMAIL_*.md / WHATSAPP_*.md
                       ▼
  ╔══════════════════════════════════════════════════╗
  ║  LAYER 2 — VAULT (Obsidian — The Desk)          ║
  ║  ~/AI_Employee_Vault/                            ║
  ║                                                  ║
  ║  /Needs_Action/    ← inbox, all items land here  ║
  ║  /Plans/           ← Claude writes PLAN_*.md     ║
  ║  /Pending_Approval/← approval requests           ║
  ║  /Approved/        ← human drags here = approve  ║
  ║  /Rejected/        ← human drags here = reject   ║
  ║  /Done/            ← completed archive           ║
  ║  /Logs/            ← JSON audit trail            ║
  ║  /Briefings/       ← weekly CEO reports          ║
  ║                                                  ║
  ║  Dashboard.md  Company_Handbook.md               ║
  ║  Business_Goals.md                               ║
  ╚══════════════════════╦═══════════════════════════╝
                         ║ watchdog detects new file
                         ▼
  ┌──────────────────────────────────────────────────┐
  │  LAYER 3 — REASONING (Claude Code)               │
  │                                                  │
  │  orchestrator.py watches /Needs_Action/          │
  │  → new .md file → trigger_reasoning.py           │
  │  → claude --print "Run the <skill> skill."       │
  │                                                  │
  │  Agent Skills (.claude/skills/):                 │
  │    triage-email.md      classify emails          │
  │    process-inbox.md     batch process all items  │
  │    social-scheduler.md  draft LinkedIn posts     │
  │    generate-briefing.md weekly CEO report        │
  │    ralph-vault-processor.md  bulk loop           │
  │                                                  │
  │  Output → PLAN_*.md to /Plans/                   │
  │         → APPROVAL_*.md to /Pending_Approval/    │
  └────────────────────┬─────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
  ┌───────────────┐      ┌──────────────────────────┐
  │  LAYER 4 —    │      │  LAYER 4 — ACTION (MCP)  │
  │  HUMAN LOOP   │      │                          │
  │               │      │  email_mcp.py            │
  │  Review file  │      │    send_email()          │
  │  in Obsidian  │      │    draft_email()         │
  │               │      │    search_email()        │
  │  Drag to      │      │                          │
  │  /Approved/ ──┼─────▶│  social_mcp.py           │
  │               │      │    post_linkedin() ✅    │
  │  or drag to   │      │    post_facebook()       │
  │  /Rejected/   │      │    post_twitter()        │
  └───────────────┘      │                          │
                         │  odoo_mcp.py             │
                         │    create_invoice()      │
                         │    list_invoices()       │
                         └──────────────────────────┘
                                    │
                                    ▼
  ┌──────────────────────────────────────────────────┐
  │  LAYER 5 — ORCHESTRATION (PM2)                   │
  │  ecosystem.config.js                             │
  │                                                  │
  │  pm2 start ecosystem.config.js                  │
  │                                                  │
  │  Process 1: ai-employee-orchestrator             │
  │  Process 2: ai-employee-gmail-watcher            │
  │  Process 3: ai-employee-filesystem-watcher       │
  │  Process 4: ai-employee-web-dashboard (:8080)    │
  │                                                  │
  │  Auto-restart on crash. Starts on OS boot.       │
  └──────────────────────────────────────────────────┘
```

---

## Core Files — One-Line Purpose

### Watchers (src/watchers/)

| File | What it does |
|------|-------------|
| `base_watcher.py` | Abstract template. Defines the `while True → check → write → sleep` loop that all watchers inherit. |
| `gmail_watcher.py` | Polls Gmail API every 2 min for `is:unread is:important`. Loads known contacts from `Company_Handbook.md`. Writes `EMAIL_<id>.md` to `/Needs_Action/`. Auto-refreshes OAuth tokens. |
| `whatsapp_watcher.py` | Uses Playwright to open WhatsApp Web in a persistent browser session. Scans every 30s. Keyword-filters messages (urgent, invoice, payment…). Writes `WHATSAPP_*.md`. |
| `filesystem_watcher.py` | Watches `/Inbox/` for dropped files (PDFs, contracts). Creates `FILE_*.md` for each new drop. |

### Vault Files (~/AI_Employee_Vault/)

| File/Folder | What it does |
|-------------|-------------|
| `/Needs_Action/` | The inbox. Every watcher writes here. Orchestrator fires Claude the moment a new `.md` lands. |
| `/Plans/` | Claude writes `PLAN_*.md` here — YAML frontmatter + step-by-step checklist per item. |
| `/Pending_Approval/` | Sensitive actions wait here. Claude cannot proceed without a human moving the file. Expires in 24h. |
| `/Approved/` | Human drags file here = consent given. Approval watcher calls MCP server immediately. |
| `/Done/` | Completed, rejected, and expired items archived here. |
| `Dashboard.md` | Real-time summary — pending items, recent activity, MTD revenue. Updated every 10 min. |
| `Company_Handbook.md` | Rules of engagement. Known contacts, auto-approve thresholds, rate limits, keyword list. Claude reads this before every decision. **No code change needed to change AI behavior — just edit this file.** |
| `Business_Goals.md` | Revenue targets, active projects, KPIs. Claude uses this for CEO briefings and social content. |

### Reasoning (src/cli/ + .claude/skills/)

| File | What it does |
|------|-------------|
| `trigger_reasoning.py` | Called by orchestrator on new file. Runs `claude --print "Run the <skill> skill."`. 3 retries with backoff. Logs result. |
| `triage-email.md` | Agent Skill: classify one email by intent (invoice/inquiry/support/spam), check known contacts, write plan or flag for review. |
| `process-inbox.md` | Agent Skill: batch process ALL pending items. Write PLAN_*.md per item. Write APPROVAL_*.md for sensitive actions. Update source file status. |
| `social-scheduler.md` | Agent Skill: read Business_Goals.md, draft LinkedIn post, write SOCIAL_*.md plan. Scheduled = auto-approved. |
| `generate-briefing.md` | Agent Skill: runs Sunday 23:00. Reads Done/, Accounting/, Business_Goals.md. Writes Monday CEO Briefing. |
| `ralph-vault-processor.md` | Agent Skill: persistence loop — Claude keeps working until all Needs_Action items are resolved. |

### MCP Servers (src/mcp_servers/)

| File | What it does |
|------|-------------|
| `email_mcp.py` | MCP server. Tools: `send_email()`, `draft_email()`, `search_email()`. Checks `/Approved/` before any send. Rate limit: 10/hr. Respects DRY_RUN. |
| `social_mcp.py` | MCP server. Tools for LinkedIn, Facebook, Instagram, Twitter. Non-scheduled posts need approval. Rate limit: 5/hr. |
| `linkedin_client.py` | HTTP client for LinkedIn Posts API v2 (`/v2/ugcPosts`). Gets user URN, POSTs content as PUBLIC. dry_run mode available. |
| `odoo_mcp.py` | MCP server for Odoo ERP: create_invoice(), list_invoices(), update_invoice() via JSON-RPC. |
| `.mcp.json` | Tells Claude Code which MCP servers to load, how to start them, and which env vars to pass. |

### Orchestration (src/orchestrator/)

| File | What it does |
|------|-------------|
| `orchestrator.py` | Master process. Watches `/Needs_Action/` with `watchdog`. On new file → triggers reasoning. Scheduled tasks: dashboard every 10 min, expiry check every 5 min, weekly briefing Sunday 23:00. |
| `approval_manager.py` | Creates APPROVAL_*.md files. Reads `Company_Handbook.md` for expiry overrides. Auto-rejects expired approvals. |
| `approval_watcher.py` | Watches `/Approved/`. When human drops file → parses YAML → dispatches to MCP server. |
| `ecosystem.config.js` | PM2 config: 4 processes, auto-restart, max 10 restarts, 5s delay, per-process log files. |

### Core Utilities (src/core/)

| File | What it does |
|------|-------------|
| `config.py` | Reads `.env`, exposes typed settings. `DEV_MODE=true` always forces `DRY_RUN=true`. Single source of truth. |
| `logger.py` | Appends structured JSON to `/Logs/YYYY-MM-DD.json`. Every action logged: timestamp, actor, target, parameters, approval_status, result. 90-day retention. |
| `rate_limiter.py` | Hard caps: 10 emails/hr, 3 payments/hr, 5 social/hr. Blocks the action if exceeded — does not queue. |
| `retry.py` | Decorator: exponential backoff, configurable max attempts, delays, exception types. |

---

## The Safety System (4 Layers)

```
1. DEV_MODE / DRY_RUN (.env)
   DEV_MODE=true  → zero API calls, all mock
   DRY_RUN=true   → real reads, no writes
   Current: DEV_MODE=false, DRY_RUN=true

2. Human-in-the-Loop (file move = consent)
   Claude writes APPROVAL_*.md → Pending_Approval/
   You drag to Approved/ → action executes
   You drag to Rejected/ → action cancelled
   After 24h with no move → auto-expired to Rejected/

3. Rate Limiting (rate_limiter.py)
   10 emails/hr, 3 payments/hr, 5 social/hr
   Hard block — cannot be bypassed by Claude

4. Company_Handbook.md (behavior config)
   Edit this plain text file to change AI rules
   No code changes required
   Claude reads it before every decision
```

---

## Data Flow: Email Arrives → Action Executes

```
1. Gmail API (is:unread is:important)
        ↓
2. gmail_watcher.py writes EMAIL_abc123.md to /Needs_Action/
   with YAML: type, from, subject, received, priority=high/low, status=pending

3. orchestrator.py detects new file (watchdog)
        ↓
4. trigger_reasoning.py → claude --print "Run the triage-email skill."
        ↓
5. Claude reads triage-email.md skill
   Reads Company_Handbook.md (known contacts? auto-approve?)
        ↓
6a. If email from new contact needing reply:
    Writes PLAN_reply_abc123.md → /Plans/
    Writes APPROVAL_email_send_abc123.md → /Pending_Approval/
    Updates EMAIL_abc123.md: status=in_progress, plan_ref=Plans/PLAN_reply_abc123.md

6b. If marketing email / no action needed:
    Writes PLAN_batch_archive.md → /Plans/
    No approval needed (read-only operation)
        ↓
7. (If approval needed) You open Obsidian, review APPROVAL_*.md
   Drag to /Approved/
        ↓
8. approval_watcher.py detects file in /Approved/
   Parses YAML frontmatter → gets action=email_send, to=..., subject=...
   Calls email_mcp.py → send_email()
        ↓
9. email_mcp.py re-checks approval (defense-in-depth, FR-015a)
   Checks rate limit
   Calls gmail_service.py → Gmail API → email sent
   Logs to /Logs/YYYY-MM-DD.json
        ↓
10. Approved file moved to /Done/
    Dashboard.md updated
```

---

## Judge Q&A — 15 Questions

---

**Q1: What problem does this solve?**

A senior professional spends 2-3 hours/day on email triage, social media, and client follow-ups. This system handles all of that autonomously. A human FTE works 2,000 hours/year and costs $4,000–8,000/month. This system works 8,760 hours/year at ~$500/month. That's an 85–90% cost reduction per task — typically the threshold where a CEO approves a project without debate.

---

**Q2: How does Claude actually do the reasoning? Walk me through an email arriving.**

Gmail Watcher polls every 2 min, finds a new important email, writes `EMAIL_<id>.md` to `/Needs_Action/` with YAML frontmatter. The Orchestrator's `watchdog` detects the new file and calls `trigger_reasoning.py`, which runs `claude --print "Run the triage-email skill."` from the vault directory. Claude reads the skill prompt from `.claude/skills/triage-email.md`, reads `Company_Handbook.md` to check known contacts, classifies the email, writes `PLAN_*.md` to `/Plans/` with a checklist, and — if a reply to a new contact is needed — writes `APPROVAL_*.md` to `/Pending_Approval/`. The original email file's `status` is updated to `in_progress` with a `plan_ref` pointer.

---

**Q3: What is Human-in-the-Loop and why is it important?**

Claude never sends an email, makes a payment, or posts a social DM on its own. It creates an `APPROVAL_*.md` file in `/Pending_Approval/` with full details of the intended action. You review it in Obsidian. Drag to `/Approved/` = consent. Drag to `/Rejected/` = cancelled. Approvals expire after 24 hours automatically. This prevents autonomous AI accidents. The file-based mechanism also creates a tamper-evident audit trail — every approval decision is a physical file move logged to `/Logs/`.

---

**Q4: What is MCP and why use it instead of calling APIs directly?**

MCP (Model Context Protocol) is Anthropic's standard for giving Claude structured, constrained access to external tools. Instead of Claude generating arbitrary code to call APIs, MCP defines a contract: here are the tools, here are their parameters, here are the return types. Claude calls `send_email(to, subject, body)` through that interface. This means: (1) Claude cannot do anything outside the defined tools, (2) each tool independently enforces rate limits and approval checks, (3) tools are composable across different Claude sessions. Direct API access would be unconstrained. MCP is deliberately limited.

---

**Q5: What are Agent Skills and why implement everything as skills?**

Agent Skills are Markdown files in `.claude/skills/` that contain a structured prompt telling Claude exactly what to do for a specific task — what to read, how to classify, what to write, and what rules to follow. The benefit: behavior is transparent and auditable (anyone can read the `.md` file), and it's configurable without code changes — edit `Company_Handbook.md` to change which contacts are auto-approved without touching Python. This is also the explicit hackathon requirement: "all AI functionality should be implemented as Agent Skills."

---

**Q6: How do you prevent the AI from going rogue?**

Four layers:
1. **DEV_MODE / DRY_RUN** in `.env` — `DRY_RUN=true` means no external writes even if an MCP tool is called.
2. **HITL approval** — every sensitive action requires a physical file move by the human before execution.
3. **Rate limiting** — `rate_limiter.py` enforces hard caps (10 emails/hr, 3 payments/hr, 5 social/hr). Cannot be bypassed by Claude.
4. **Company_Handbook.md** — Claude reads the rules of engagement before every decision. Known contacts and thresholds are explicit.
5. **Approval expiry** — approvals expire after 24h, preventing replay attacks.

---

**Q7: You have 44 emails in /Needs_Action/ — why unprocessed?**

Those were collected when validating the Gmail OAuth integration with `DRY_RUN=true` and the Orchestrator not running in continuous mode. In production — `pm2 start ecosystem.config.js` running 24/7 — every new email triggers Claude within seconds of arrival. The 44 files represent the backlog that a live deployment would have processed. I generated 3 sample `PLAN_*.md` files today from real emails to demonstrate the reasoning loop works.

---

**Q8: How does scheduling work?**

Two layers: **PM2** (`ecosystem.config.js`) starts all four processes on OS boot and auto-restarts any that crash within 5 seconds — this is the always-on guarantee. **APScheduler** inside `orchestrator.py` handles time-based tasks: dashboard update every 10 min, expiry check every 5 min, log cleanup daily at 2 AM, CEO briefing every Sunday at 23:00. On top of that, the Orchestrator uses `watchdog` for event-based triggers — any new file in `/Needs_Action/` fires Claude immediately with no polling delay.

---

**Q9: Explain the Ralph Wiggum Loop simply.**

Claude exits after processing a prompt. For one email that's fine. For 44 emails, you don't want 44 separate invocations. The Ralph Wiggum pattern uses a Stop hook: when Claude tries to exit, the hook checks if the task is complete (all items in `/Needs_Action/` have a `plan_ref` or are in `/Done/`). If not complete, it re-injects the prompt and Claude continues. If complete, it allows exit. Named after the Simpsons character who keeps trying despite everything. Triggered when `/Needs_Action/` exceeds 3 items (configurable threshold).

---

**Q10: What is the difference between DEV_MODE and DRY_RUN?**

`DEV_MODE=true` is a full sandbox — zero API calls, all mock data. Gmail Watcher returns fake emails. LinkedIn client returns a fake response. Nothing touches the internet. Use while developing. `DRY_RUN=true` is safe production mode — real API reads are allowed (Gmail Watcher fetches your actual emails), but writes are logged-only (no emails sent, no posts published). MCP tools log "would have done X" instead of executing. Current setting: `DEV_MODE=false, DRY_RUN=true` — Gmail integration is live, 44 real emails in vault, but nothing goes out without an explicit call.

---

**Q11: How is data stored? Is anything sent to the cloud?**

Everything is stored locally in `~/AI_Employee_Vault/` as plain Markdown files. No cloud sync, no third-party storage. The only things that leave the machine are: Gmail API calls (reading your email), LinkedIn API calls (posting), and Claude Code's LLM inference (prompt sent to Anthropic's API — the reasoning, not your raw email content). Credentials live in `.env` locally, excluded from git via `.gitignore`. The vault itself is never synced to any cloud by default.

---

**Q12: How does the LinkedIn post work technically?**

The `social-scheduler` skill reads `Business_Goals.md` and drafts content. Scheduled posts are auto-approved per `Company_Handbook.md`. `social_mcp.py` calls `LinkedInClient.post()`. The client calls `/v2/userinfo` to get the authenticated user's URN (unique LinkedIn ID), then POSTs to `/v2/ugcPosts` with the content, `lifecycleState: PUBLISHED`, and `visibility: PUBLIC`. The post ID is returned in the `x-restli-id` response header. Today's live post ID: `urn:li:share:7431283914595504128`.

---

**Q13: How would you make this production-ready?**

Three steps: (1) `pm2 start ecosystem.config.js && pm2 save && pm2 startup` — registers PM2 with the OS init system so everything starts on boot. (2) For 24/7 cloud deployment, separate duties: a cloud VM runs email triage and social post drafting in draft-only mode; the local machine handles WhatsApp, payments, and final send/post. They coordinate via Git-synced vault files — secrets never sync. (3) Set `WHATSAPP_SESSION_PATH` to a persistent directory so the Playwright browser session survives reboots without a QR re-scan.

---

**Q14: What would you do differently with more time?**

Three things: (1) Make the vault self-contained by symlinking `.claude/skills/` into `~/AI_Employee_Vault/.claude/skills/` so Claude can be invoked from the vault directory and still find all skills — currently the skills live in the project directory. (2) Make the Email MCP's approval matching more robust — currently it scans approval file text as a string; should parse YAML `id` field for exact match. (3) Add WhatsApp outbound sending — currently the Watcher reads messages but sending requires a separate Playwright interaction script not yet implemented.

---

**Q15: What tier is this and what is your evidence?**

**Platinum tier.** Evidence:
- **Bronze**: Vault with `Dashboard.md`, `Company_Handbook.md`, `/Inbox /Needs_Action /Done` folders, 44 real emails from Gmail, 3 Claude-generated `PLAN_*.md` files in `/Plans/`, 5 Agent Skills in `.claude/skills/`.
- **Silver**: Gmail + WhatsApp + FileSystem watchers, Email MCP in `.mcp.json`, HITL workflow with live approval request in `/Pending_Approval/`, LinkedIn post `urn:li:share:7431283914595504128` posted live today, PM2 scheduling config.
- **Gold**: Social MCP, Odoo MCP, CEO Briefing skill, Ralph Wiggum loop in `.claude/plugins/ralph-wiggum/`.
- **Platinum**: `src/cloud/` with cloud agent + vault sync scripts, claim-by-move multi-agent coordination in `claim_manager.py`, conflict resolver for vault sync.
- 89 passing tests, structured JSON audit logs in `/Logs/`, `HACKATHON_SUBMISSION.md`.

---

## Demo Order (7 minutes)

```
0:00  Open this file + Obsidian vault side by side

1. BRONZE (2 min)
   - Show Dashboard.md (live stats)
   - Show Company_Handbook.md (rules of engagement)
   - Show /Needs_Action/ — 44 real emails from Gmail
   - Show .claude/skills/ — 5 Agent Skills
   - Run: ls ~/AI_Employee_Vault/Plans/ → show 3 PLAN_*.md files

2. SILVER (3 min)
   - Open PLAN_client_invoice_request_acme.md in /Plans/
     "Claude classified this as a client invoice request,
      created a checklist, and identified it needs approval"
   - Open APPROVAL_email_send_demo_client_acme_20260222.md in /Pending_Approval/
     "This is the HITL gate — nothing executes until I drag this file"
   - Drag to /Approved/ — "I just approved the action"
   - Show /Logs/ — audit trail confirms the action
   - Show LinkedIn post live on profile (urn:li:share:7431283914595504128)
   - Show ecosystem.config.js — "PM2 keeps all this running 24/7"

3. ARCHITECTURE (1 min)
   - Show src/ tree: watchers/, orchestrator/, mcp_servers/, core/
   - Point to orchestrator.py — "this is the nerve center"
   - Show .mcp.json — "4 MCP servers wired to Claude Code"

4. SECURITY (1 min)
   - Show .env: DEV_MODE=false, DRY_RUN=true
   - "Nothing goes out without approval + rate limits + audit log"
```

---

*Generated 2026-02-22 | Personal AI Employee Hackathon 0 — Platinum Tier*
