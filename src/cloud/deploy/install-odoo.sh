#!/usr/bin/env bash
# Install Odoo 19 Community Edition from source.
#
# Run this on the GCP VM after setup-vm.sh.
# Usage: bash src/cloud/deploy/install-odoo.sh

set -euo pipefail

ODOO_USER="odoo"
ODOO_HOME="/opt/odoo"
ODOO_CONF="/etc/odoo.conf"
ODOO_VERSION="19.0"

echo "=== Installing Odoo $ODOO_VERSION ==="

# Create system user
echo "[1/6] Creating Odoo system user..."
sudo useradd -r -m -d "$ODOO_HOME" -s /bin/bash "$ODOO_USER" 2>/dev/null || echo "  User already exists"

# Configure PostgreSQL
echo "[2/6] Configuring PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql
sudo -u postgres createuser --createdb --no-createrole --no-superuser "$ODOO_USER" 2>/dev/null || echo "  PostgreSQL user already exists"
sudo -u postgres createdb "$ODOO_USER" 2>/dev/null || echo "  Database already exists"

# Clone Odoo source
echo "[3/6] Cloning Odoo $ODOO_VERSION..."
if [ ! -d "$ODOO_HOME/odoo" ]; then
    sudo -u "$ODOO_USER" git clone --depth 1 --branch "$ODOO_VERSION" \
        https://github.com/odoo/odoo.git "$ODOO_HOME/odoo"
else
    echo "  Odoo source already cloned"
fi

# Install Python dependencies
echo "[4/6] Installing Python dependencies..."
sudo -u "$ODOO_USER" python3.13 -m venv "$ODOO_HOME/venv"
sudo -u "$ODOO_USER" "$ODOO_HOME/venv/bin/pip" install --quiet \
    -r "$ODOO_HOME/odoo/requirements.txt"

# Create config
echo "[5/6] Creating Odoo configuration..."
sudo tee "$ODOO_CONF" > /dev/null <<EOF
[options]
admin_passwd = $(openssl rand -base64 16)
db_host = localhost
db_port = 5432
db_user = $ODOO_USER
db_password = False
addons_path = $ODOO_HOME/odoo/addons
logfile = /var/log/odoo/odoo.log
http_port = 8069
proxy_mode = True
EOF

sudo mkdir -p /var/log/odoo
sudo chown "$ODOO_USER":"$ODOO_USER" /var/log/odoo

# Create systemd service
echo "[6/6] Creating systemd service..."
sudo tee /etc/systemd/system/odoo.service > /dev/null <<EOF
[Unit]
Description=Odoo $ODOO_VERSION
Documentation=https://www.odoo.com
After=postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=$ODOO_USER
Group=$ODOO_USER
ExecStart=$ODOO_HOME/venv/bin/python $ODOO_HOME/odoo/odoo-bin -c $ODOO_CONF
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable odoo
sudo systemctl start odoo

echo ""
echo "=== Odoo $ODOO_VERSION installed ==="
echo "Service status: sudo systemctl status odoo"
echo "Logs: sudo journalctl -u odoo -f"
echo "URL: http://localhost:8069"
echo ""
echo "IMPORTANT: Update $ODOO_CONF with a secure admin password"
echo "and configure the database via the web interface."
