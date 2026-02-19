# Quickstart: Personal AI Employee

## Prerequisites

- Python 3.13+ installed
- UV package manager installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node.js 24+ LTS installed
- Claude Code installed and authenticated (`npm install -g @anthropic/claude-code`)
- Obsidian installed (v1.10.6+)
- Git installed
- Gmail API OAuth2 credentials (see Setup section)

## 1. Clone & Initialize

```bash
# Clone the project
git clone <repo-url> ai-employee
cd ai-employee

# Initialize UV Python project
uv init --python 3.13
uv sync

# Install Node.js dependencies (MCP servers)
npm install
```

## 2. Create the Vault

```bash
# Set vault path (add to your shell profile)
export VAULT_PATH="$HOME/AI_Employee_Vault"

# Initialize vault structure
uv run python src/cli/init_vault.py --path "$VAULT_PATH"

# Open in Obsidian
# → Open Obsidian → "Open folder as vault" → select ~/AI_Employee_Vault
```

## 3. Configure Credentials

```bash
# Copy the example .env file
cp .env.example .env

# Edit .env with your credentials
# NEVER commit this file!
```

Required `.env` variables:
```bash
# Vault
VAULT_PATH=~/AI_Employee_Vault

# Mode (set to false for production)
DEV_MODE=true
DRY_RUN=true

# Gmail API
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
GMAIL_CREDENTIALS_PATH=~/.config/ai-employee/gmail_credentials.json

# WhatsApp (Playwright session)
WHATSAPP_SESSION_PATH=~/.config/ai-employee/whatsapp-session

# Social Media (set up as you get API access)
LINKEDIN_ACCESS_TOKEN=
META_ACCESS_TOKEN=
TWITTER_BEARER_TOKEN=
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_SECRET=

# Odoo (set up when deploying Gold tier)
ODOO_URL=
ODOO_DB=
ODOO_USERNAME=
ODOO_PASSWORD=
```

## 4. Set Up Gmail OAuth2

```bash
# 1. Go to Google Cloud Console → APIs & Services → Credentials
# 2. Create OAuth 2.0 Client ID (Desktop app)
# 3. Download credentials.json
# 4. Run the auth flow:
uv run python src/cli/gmail_auth.py --credentials credentials.json

# This opens a browser for consent, then saves tokens to GMAIL_CREDENTIALS_PATH
```

## 5. Start the System (Bronze Tier)

```bash
# Start with DEV_MODE=true for safety
DEV_MODE=true uv run python src/orchestrator.py

# Or start individual components:
uv run python src/watchers/gmail_watcher.py &
uv run python src/watchers/filesystem_watcher.py &
```

## 6. Verify It Works

```bash
# Drop a test file
echo "Test file for AI Employee" > "$VAULT_PATH/../drop_folder/test.txt"

# Check Needs_Action
ls "$VAULT_PATH/Needs_Action/"
# Should show: FILE_test.txt and FILE_test.txt.md

# Send yourself an important email, wait 2 minutes
ls "$VAULT_PATH/Needs_Action/"
# Should show: EMAIL_<id>.md
```

## 7. Production Mode

```bash
# Install PM2 for process management
npm install -g pm2

# Start all services
pm2 start ecosystem.config.js

# Save for boot persistence
pm2 save
pm2 startup
```

## Tier Progression

| Step | Tier | What to Enable |
|------|------|---------------|
| 1 | Bronze | Vault + File Watcher + Claude read/write |
| 2 | Bronze | Gmail Watcher |
| 3 | Silver | WhatsApp Watcher + Email MCP |
| 4 | Silver | LinkedIn auto-posting + Scheduling |
| 5 | Gold | Odoo ERP + Social media (FB/IG/X) |
| 6 | Gold | CEO Briefing + Ralph Wiggum loop |
| 7 | Platinum | GCP deployment + Vault sync |
| 8 | Platinum | Cloud Odoo + Work-zone specialization |

## Useful Commands

```bash
# Check system status
uv run python src/cli/status.py

# Trigger Claude reasoning manually
claude --cwd "$VAULT_PATH" "Check /Needs_Action and process any pending items."

# Start a Ralph loop for multi-step processing
/ralph-loop "Process all items in /Needs_Action. Create plans, request approvals as needed. Move completed items to /Done. Output <promise>TASK_COMPLETE</promise> when Needs_Action is empty." --completion-promise "TASK_COMPLETE" --max-iterations 10

# Generate CEO briefing manually
claude --cwd "$VAULT_PATH" "Generate a CEO briefing for this week."

# View audit logs
uv run python src/cli/view_logs.py --date today
```
