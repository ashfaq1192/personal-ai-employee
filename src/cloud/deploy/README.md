# Cloud Deployment Guide (Platinum Tier)

Deploy the AI Employee on a GCP Compute Engine VM for 24/7 operation.

## Prerequisites

- GCP account with billing enabled
- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- A domain name (for HTTPS/Odoo access)
- Local setup already working (vault initialized, watchers tested)

## Step-by-Step

### 1. Provision the VM

```bash
# Set your GCP project
gcloud config set project YOUR_PROJECT_ID

# Create VM, firewall rules, static IP
bash src/cloud/deploy/setup-vm.sh
```

This creates an `e2-standard-2` VM (2 vCPU, 8GB RAM, 50GB SSD) with:
- Python 3.13, UV, Node.js 24, PM2
- nginx, PostgreSQL, Playwright deps
- Git

### 2. Install Odoo

```bash
# SSH into the VM
gcloud compute ssh ai-employee-vm --zone=us-central1-a

# Run the installer
bash src/cloud/deploy/install-odoo.sh
```

### 3. Configure HTTPS (nginx + Let's Encrypt)

```bash
# Copy nginx config
sudo cp src/cloud/deploy/nginx.conf /etc/nginx/sites-available/odoo
sudo ln -s /etc/nginx/sites-available/odoo /etc/nginx/sites-enabled/

# Edit: replace YOUR_DOMAIN with your actual domain
sudo nano /etc/nginx/sites-available/odoo

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Test and reload
sudo nginx -t && sudo systemctl reload nginx
```

### 4. Initialize Vault Sync

```bash
# On the VM: clone vault repo
git clone git@github.com:YOUR_ORG/ai-employee-vault.git ~/AI_Employee_Vault

# Set up SSH keys for passwordless push/pull
ssh-keygen -t ed25519 -C "ai-employee-cloud"
# Add the public key to your GitHub repo as a deploy key

# Install sync cron
crontab -e
# Add: */2 * * * * /opt/ai-employee/src/cloud/sync/vault_sync.sh >> /var/log/vault-sync.log 2>&1
```

### 5. Configure Environment

```bash
# Copy and edit .env
cp .env.example .env
nano .env

# Key settings for cloud:
# VAULT_PATH=~/AI_Employee_Vault
# DEV_MODE=false
# DRY_RUN=false (when ready for production)
# GMAIL_* credentials
# ODOO_URL=http://localhost:8069
```

### 6. Start the Cloud Agent

```bash
# Install dependencies
uv sync

# Start with PM2
pm2 start ecosystem.config.js --only cloud-agent
pm2 save
pm2 startup  # Enable auto-start on boot
```

### 7. Set Up Odoo Backups

```bash
# Install backup cron
crontab -e
# Add: 0 2 * * * /opt/ai-employee/src/cloud/deploy/backup-odoo.sh >> /var/log/odoo-backup.log 2>&1
```

## Security Checklist

- [ ] `.env` file has restricted permissions (`chmod 600 .env`)
- [ ] SSH key authentication only (disable password auth)
- [ ] Firewall allows only ports 22, 443
- [ ] Odoo admin password changed from default
- [ ] Let's Encrypt certificate auto-renewal configured
- [ ] Vault `.gitignore` excludes secrets (`.env`, `*credentials*`, `*.key`)
- [ ] DRY_RUN=true until full testing complete
- [ ] Cloud agent is draft-only (never sends without local approval)

## Monitoring

```bash
# Check cloud agent logs
pm2 logs cloud-agent

# Check vault sync
tail -f /var/log/vault-sync.log

# Check Odoo
sudo systemctl status odoo
sudo journalctl -u odoo -f

# Check nginx
sudo tail -f /var/log/nginx/odoo-error.log
```

## Architecture

```
Local Machine                    GCP VM
├── Orchestrator (full)          ├── Cloud Agent (draft-only)
├── Gmail Watcher                ├── Gmail Watcher
├── WhatsApp Watcher             ├── (no WhatsApp)
├── File Watcher                 ├── Odoo (localhost:8069)
└── Vault ←── Git Sync ──────── └── Vault
```

The claim-by-move rule ensures no duplicate processing:
- First agent to move a file from `Needs_Action/` to `In_Progress/<agent>/` owns it.
- Cloud agent creates only drafts and approval requests.
- Local agent handles all actual sends after human approval.
