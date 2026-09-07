#!/usr/bin/env bash
#
# Provision a fresh Debian/Ubuntu host to serve ControlYourQR.
#
# Idempotent: safe to re-run. Run as root, from a checkout of this repository:
#
#     sudo ./deploy/scripts/bootstrap.sh
#
# Afterwards, enable TLS once DNS points at this machine:
#
#     sudo certbot --nginx -d controlyourqr.com -d www.controlyourqr.com

set -euo pipefail

APP_NAME="controlyourqr"
APP_USER="controlyourqr"
APP_DIR="/opt/${APP_NAME}"
DOMAIN="${DOMAIN:-controlyourqr.com}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must run as root (use sudo)." >&2
  exit 1
fi

# --------------------------------------------------------------------------- #
log "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  python3 python3-venv python3-pip \
  nginx rsync ca-certificates \
  certbot python3-certbot-nginx \
  ufw unattended-upgrades

# --------------------------------------------------------------------------- #
log "Creating the service account"
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --home-dir "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
fi

# --------------------------------------------------------------------------- #
log "Syncing application code to ${APP_DIR}"
mkdir -p "${APP_DIR}"
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude 'tests/' \
  "${SRC_DIR}/" "${APP_DIR}/"

# --------------------------------------------------------------------------- #
log "Building the Python environment"
if [[ ! -x "${APP_DIR}/.venv/bin/python" ]]; then
  python3 -m venv "${APP_DIR}/.venv"
fi
"${APP_DIR}/.venv/bin/pip" install --quiet --upgrade pip
"${APP_DIR}/.venv/bin/pip" install --quiet -r "${APP_DIR}/requirements.txt"

# The service must not be able to modify its own code.
chown -R root:"${APP_USER}" "${APP_DIR}"
chmod -R g+rX,o-rwx "${APP_DIR}"
find "${APP_DIR}" -type d -exec chmod 750 {} +

# --------------------------------------------------------------------------- #
log "Installing the systemd unit"
mkdir -p /etc/${APP_NAME}
touch /etc/${APP_NAME}/app.env
chmod 640 /etc/${APP_NAME}/app.env
chown root:"${APP_USER}" /etc/${APP_NAME}/app.env

install -m 0644 "${APP_DIR}/deploy/systemd/${APP_NAME}.service" \
  "/etc/systemd/system/${APP_NAME}.service"
systemctl daemon-reload
systemctl enable --now "${APP_NAME}.service"
systemctl restart "${APP_NAME}.service"

# --------------------------------------------------------------------------- #
log "Configuring nginx"
mkdir -p /etc/nginx/snippets /var/www/html/.well-known/acme-challenge
install -m 0644 "${APP_DIR}/deploy/nginx/snippets/${APP_NAME}.common.conf" \
  "/etc/nginx/snippets/${APP_NAME}.common.conf"

# Pick the site file that matches reality. Certificates are obtained with
# `certbot certonly`, so certbot never edits these files and re-running this
# script cannot clobber a working TLS configuration.
if [[ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
  VARIANT="tls"
else
  VARIANT="http"
  echo "    no certificate for ${DOMAIN} yet — serving plain HTTP"
fi
echo "    using the ${VARIANT} site configuration"

install -m 0644 "${APP_DIR}/deploy/nginx/${APP_NAME}.${VARIANT}.conf" \
  "/etc/nginx/sites-available/${APP_NAME}.conf"
ln -sfn "/etc/nginx/sites-available/${APP_NAME}.conf" \
  "/etc/nginx/sites-enabled/${APP_NAME}.conf"
rm -f /etc/nginx/sites-enabled/default

# nginx needs traversal into the static directory.
chmod o+x /opt "${APP_DIR}" "${APP_DIR}/app"
chmod -R o+rX "${APP_DIR}/app/static"

nginx -t
systemctl enable nginx
systemctl reload nginx

# --------------------------------------------------------------------------- #
log "Configuring the firewall"
ufw allow OpenSSH >/dev/null
ufw allow 'Nginx Full' >/dev/null
ufw --force enable >/dev/null

log "Enabling unattended security updates"
dpkg-reconfigure -f noninteractive unattended-upgrades >/dev/null 2>&1 || true

# --------------------------------------------------------------------------- #
log "Verifying"
sleep 2
systemctl --no-pager --lines=0 status "${APP_NAME}.service" || true
curl -fsS http://127.0.0.1/healthz && echo "  health check OK"

cat <<SUMMARY

$(printf '\033[1;32m==> ControlYourQR is live over HTTP.\033[0m')

Next steps:
  1. Point the DNS A record for controlyourqr.com at this machine's external IP.
  2. Once it resolves, enable HTTPS:
       sudo ${APP_DIR}/deploy/scripts/enable-tls.sh

     HSTS needs no further action: the app emits it only on requests that
     actually arrived over TLS, so it switches itself on with the certificate.

Useful commands:
  systemctl status ${APP_NAME}
  journalctl -u ${APP_NAME} -f
  sudo ${APP_DIR}/deploy/scripts/deploy.sh     # pull + restart
SUMMARY
