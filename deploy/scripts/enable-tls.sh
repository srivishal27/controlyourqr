#!/usr/bin/env bash
#
# Obtain a Let's Encrypt certificate and switch nginx to the TLS site file.
#
#     sudo ./deploy/scripts/enable-tls.sh
#
# Uses `certbot certonly --webroot` rather than `--nginx` on purpose: certbot
# then never edits the nginx configuration, so the files in this repository
# stay the single source of truth and a later bootstrap/deploy cannot wipe out
# a working TLS setup.
#
# Override with the environment if needed:
#     DOMAIN=example.com ALT_NAMES="www.example.com" CERTBOT_EMAIL=me@example.com

set -euo pipefail

APP_NAME="controlyourqr"
APP_DIR="/opt/${APP_NAME}"
DOMAIN="${DOMAIN:-controlyourqr.com}"
ALT_NAMES="${ALT_NAMES:-www.controlyourqr.com}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-srivishal66@gmail.com}"
WEBROOT="/var/www/html"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must run as root (use sudo)." >&2
  exit 1
fi

# --------------------------------------------------------------------------- #
log "Checking that the ACME challenge path is reachable"
mkdir -p "${WEBROOT}/.well-known/acme-challenge"
PROBE="cyqr-probe-$$"
echo "${PROBE}" > "${WEBROOT}/.well-known/acme-challenge/${PROBE}"
trap 'rm -f "${WEBROOT}/.well-known/acme-challenge/${PROBE}"' EXIT

DOMAIN_ARGS=(-d "${DOMAIN}")
REACHABLE=1
for name in "${DOMAIN}" ${ALT_NAMES}; do
  url="http://${name}/.well-known/acme-challenge/${PROBE}"
  if [[ "$(curl -fsS --max-time 15 "${url}" 2>/dev/null || true)" == "${PROBE}" ]]; then
    printf '    %-28s reachable\n' "${name}"
    [[ "${name}" != "${DOMAIN}" ]] && DOMAIN_ARGS+=(-d "${name}")
  else
    printf '    %-28s NOT reachable — it will be left out of the certificate\n' "${name}"
    [[ "${name}" == "${DOMAIN}" ]] && REACHABLE=0
  fi
done

if [[ "${REACHABLE}" -eq 0 ]]; then
  cat >&2 <<MSG

The primary domain ${DOMAIN} could not serve the ACME challenge, so Let's
Encrypt will not be able to validate it either. Common causes:

  * DNS does not point at this machine yet (check: dig +short A ${DOMAIN})
  * A CDN or proxy in front is redirecting HTTP to HTTPS before the request
    reaches this server. Disable that redirect, or set the DNS record to
    DNS-only, until the certificate has been issued.
  * Port 80 is blocked by a cloud firewall rule.

MSG
  exit 1
fi

# --------------------------------------------------------------------------- #
log "Requesting the certificate"
certbot certonly \
  --webroot -w "${WEBROOT}" \
  "${DOMAIN_ARGS[@]}" \
  --agree-tos \
  --email "${CERTBOT_EMAIL}" \
  --non-interactive \
  --keep-until-expiring \
  --deploy-hook "systemctl reload nginx"

# --------------------------------------------------------------------------- #
log "Switching nginx to the TLS configuration"
install -m 0644 "${APP_DIR}/deploy/nginx/snippets/${APP_NAME}.common.conf" \
  "/etc/nginx/snippets/${APP_NAME}.common.conf"
install -m 0644 "${APP_DIR}/deploy/nginx/snippets/cloudflare-real-ip.conf" \
  "/etc/nginx/snippets/cloudflare-real-ip.conf"
install -m 0644 "${APP_DIR}/deploy/nginx/${APP_NAME}.tls.conf" \
  "/etc/nginx/sites-available/${APP_NAME}.conf"
ln -sfn "/etc/nginx/sites-available/${APP_NAME}.conf" \
  "/etc/nginx/sites-enabled/${APP_NAME}.conf"

nginx -t
systemctl reload nginx

# --------------------------------------------------------------------------- #
log "Verifying"
sleep 2
if curl -fsS --max-time 15 "https://${DOMAIN}/healthz" >/dev/null; then
  echo "    HTTPS is serving"
else
  echo "    HTTPS check failed — inspect: nginx -t; journalctl -u nginx -n 40" >&2
  exit 1
fi

certbot certificates 2>/dev/null | sed -n '/Certificate Name/,/Expiry/p' | head -12

log "Renewal"
systemctl list-timers 'certbot*' --no-pager 2>/dev/null | head -3
echo "    Renewal is automatic; nginx reloads via the deploy hook."
echo "    Dry run:  sudo certbot renew --dry-run"

cat <<SUMMARY

$(printf '\033[1;32m==> HTTPS is enabled.\033[0m')

HSTS needs no further action: the application emits Strict-Transport-Security
only on requests that actually arrived over TLS, so it is live as of now.
SUMMARY
