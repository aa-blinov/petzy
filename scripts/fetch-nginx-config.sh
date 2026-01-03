#!/bin/bash
# Script to fetch nginx configuration from remote server
# Usage: ./scripts/fetch-nginx-config.sh [config-name]

# Load secrets from environment or use defaults
SERVER_HOST="${SERVER_PETZY_HOST:-your-server.com}"
SERVER_USER="${SERVER_PETZY_USER:-user}"
SSH_KEY="${SERVER_PETZY_SSH_KEY:-~/.ssh/id_rsa}"

CONFIG_NAME="${1:-default}"

echo "Fetching nginx configuration from ${SERVER_USER}@${SERVER_HOST}..."

# Create output directory
mkdir -p ./nginx-configs

# Fetch main nginx config
echo "Fetching main nginx.conf..."
scp -i "${SSH_KEY}" "${SERVER_USER}@${SERVER_HOST}:/etc/nginx/nginx.conf" ./nginx-configs/nginx.conf 2>/dev/null || echo "Could not fetch main config"

# List available configs
echo "Available site configs:"
ssh -i "${SSH_KEY}" "${SERVER_USER}@${SERVER_HOST}" "ls -1 /etc/nginx/sites-available/ 2>/dev/null || ls -1 /etc/nginx/conf.d/*.conf 2>/dev/null"

# Fetch specific config if provided
if [ "$CONFIG_NAME" != "default" ]; then
    echo "Fetching ${CONFIG_NAME}..."
    # Try sites-available first
    scp -i "${SSH_KEY}" "${SERVER_USER}@${SERVER_HOST}:/etc/nginx/sites-available/${CONFIG_NAME}" "./nginx-configs/${CONFIG_NAME}" 2>/dev/null || \
    # Try conf.d
    scp -i "${SSH_KEY}" "${SERVER_USER}@${SERVER_HOST}:/etc/nginx/conf.d/${CONFIG_NAME}.conf" "./nginx-configs/${CONFIG_NAME}.conf" 2>/dev/null || \
    echo "Config ${CONFIG_NAME} not found"
fi

# Search for configs containing cat-health-control or petzy
echo "Searching for configs related to cat-health-control..."
ssh -i "${SSH_KEY}" "${SERVER_USER}@${SERVER_HOST}" "grep -rl 'cat-health-control\|petzy' /etc/nginx/ 2>/dev/null" | while read config_path; do
    config_name=$(basename "$config_path")
    echo "Found: $config_path"
    scp -i "${SSH_KEY}" "${SERVER_USER}@${SERVER_HOST}:${config_path}" "./nginx-configs/${config_name}" 2>/dev/null
done

echo "Configs saved to ./nginx-configs/"

