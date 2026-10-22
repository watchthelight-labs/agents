#!/bin/bash
set -euo pipefail
test "$(id -u)" = 0
certbot certonly --webroot -w /var/lib/letsencrypt -d mcp.example.org --non-interactive --agree-tos --keep-until-expiring
cp -a /etc/nginx/sites-available/mcp.example.org /etc/nginx/sites-available/mcp.example.org.pre-tls
install -m 644 /srv/memory-mcp/app/ops/mcp.example.org.conf /etc/nginx/sites-available/mcp.example.org
if ! nginx -t; then
    cp -a /etc/nginx/sites-available/mcp.example.org.pre-tls /etc/nginx/sites-available/mcp.example.org
    exit 1
fi
systemctl reload nginx
install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
printf '%s\n' '#!/bin/sh' 'nginx -t && systemctl reload nginx' >/etc/letsencrypt/renewal-hooks/deploy/memory-mcp-nginx
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/memory-mcp-nginx
systemctl enable --now certbot.timer
echo 'HTTPS enabled.'
