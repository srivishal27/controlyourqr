#!/usr/bin/env bash
#
# Update a running deployment to the latest committed code.
#
#     sudo /opt/controlyourqr/deploy/scripts/deploy.sh [git-ref]
#
# Pulls from origin, reinstalls dependencies if they changed, reloads nginx and
# restarts the service. Refuses to leave a broken config behind.

set -euo pipefail

APP_NAME="controlyourqr"
APP_USER="controlyourqr"
APP_DIR="/opt/${APP_NAME}"
CHECKOUT="${CHECKOUT_DIR:-/srv/${APP_NAME}.git-checkout}"
REF="${1:-main}"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must run as root (use sudo)." >&2
  exit 1
fi

if [[ ! -d "${CHECKOUT}/.git" ]]; then
  echo "No git checkout at ${CHECKOUT}." >&2
  echo "Clone the repository there first, or re-run bootstrap.sh from a checkout." >&2
  exit 1
fi

log "Fetching ${REF}"
git -C "${CHECKOUT}" fetch --prune origin
git -C "${CHECKOUT}" checkout -q "${REF}"
git -C "${CHECKOUT}" reset --hard -q "origin/${REF}"
echo "    now at $(git -C "${CHECKOUT}" rev-parse --short HEAD) — $(git -C "${CHECKOUT}" log -1 --format=%s)"

log "Syncing code"
rsync -a --delete \
  --exclude '.git/' --exclude '.venv/' --exclude '__pycache__/' \
  --exclude '.pytest_cache/' --exclude 'tests/' \
  "${CHECKOUT}/" "${APP_DIR}/"

log "Updating dependencies"
"${APP_DIR}/.venv/bin/pip" install --quiet -r "${APP_DIR}/requirements.txt"

chown -R root:"${APP_USER}" "${APP_DIR}"
find "${APP_DIR}" -type d -exec chmod 750 {} +
chmod o+x /opt "${APP_DIR}" "${APP_DIR}/app"
chmod -R o+rX "${APP_DIR}/app/static"

log "Reloading services"
install -m 0644 "${APP_DIR}/deploy/systemd/${APP_NAME}.service" \
  "/etc/systemd/system/${APP_NAME}.service"
install -m 0644 "${APP_DIR}/deploy/nginx/${APP_NAME}.conf" \
  "/etc/nginx/sites-available/${APP_NAME}.conf"

nginx -t
systemctl daemon-reload
systemctl restart "${APP_NAME}.service"
systemctl reload nginx

log "Verifying"
sleep 2
if curl -fsS http://127.0.0.1/healthz >/dev/null; then
  echo "    deploy OK — $(git -C "${CHECKOUT}" rev-parse --short HEAD)"
else
  echo "    health check FAILED; inspect: journalctl -u ${APP_NAME} -n 50" >&2
  exit 1
fi
