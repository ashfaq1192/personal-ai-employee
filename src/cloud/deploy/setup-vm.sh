#!/usr/bin/env bash
# GCP VM Provisioning Script for AI Employee (Platinum Tier)
# Creates an e2-standard-2 VM with all dependencies.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - GCP project set: gcloud config set project YOUR_PROJECT_ID
#
# Usage: bash src/cloud/deploy/setup-vm.sh [--project PROJECT_ID] [--zone ZONE]

set -euo pipefail

PROJECT="${1:-$(gcloud config get-value project 2>/dev/null)}"
ZONE="${2:-us-central1-a}"
VM_NAME="ai-employee-vm"
MACHINE_TYPE="e2-standard-2"
BOOT_DISK_SIZE="50GB"
IMAGE_FAMILY="ubuntu-2404-lts-amd64"
IMAGE_PROJECT="ubuntu-os-cloud"

echo "=== AI Employee GCP VM Setup ==="
echo "Project: $PROJECT"
echo "Zone:    $ZONE"
echo "VM:      $VM_NAME ($MACHINE_TYPE)"
echo ""

# Reserve static IP
echo "[1/5] Reserving static IP..."
gcloud compute addresses create ai-employee-ip \
    --project="$PROJECT" \
    --region="${ZONE%-*}" \
    2>/dev/null || echo "  Static IP already exists"

STATIC_IP=$(gcloud compute addresses describe ai-employee-ip \
    --project="$PROJECT" \
    --region="${ZONE%-*}" \
    --format="get(address)")
echo "  Static IP: $STATIC_IP"

# Create firewall rules
echo "[2/5] Creating firewall rules..."
gcloud compute firewall-rules create ai-employee-allow-https \
    --project="$PROJECT" \
    --allow=tcp:443 \
    --target-tags=ai-employee \
    --description="Allow HTTPS for Odoo" \
    2>/dev/null || echo "  HTTPS firewall rule already exists"

gcloud compute firewall-rules create ai-employee-allow-ssh \
    --project="$PROJECT" \
    --allow=tcp:22 \
    --target-tags=ai-employee \
    --description="Allow SSH" \
    2>/dev/null || echo "  SSH firewall rule already exists"

# Create VM
echo "[3/5] Creating VM instance..."
gcloud compute instances create "$VM_NAME" \
    --project="$PROJECT" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --boot-disk-size="$BOOT_DISK_SIZE" \
    --boot-disk-type=pd-ssd \
    --image-family="$IMAGE_FAMILY" \
    --image-project="$IMAGE_PROJECT" \
    --address="$STATIC_IP" \
    --tags=ai-employee \
    --metadata=startup-script='#!/bin/bash
echo "AI Employee VM startup at $(date)" >> /var/log/ai-employee-startup.log
' \
    2>/dev/null || echo "  VM already exists"

# Install dependencies via SSH
echo "[4/5] Installing dependencies on VM..."
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT" --command="
set -euo pipefail

echo '--- Updating system ---'
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential \
    curl \
    git \
    nginx \
    certbot \
    python3-certbot-nginx \
    libpq-dev \
    postgresql \
    postgresql-client \
    wget \
    unzip

echo '--- Installing Python 3.13 via deadsnakes PPA ---'
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update -qq
sudo apt-get install -y -qq python3.13 python3.13-venv python3.13-dev

echo '--- Installing UV ---'
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH=\"\$HOME/.local/bin:\$PATH\"

echo '--- Installing Node.js 24 + PM2 ---'
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt-get install -y -qq nodejs
sudo npm install -g pm2

echo '--- Installing Playwright dependencies ---'
sudo npx playwright install-deps chromium

echo '--- Verifying installations ---'
python3.13 --version
uv --version
node --version
pm2 --version
nginx -v
psql --version

echo '--- Setup complete ---'
"

echo "[5/5] VM provisioning complete!"
echo ""
echo "Next steps:"
echo "  1. Run install-odoo.sh to install Odoo"
echo "  2. Run nginx.conf setup for HTTPS"
echo "  3. Clone the repo and configure .env"
echo "  4. Start the cloud agent with PM2"
echo ""
echo "SSH: gcloud compute ssh $VM_NAME --zone=$ZONE"
echo "IP:  $STATIC_IP"
