#!/bin/bash
# Production Infrastructure Setup Script
# Run this script to set up persistent directories and move binaries to production locations

set -e

# Configuration
PROD_USER="ragkb"
PROD_GROUP="ragkb"
QDRANT_VERSION="1.12.1"
QDRANT_BIN_URL="https://github.com/qdrant/qdrant/releases/download/v${QDRANT_VERSION}/qdrant-x86_64-unknown-linux-musl.tar.gz"

echo "========================================"
echo "RAG Knowledge Base - Production Setup"
echo "========================================"

# =============================================================================
# 1. Create Production User
# =============================================================================
if ! id "$PROD_USER" &>/dev/null; then
    echo "Creating production user: $PROD_USER"
    sudo useradd -r -s /bin/false "$PROD_USER"
else
    echo "User $PROD_USER already exists"
fi

# =============================================================================
# 2. Create Persistent Directories
# =============================================================================
echo "Creating persistent directories..."

# Qdrant data (must survive reboots)
sudo mkdir -p /var/lib/qdrant
sudo chown -R "$PROD_USER:$PROD_GROUP" /var/lib/qdrant
sudo chmod 750 /var/lib/qdrant

# Application storage
sudo mkdir -p /var/lib/ragkb/storage
sudo chown -R "$PROD_USER:$PROD_GROUP" /var/lib/ragkb/storage
sudo chmod 750 /var/lib/ragkb/storage

# Log directory
sudo mkdir -p /var/log/ragkb
sudo chown -R "$PROD_USER:$PROD_GROUP" /var/log/ragkb
sudo chmod 750 /var/log/ragkb

# Model cache
sudo mkdir -p /var/cache/ragkb/models
sudo chown -R "$PROD_USER:$PROD_GROUP" /var/cache/ragkb/models
sudo chmod 755 /var/cache/ragkb/models

# =============================================================================
# 3. Download and Install Qdrant
# =============================================================================
QDRANT_INSTALL_DIR="/usr/local/bin"
if [ ! -f "$QDRANT_INSTALL_DIR/qdrant" ]; then
    echo "Downloading Qdrant v${QDRANT_VERSION}..."

    TMPDIR=$(mktemp -d)
    cd "$TMPDIR"

    curl -L -o qdrant.tar.gz "$QDRANT_BIN_URL"
    tar xzf qdrant.tar.gz

    sudo mv qdrant "$QDRANT_INSTALL_DIR/"
    sudo chmod +x "$QDRANT_INSTALL_DIR/qdrant"
    sudo chown root:root "$QDRANT_INSTALL_DIR/qdrant"

    cd -
    rm -rf "$TMPDIR"

    echo "Qdrant installed to $QDRANT_INSTALL_DIR/qdrant"
else
    echo "Qdrant already installed at $QDRANT_INSTALL_DIR/qdrant"
fi

# =============================================================================
# 4. Create Qdrant Config
# =============================================================================
if [ ! -f "/etc/qdrant/config.yaml" ]; then
    echo "Creating Qdrant configuration..."

    sudo mkdir -p /etc/qdrant
    sudo tee /etc/qdrant/config.yaml > /dev/null << 'EOF'
storage:
  storage_path: /var/lib/qdrant
  snapshots_path: /var/lib/qdrant/snapshots
  snapshots_config:
    snapshots_enabled: true

service:
  host: 127.0.0.1
  http_port: 6333
  grpc_port: 6334

cluster:
  enabled: false
EOF

    sudo chown -R "$PROD_USER:$PROD_GROUP" /etc/qdrant
    sudo chmod 750 /etc/qdrant
fi

# =============================================================================
# 5. Setup Log Rotation
# =============================================================================
echo "Setting up log rotation..."

sudo tee /etc/logrotate.d/ragkb > /dev/null << 'EOF'
/var/log/ragkb/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 ragkb ragkb
    sharedscripts
    postrotate
        /bin/kill -HUP $(cat /var/run/ragkb.pid 2>/dev/null) 2>/dev/null || true
    endscript
}
EOF

# =============================================================================
# 6. Summary
# =============================================================================
echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Directories created:"
echo "  /var/lib/qdrant          - Qdrant data (persistent)"
echo "  /var/lib/ragkb/storage   - Upload storage"
echo "  /var/log/ragkb           - Application logs"
echo "  /var/cache/ragkb/models  - Model cache"
echo ""
echo "Qdrant installed:"
echo "  /usr/local/bin/qdrant"
echo ""
echo "Configuration:"
echo "  /etc/qdrant/config.yaml"
echo ""
echo "Next steps:"
echo "  1. Copy deploy/config/.env.production to /opt/ragkb/.env"
echo "  2. Update API_KEY and other secrets"
echo "  3. Install systemd services: sudo cp deploy/systemd/*.service /etc/systemd/system/"
echo "  4. Start services: sudo systemctl start ragkb-api ragkb-worker"
echo ""
