# Implementation Plan: Personal AI Employee (Digital FTE)

**Branch**: `personal-ai-employee` | **Date**: 2026-02-08 | **Spec**: `specs/personal-ai-employee/spec.md`
**Input**: Feature specification for Platinum-tier Personal AI Employee with all watchers, MCP servers, HITL, Odoo, social media, CEO briefing, Ralph Wiggum, and cloud deployment.

## Summary

Build a local-first, autonomous AI Employee using Python 3.13 (UV-managed) for watchers and orchestration, MCP servers for external actions, Obsidian as the GUI/memory layer, and Claude Code as the reasoning engine. The system follows a Perception → Reasoning → Action pipeline with mandatory Human-in-the-Loop approval for sensitive operations. Deployment targets local (primary) + GCP Compute Engine (cloud, 24/7) with Git-based vault sync.

## Technical Context

**Language/Version**: Python 3.13 (UV managed) + Node.js 24+ LTS (PM2 process manager + npx community MCP tools)
**Primary Dependencies**: google-api-python-client, playwright, watchdog, httpx, tweepy, mcp SDK, apscheduler
**Storage**: Local filesystem (Obsidian vault: Markdown + JSON), Odoo PostgreSQL (cloud)
**Testing**: pytest (unit/integration), dry-run mode (system testing), manual E2E
**Target Platform**: Linux (WSL2 local dev), Ubuntu 24.04 LTS (GCP cloud)
**Project Type**: Multi-component (Python watchers + Python orchestrator + MCP servers + Claude Code skills)
**Performance Goals**: Gmail detection <2min, WhatsApp <30s, filesystem <5s, orchestrator response <60s
**Constraints**: Rate limits (10 emails/hr, 3 payments/hr), 24h approval expiry, $300 GCP budget (~5 months)
**Scale/Scope**: Single user, 1 local + 1 cloud agent, ~50 emails/day, ~20 WhatsApp messages/day

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Local-First Architecture | ✅ PASS | Vault at `~/AI_Employee_Vault/`, separate from code repo. Secrets never sync. |
| II. Perception → Reasoning → Action | ✅ PASS | Three-layer architecture: Watchers → Claude Code → MCP Servers. |
| III. HITL (Non-Negotiable) | ✅ PASS | File-based approval workflow with 24h expiry. All payments, new contacts, DMs require approval. |
| IV. Agent Skills Pattern | ✅ PASS | All AI functionality implemented as Claude Code Agent Skills. |
| V. Security & Privacy by Design | ✅ PASS | `.env` for credentials, DEV_MODE/dry-run, rate limiting, 90-day audit logs. |
| VI. Graceful Degradation | ✅ PASS | Exponential backoff, PM2 auto-restart, queue-on-failure, never auto-retry payments. |

**Gate Result: PASS** — No violations.

## Project Structure

### Documentation (this feature)

```text
specs/personal-ai-employee/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: Research findings
├── data-model.md        # Phase 1: Entity schemas
├── quickstart.md        # Phase 1: Setup guide
├── contracts/
│   └── mcp-tools.md     # Phase 1: MCP tool contracts
└── tasks.md             # Phase 2: Implementation tasks (via /sp.tasks)
```

### Source Code (repository root)

```text
src/
├── watchers/
│   ├── base_watcher.py          # Abstract base class (BaseWatcher)
│   ├── gmail_watcher.py         # Gmail API polling watcher
│   ├── whatsapp_watcher.py      # Playwright-based WhatsApp Web watcher
│   └── filesystem_watcher.py    # watchdog-based drop folder watcher
├── orchestrator/
│   ├── orchestrator.py          # Master process: scheduling, folder watching, health checks
│   ├── scheduler.py             # APScheduler-based cron-like scheduling
│   └── health_monitor.py        # Watcher process health monitoring
├── mcp_servers/
│   ├── email_mcp.py             # Gmail send/draft/search MCP server
│   ├── social_mcp.py            # LinkedIn/Facebook/Instagram/Twitter MCP server
│   └── odoo_mcp.py              # Odoo JSON-RPC MCP server (wrapper around mcp-odoo-adv)
├── skills/
│   ├── process_inbox.md         # Agent Skill: process /Needs_Action items
│   ├── generate_briefing.md     # Agent Skill: generate CEO briefing
│   ├── triage_email.md          # Agent Skill: triage and classify emails
│   └── social_scheduler.md      # Agent Skill: schedule social media posts
├── vault/
│   ├── init_vault.py            # Vault initialization script
│   └── templates/               # Template files for Dashboard.md, Company_Handbook.md, etc.
├── cli/
│   ├── init_vault.py            # CLI: Initialize vault
│   ├── gmail_auth.py            # CLI: Gmail OAuth2 flow
│   ├── status.py                # CLI: System status check
│   └── view_logs.py             # CLI: View audit logs
├── core/
│   ├── config.py                # Configuration management (env vars, vault path)
│   ├── logger.py                # Audit logger (JSON to /Logs/)
│   ├── retry.py                 # Exponential backoff retry decorator
│   └── rate_limiter.py          # Per-action rate limiting
└── cloud/
    ├── deploy/
    │   ├── setup-vm.sh          # GCP VM provisioning script
    │   ├── install-odoo.sh      # Odoo 19 installation script
    │   └── nginx.conf           # Nginx reverse proxy (HTTPS for Odoo)
    ├── sync/
    │   ├── vault_sync.sh        # Git-based vault sync cron job
    │   └── conflict_resolver.py # Merge conflict handler
    └── agent/
        └── cloud_agent.py       # Cloud-specific orchestrator (draft-only)

tests/
├── unit/
│   ├── test_base_watcher.py
│   ├── test_gmail_watcher.py
│   ├── test_config.py
│   ├── test_logger.py
│   ├── test_retry.py
│   └── test_rate_limiter.py
├── integration/
│   ├── test_vault_init.py
│   ├── test_approval_workflow.py
│   ├── test_orchestrator.py
│   └── test_mcp_email.py
└── conftest.py                  # Shared fixtures (temp vault, mock APIs)

.claude/
├── skills/                      # Agent Skills directory
│   ├── process-inbox.md
│   ├── generate-briefing.md
│   ├── triage-email.md
│   └── social-scheduler.md
└── settings.json                # Claude Code project settings

ecosystem.config.js              # PM2 process configuration
.env.example                     # Environment variable template
.mcp.json                        # MCP server configuration
pyproject.toml                   # UV/Python project config
```

**Structure Decision**: Multi-component layout with clear separation:
- `src/watchers/` — Perception layer (Python sentinel scripts)
- `src/orchestrator/` — Coordination layer
- `src/mcp_servers/` — Action layer (MCP protocol servers)
- `.claude/skills/` — **Canonical** Agent Skills location (Claude Code reads from here)
- `src/skills/` — Agent Skills source files (symlinked into `.claude/skills/`)
- `src/core/` — Shared utilities (config, logging, retry, rate limiting)
- `src/cloud/` — Platinum-tier cloud deployment and sync
- `tests/` — Pytest test suite

## Architecture

### Component Interaction Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SOURCES                           │
│   Gmail API    WhatsApp Web    Drop Folder    Bank APIs          │
└──────┬──────────────┬────────────┬──────────────┬───────────────┘
       │              │            │              │
       ▼              ▼            ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│ PERCEPTION LAYER (src/watchers/)                                │
│  gmail_watcher  whatsapp_watcher  filesystem_watcher            │
│  BaseWatcher ABC: check_for_updates() → create_action_file()   │
│  Managed by Orchestrator (PM2 manages Orchestrator only).       │
│  Writes to ~/AI_Employee_Vault/Needs_Action/                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ .md files
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ OBSIDIAN VAULT (~/AI_Employee_Vault/)                           │
│  /Needs_Action/ → /Plans/ → /Pending_Approval/ → /Done/        │
│  Dashboard.md | Company_Handbook.md | Business_Goals.md         │
│  /Logs/YYYY-MM-DD.json (audit trail)                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ folder change detected
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ ORCHESTRATOR (src/orchestrator/)                                 │
│  Watches: /Needs_Action/, /Approved/, /Pending_Approval/        │
│  Triggers: Claude Code reasoning, MCP actions, scheduled tasks  │
│  Health: monitors watcher PIDs, restarts on crash               │
│  Scheduling: APScheduler for cron-like tasks (briefing, etc.)   │
└──────┬──────────────────────────────────┬───────────────────────┘
       │ triggers Claude                  │ triggers MCP
       ▼                                  ▼
┌──────────────────────┐    ┌────────────────────────────────────┐
│ CLAUDE CODE           │    │ MCP SERVERS (src/mcp_servers/)      │
│ (Reasoning Engine)    │    │  email_mcp: send/draft/search       │
│  Agent Skills:        │    │  social_mcp: LinkedIn/FB/IG/X       │
│  - process-inbox      │    │  odoo_mcp: invoices/payments        │
│  - generate-briefing  │    │  browser_mcp: web interaction       │
│  - triage-email       │    │                                     │
│  Writes: Plans, Approvals │ │  All: DRY_RUN support, rate limiting│
│  Ralph Wiggum loop    │    │  All: audit logging on every action  │
└──────────────────────┘    └────────────────────────────────────┘
```

### Tier Implementation Order

**Bronze (P1 — Foundation)**:
1. `src/core/config.py` — Configuration management
2. `src/core/logger.py` — Audit logging
3. `src/vault/init_vault.py` — Vault initialization
4. `src/watchers/base_watcher.py` — Abstract base class
5. `src/watchers/filesystem_watcher.py` — File drop watcher
6. `src/watchers/gmail_watcher.py` — Gmail watcher
7. `src/watchers/whatsapp_watcher.py` — WhatsApp watcher
8. Claude read/write integration (via Agent Skills)

**Silver (P2 — Functional Assistant)**:
9. `src/orchestrator/orchestrator.py` — Master process
10. `src/mcp_servers/email_mcp.py` — Email MCP server
11. `src/skills/` — Agent Skills (process-inbox, triage-email)
12. HITL approval workflow (orchestrator watches /Approved/)
13. `src/mcp_servers/social_mcp.py` — LinkedIn posting
14. `src/orchestrator/scheduler.py` — Scheduling
15. `ecosystem.config.js` — PM2 configuration

**Gold (P3 — Autonomous Employee)**:
16. `src/mcp_servers/social_mcp.py` — Facebook, Instagram, Twitter/X
17. `src/mcp_servers/odoo_mcp.py` — Odoo integration
18. `src/skills/generate-briefing.md` — CEO Briefing skill
19. Ralph Wiggum integration (use installed plugin)
20. `src/core/retry.py` + `src/core/rate_limiter.py` — Resilience

**Platinum (P4 — Always-On Cloud)**:
21. `src/cloud/deploy/` — GCP VM setup, Odoo install, nginx
22. `src/cloud/sync/vault_sync.sh` — Git-based vault sync
23. `src/cloud/agent/cloud_agent.py` — Cloud orchestrator (draft-only)
24. Work-zone specialization (claim-by-move rule)
25. End-to-end Platinum demo

### Key Design Decisions

**D1: Vault separate from code repo**
- Code: `/mnt/d/projects/hackathon-0/` (this repo)
- Vault: `~/AI_Employee_Vault/` (configured via `VAULT_PATH`)
- Rationale: Runtime data (logs, action items) doesn't belong in code VCS

**D2: Python for watchers, MCP servers in Python (not Node.js)**
- All MCP servers written in Python using `mcp` Python SDK
- Rationale: Single language (Python) for the entire stack reduces complexity. UV manages all dependencies. Node.js only used for PM2 and npx-based community MCP servers (e.g., mcp-odoo-adv).

**D3: APScheduler over cron**
- Orchestrator uses APScheduler for scheduling (briefing, social posts, cleanup)
- Rationale: In-process scheduling is more portable (works on Windows/Linux/Mac without OS-level cron)

**D4: Orchestrator as single process, watchers as child processes**
- Orchestrator spawns and monitors watchers as subprocesses
- PM2 manages the orchestrator (which manages its children)
- Rationale: Simpler than PM2 managing N separate processes; health checks are internal

**D5: Ralph Wiggum via official plugin (not custom)**
- Use the installed `ralph-loop` plugin at `~/.claude/plugins/`
- Orchestrator triggers Claude with `/ralph-loop` for complex multi-step tasks
- Rationale: Mature implementation, already installed, maintained by community

## Complexity Tracking

No constitution violations to justify. All design decisions align with the six core principles.

## Post-Design Constitution Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Local-First | ✅ PASS | Vault at configurable `VAULT_PATH`. Cloud syncs markdown only. |
| II. Perception → Reasoning → Action | ✅ PASS | Three-layer: watchers → Claude → MCP servers. Clear boundaries. |
| III. HITL | ✅ PASS | Approval workflow in orchestrator. 24h expiry. All payments/new contacts require approval. |
| IV. Agent Skills | ✅ PASS | Skills in `.claude/skills/` and `src/skills/`. |
| V. Security | ✅ PASS | `.env` for secrets, DRY_RUN default true, rate limiting in core/rate_limiter.py. |
| VI. Graceful Degradation | ✅ PASS | retry.py for backoff, PM2 for restarts, queue-on-failure. |

**Final Gate: PASS**
