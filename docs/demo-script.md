# AI Employee Demo Script

**Duration**: 5-10 minutes
**Tier**: Platinum (all features)

---

## 1. Introduction (30s)

> "This is the Personal AI Employee — an autonomous, local-first AI assistant that handles email, social media, invoicing, and scheduling. It runs on your machine with Claude Code, uses Obsidian as a knowledge base, and keeps a human in the loop for every important action."

---

## 2. Vault Setup (1 min)

```bash
# Initialize the vault
uv run python src/cli/init_vault.py --vault-path ~/AI_Employee_Vault

# Show structure in Obsidian
# Point out: Dashboard, Company_Handbook, Business_Goals
```

> "The vault is the single source of truth — every action, approval, and log lives here as plain Markdown."

---

## 3. Watcher Demo: File Drop (1 min)

```bash
# Start the orchestrator
pm2 start ecosystem.config.js

# Drop a file into the Inbox
cp sample_invoice.pdf ~/AI_Employee_Vault/Inbox/

# Show the action item appear in Needs_Action
ls ~/AI_Employee_Vault/Needs_Action/
```

> "The file watcher detected the new file, created an action item, and Claude is already analyzing it."

---

## 4. Email Processing (1.5 min)

```bash
# Show Gmail watcher logs
pm2 logs orchestrator --lines 20

# Show the email action item in Needs_Action
cat ~/AI_Employee_Vault/Needs_Action/EMAIL_*.md

# Show Claude's draft reply in Pending_Approval
cat ~/AI_Employee_Vault/Pending_Approval/APPROVAL_*.md
```

> "Gmail detected a new email from a known contact, Claude drafted a reply, and it's waiting for human approval."

---

## 5. HITL Approval Flow (1.5 min)

```bash
# Review the approval request
cat ~/AI_Employee_Vault/Pending_Approval/APPROVAL_email_reply.md

# Approve by moving to Approved
mv ~/AI_Employee_Vault/Pending_Approval/APPROVAL_email_reply.md ~/AI_Employee_Vault/Approved/

# Watch the action execute
pm2 logs orchestrator --lines 10

# Show the result in Done
ls ~/AI_Employee_Vault/Done/
```

> "One drag-and-drop in Obsidian and the email is sent. The approval watcher detected the move and triggered the MCP server."

---

## 6. Social Media Scheduling (1 min)

```bash
# Show the social scheduler skill
cat .claude/skills/social-scheduler.md

# Trigger a scheduled post (DRY_RUN)
# Show the draft in the logs
pm2 logs orchestrator | grep "social_post"
```

> "Social posts are scheduled via cron. Scheduled posts are auto-approved per the Company Handbook — ad-hoc posts always require human approval."

---

## 7. CEO Briefing (1.5 min)

```bash
# Generate sample data
uv run python tests/fixtures/generate_sample_week.py

# Trigger the briefing
uv run python src/cli/trigger_reasoning.py --skill generate-briefing

# Show the briefing
cat ~/AI_Employee_Vault/Briefings/*Monday_Briefing.md
```

> "Every Sunday night, Claude generates a comprehensive weekly briefing: revenue tracking, completed tasks, bottlenecks, and proactive suggestions — all from real vault data."

---

## 8. Cloud Agent (Platinum) (1 min)

```bash
# Show cloud agent architecture
cat src/cloud/deploy/README.md

# Show vault sync
cat src/cloud/sync/vault_sync.sh

# Demonstrate claim-by-move
ls ~/AI_Employee_Vault/In_Progress/
```

> "On the cloud VM, a stripped-down agent monitors Gmail 24/7. It creates drafts and approval requests, but never sends — that's always the local human's decision."

---

## 9. Status Check (30s)

```bash
# System status
uv run python src/cli/status.py
```

> "One command shows everything: process health, vault state, recent errors, and cloud VM status."

---

## 10. Wrap-Up (30s)

> "The AI Employee is local-first, privacy-respecting, and always keeps a human in the loop. It uses plain Markdown files for everything — no vendor lock-in, full auditability, and it works with any Obsidian vault."

---

## Key Talking Points

- **Local-first**: All data stays on your machine
- **Human-in-the-loop**: File-based approval via Obsidian drag-and-drop
- **Multi-channel**: Email, WhatsApp, LinkedIn, Facebook, Instagram, Twitter/X
- **Financial integration**: Odoo ERP for invoicing and accounting
- **24/7 availability**: Cloud agent for always-on monitoring (Platinum)
- **Full audit trail**: Every action logged as JSON in the vault
