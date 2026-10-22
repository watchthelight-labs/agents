#!/bin/bash
set -euo pipefail
test "$(id -u)" = 0
BASE=/srv/memory-mcp
if ! id memory-mcp >/dev/null 2>&1; then
    useradd --system --home-dir "$BASE" --shell /usr/sbin/nologin memory-mcp
fi
install -d -m 755 "$BASE"
install -d -m 700 -o memory-mcp -g memory-mcp "$BASE/data"
install -d -m 2770 -o memory-mcp -g ubuntu "$BASE/inbox"
# Unpack into a clean tree and swap it in, so files removed upstream do not linger; keep one previous release.
rm -rf "$BASE/app.new"
install -d -m 755 "$BASE/app.new"
tar -xzf /home/ubuntu/memory-mcp-upload/app.tar.gz -C "$BASE/app.new" --no-same-owner
rm -rf "$BASE/app.prev"
if test -d "$BASE/app"; then mv "$BASE/app" "$BASE/app.prev"; fi
mv "$BASE/app.new" "$BASE/app"
python3 -m venv "$BASE/venv"
"$BASE/venv/bin/pip" install --disable-pip-version-check -q --require-hashes -r "$BASE/app/requirements.lock"
"$BASE/venv/bin/pip" install --disable-pip-version-check -q --no-deps --force-reinstall "$BASE/app"
# Never replace a live environment file: it holds the vault key. Update it by hand when variables change.
if ! test -e /etc/memory-mcp.env; then
    install -m 600 /home/ubuntu/memory-mcp-upload/memory-mcp.env /etc/memory-mcp.env
fi
install -m 644 "$BASE/app/ops/memory-mcp.service" /etc/systemd/system/
install -m 644 "$BASE/app/ops/memory-mcp-import.service" /etc/systemd/system/
install -m 644 "$BASE/app/ops/memory-mcp-import.timer" /etc/systemd/system/
install -m 644 "$BASE/app/ops/memory-mcp-backup.service" /etc/systemd/system/
install -m 644 "$BASE/app/ops/memory-mcp-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable memory-mcp.service memory-mcp-import.timer memory-mcp-backup.timer
systemctl restart memory-mcp.service
curl -fsS --retry 10 --retry-connrefused --retry-delay 1 http://127.0.0.1:8091/healthz
install -d -m 755 /var/lib/letsencrypt
# A new dedicated vhost; existing site configurations are not rewritten.
if ! test -e /etc/nginx/sites-available/mcp.example.org; then
    cat >/etc/nginx/sites-available/mcp.example.org <<'NGINX'
server {
    listen 80;
    server_name mcp.example.org;
    location /.well-known/acme-challenge/ { root /var/lib/letsencrypt; }
    location / { return 404; }
}
NGINX
    ln -s /etc/nginx/sites-available/mcp.example.org /etc/nginx/sites-enabled/mcp.example.org
    nginx -t
    systemctl reload nginx
fi
echo 'Application and ACME challenge host ready.'

# Dashboard: dash.example.org (API on 127.0.0.1:8092, SPA served by nginx from app/dash-ui/dist).
UP=/home/ubuntu/memory-mcp-upload
if test -e "$UP/memory-dash.env" && ! test -e /etc/memory-dash.env; then
    install -m 600 "$UP/memory-dash.env" /etc/memory-dash.env
fi
if test -d "$UP/dash-certs"; then
    install -d -m 750 /etc/ssl/memory-dash
    install -m 644 "$UP/dash-certs/origin.pem" "$UP/dash-certs/aop-ca.pem" /etc/ssl/memory-dash/
    install -m 600 "$UP/dash-certs/origin.key" /etc/ssl/memory-dash/
    rm -rf "$UP/dash-certs"
fi
if test -e /etc/memory-dash.env; then
    install -m 644 "$BASE/app/ops/memory-dash.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable memory-dash.service
    systemctl restart memory-dash.service
    if test -e /etc/ssl/memory-dash/origin.pem && test -e "$BASE/app/dash-ui/dist/index.html"; then
        install -m 644 "$BASE/app/ops/dash.example.org.conf" /etc/nginx/sites-available/dash.example.org
        ln -sfn /etc/nginx/sites-available/dash.example.org /etc/nginx/sites-enabled/dash.example.org
        if ! nginx -t; then
            rm -f /etc/nginx/sites-enabled/dash.example.org
            echo 'Dashboard vhost rejected by nginx -t; left disabled.' >&2
            exit 1
        fi
        systemctl reload nginx
        echo 'Dashboard ready.'
    fi
fi
