# Personal AI Employee (Digital FTE)

**Platinum Tier Implementation — COMPLETE**

An autonomous, local-first AI assistant that handles email, social media, invoicing, and scheduling — powered by Claude Code with Obsidian as the knowledge base.

> **Status:** All 89 tests passing | All 4 tiers implemented | Production-ready

## Prerequisites

| Dependency | Version | Install |
|------------|---------|---------|
| Claude Code | latest | [claude.ai/code](https://claude.ai/code) |
| Python | ≥ 3.13 | [python.org](https://python.org) |
| Node.js | ≥ 20 | [nodejs.org](https://nodejs.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Obsidian | latest | [obsidian.md](https://obsidian.md) *(optional — vault works without GUI)* |

---

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd hackathon-0
uv sync

# 2. Run health check (verify all dependencies)
./doctor

# 3. Configure credentials
cp .env.example .env
# Edit .env with your API keys (see docs/setup-gmail.md for Gmail OAuth)

# 4. Initialize the Obsidian vault
uv run python main.py --init-vault

# 5. Start in development mode (dry-run, no real API calls)
uv run python main.py

# 6. Or start all services in production with PM2
pm2 start ecosystem.config.js
pm2 save
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PERSONAL AI EMPLOYEE                         │
├─────────────────────────────────────────────────────────────────┤
│  Perception (Watchers) → Reasoning (Claude) → Action (MCP)     │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Gmail        │     │ Claude Code  │     │ Email MCP    │
│ WhatsApp     │────▶│ + Ralph Loop │────▶│ Social MCP   │
│ File Drop    │     │              │     │ Odoo MCP     │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────▼───────┐
                     │ Obsidian     │
                     │ Vault        │
                     └──────────────┘
```

---

## CLI Reference

```bash
python main.py                  # Start orchestrator (default)
python main.py --init-vault     # Create vault folders and templates
python main.py --status         # Show vault and agent status
python main.py --dashboard      # Start web dashboard (port 8080)
python main.py --demo           # Run end-to-end demo scenario
python main.py --help           # Show all commands
```

---

## Hackathon Tier Checklist

| Tier | Status | Key Features |
|------|--------|--------------|
| **Bronze** | Complete | Vault init, Gmail watcher, file watcher, Dashboard.md, audit logs |
| **Silver** | Complete | WhatsApp watcher, HITL approval flow, Email MCP, Social MCP |
| **Gold** | Complete | Odoo ERP integration, all social platforms, CEO briefing, Ralph loop |
| **Platinum** | Complete | GCP cloud agent, vault sync, 24/7 monitoring, full test suite |

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Email Management** | Gmail monitoring, AI-drafted replies with human approval |
| **Social Media** | Scheduled posts to LinkedIn, Facebook, Instagram, Twitter/X |
| **Invoicing** | Odoo ERP integration for draft invoices and financial tracking |
| **CEO Briefing** | Weekly auto-generated briefing with revenue, tasks, suggestions |
| **Human-in-the-Loop** | Every sensitive action requires approval via file move |
| **Cloud Agent** | 24/7 GCP VM for always-on monitoring (draft-only mode) |
| **Full Audit Trail** | Every action logged as structured JSON to `/Logs/` |

---

## Test Coverage

```bash
# Run all tests
uv run pytest tests/ -v

# 89 tests covering:
# - Core utilities (config, logger, rate limiter, retry)
# - Orchestrator (approval, claim, dashboard)
# - Watchers (Gmail, filesystem)
# - Integration tests
```

---

## Safety Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `DEV_MODE=true` | No external API calls | Development/testing |
| `DRY_RUN=true` | API reads OK, writes logged | Staging/validation |
| Production | Full execution | Live deployment |

---

## Documentation

- **[docs/setup-gmail.md](docs/setup-gmail.md)** — Gmail OAuth setup guide
- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** — Complete tier-by-tier status
- **[hackathon-0.md](hackathon-0.md)** — Original hackathon requirements
- **[src/cloud/deploy/README.md](src/cloud/deploy/README.md)** — Cloud deployment guide

---

## Demo Video

*[Demo video link — TBD]*

---

## Security

- No hardcoded secrets — all credentials via `.env`
- `.env` excluded from version control
- Vault sync excludes sensitive files (`.gitignore`)
- Cloud agent is draft-only — never sends without local approval
- Rate limits enforced: emails (10/hr), social (5/hr), payments (3/hr)

---

## License

Proprietary — Hackathon submission.

---

*Built for Personal AI Employee Hackathon 0: Building Autonomous FTEs (2026)*
