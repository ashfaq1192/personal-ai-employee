# Personal AI Employee (Digital FTE) Constitution

## Core Principles

### I. Local-First Architecture
All data resides locally in an Obsidian vault. Sensitive information (credentials, banking data, personal messages) never leaves the local machine unless explicitly approved. The Obsidian vault serves as both the GUI dashboard and long-term memory. Cloud deployment (Platinum tier) syncs only markdown/state — secrets never sync.

### II. Perception → Reasoning → Action Pipeline
The system follows a strict three-layer architecture:
- **Perception (Watchers):** Lightweight Python sentinel scripts monitor external sources (Gmail, WhatsApp, filesystem, bank APIs) and write `.md` files to `/Needs_Action/`.
- **Reasoning (Claude Code):** Reads from the vault, plans actions, writes `Plan.md` files with checkboxes, and creates approval requests for sensitive operations.
- **Action (MCP Servers):** External actions (send email, make payment, post to social media) are executed only through MCP servers, never directly.

### III. Human-in-the-Loop (HITL) — NON-NEGOTIABLE
Sensitive actions MUST require explicit human approval via file-based workflow:
- Claude writes approval requests to `/Pending_Approval/`.
- Human reviews and moves files to `/Approved/` or `/Rejected/`.
- System executes ONLY after approval is detected.
- Payments to new recipients, large amounts (>$100), bulk email sends, and DMs always require approval.
- Auto-approve thresholds defined in `Company_Handbook.md`.

### IV. Agent Skills Pattern
All AI functionality MUST be implemented as Agent Skills. This ensures modularity, reusability, and clear capability boundaries. Each skill is a self-contained unit that can be independently developed, tested, and deployed.

### V. Security & Privacy by Design
- Credentials managed via environment variables and `.env` files (never committed to VCS).
- All scripts support `--dry-run` mode and `DEV_MODE` flag during development.
- Rate limiting on all external actions (max 10 emails/hour, max 3 payments/hour).
- Comprehensive audit logging in `/Vault/Logs/YYYY-MM-DD.json` with 90-day retention.
- Permission boundaries enforced per action category (see Section 6.4 of hackathon doc).

### VI. Graceful Degradation & Fault Tolerance
- Transient errors use exponential backoff retry.
- Authentication failures alert human and pause operations.
- Component failures degrade gracefully — watchers continue queuing even if Claude is unavailable.
- Banking/payment actions are NEVER auto-retried; always require fresh approval.
- Process management (PM2/supervisord) keeps watchers alive; watchdog monitors health.

## Technology Stack

| Component | Technology | Role |
|-----------|-----------|------|
| Knowledge Base / GUI | Obsidian (local Markdown) | Dashboard, memory, task management |
| Reasoning Engine | Claude Code (claude-opus-4-6 or via Router) | Planning, decision-making, orchestration |
| External Integration | MCP Servers (Python primary; npx for community tools) | Gmail, Social Media, Accounting, Browser |
| Watchers (Perception) | Python sentinel scripts | Gmail, WhatsApp, filesystem, finance monitoring |
| Browser Automation | Playwright | Payment portals, web interactions |
| Orchestration | Python `orchestrator.py` | Scheduling, folder watching, process management |
| Process Management | PM2 or supervisord | Daemon lifecycle, auto-restart, boot persistence |
| Version Control | Git / GitHub Desktop | Vault versioning, collaboration |

## Vault Structure (Canonical)

```
/Vault/
├── Dashboard.md              # Real-time status summary
├── Company_Handbook.md        # Rules of engagement, thresholds
├── Business_Goals.md          # Objectives, KPIs, targets
├── Inbox/                     # Raw incoming items
├── Needs_Action/              # Actionable items for Claude
├── Plans/                     # Claude-generated action plans
├── Pending_Approval/          # HITL approval requests
├── Approved/                  # Human-approved actions
├── Rejected/                  # Human-rejected actions
├── In_Progress/<agent>/       # Claimed tasks (claim-by-move)
├── Done/                      # Completed items
├── Accounting/                # Financial records, transactions
├── Invoices/                  # Generated invoices
├── Briefings/                 # CEO briefings, audit reports
├── Logs/                      # Audit logs (JSON, 90-day retention)
└── Active_Project/            # Project-based work items
```

## Tiered Delivery Model

| Tier | Scope | Estimated Effort |
|------|-------|-----------------|
| Bronze | Vault + 1 watcher + Claude read/write + folder structure | 8-12 hours |
| Silver | Bronze + 2+ watchers + MCP server + HITL + scheduling + LinkedIn posting | 20-30 hours |
| Gold | Silver + full cross-domain + Odoo ERP + social media + CEO briefing + Ralph Wiggum loop | 40+ hours |
| Platinum | Gold + cloud 24/7 + work-zone specialization + synced vault + cloud Odoo | 60+ hours |

## Development Workflow

1. **Clarify** — Confirm requirements and tier scope before building.
2. **Specify** — Write feature specs with acceptance scenarios (Gherkin-style).
3. **Plan** — Architect the solution; identify MCP servers, watchers, vault structure.
4. **Implement** — Build incrementally: watcher → vault integration → Claude reasoning → MCP action → HITL.
5. **Test** — Dry-run mode first; test with sandbox accounts; verify audit logs.
6. **Review** — Weekly action log review; monthly comprehensive audit.

## Ethical Guardrails

- AI MUST NOT act autonomously on: emotional contexts, legal matters, medical decisions, irreversible actions.
- Disclose AI involvement in outbound communications.
- Maintain full audit trails for all actions.
- The human remains accountable for all AI Employee actions.
- Oversight schedule: daily dashboard check, weekly log review, monthly audit, quarterly security review.

## Governance

- This constitution supersedes all other development practices for this project.
- Amendments require documentation and user approval.
- All code changes must verify compliance with HITL, security, and local-first principles.
- The hackathon document (`hackathon-0.md`) is the authoritative source for project scope and requirements.

**Version**: 1.0.0 | **Ratified**: 2026-02-08 | **Last Amended**: 2026-02-08
