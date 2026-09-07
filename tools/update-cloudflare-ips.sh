#!/usr/bin/env bash
#
# Regenerate the nginx real-IP snippet from Cloudflare's published ranges.
#
#     ./tools/update-cloudflare-ips.sh
#
# Behind the Cloudflare proxy every request arrives from a Cloudflare address,
# so without this nginx sees a handful of distinct clients: rate limiting would
# throttle all visitors collectively, and logs would record the edge rather than
# the caller. `set_real_ip_from` trusts only these ranges, so the
# CF-Connecting-IP header cannot be spoofed by a direct connection.
#
# Cloudflare changes these ranges rarely; re-run when they announce a change.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/deploy/nginx/snippets/cloudflare-real-ip.conf"
TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT

echo "==> Fetching Cloudflare IP ranges"
V4="$(curl -fsS --max-time 20 https://www.cloudflare.com/ips-v4)"
V6="$(curl -fsS --max-time 20 https://www.cloudflare.com/ips-v6)"

if [[ -z "${V4}" || -z "${V6}" ]]; then
  echo "Refusing to write an empty range list." >&2
  exit 1
fi

{
  echo "# Cloudflare edge ranges — GENERATED, do not edit by hand."
  echo "# Regenerate with tools/update-cloudflare-ips.sh"
  echo "# Source: https://www.cloudflare.com/ips-v4 and ips-v6"
  echo "# Fetched: $(date -u +%Y-%m-%d)"
  echo
  while read -r cidr; do [[ -n "${cidr}" ]] && echo "set_real_ip_from ${cidr};"; done <<< "${V4}"
  echo
  while read -r cidr; do [[ -n "${cidr}" ]] && echo "set_real_ip_from ${cidr};"; done <<< "${V6}"
  echo
  echo "# Trust the edge's own header only, and only from the ranges above."
  echo "real_ip_header CF-Connecting-IP;"
  echo "real_ip_recursive off;"
} > "${TMP}"

mv "${TMP}" "${OUT}"
trap - EXIT

echo "==> Wrote ${OUT#"${ROOT}/"} ($(grep -c set_real_ip_from "${OUT}") ranges)"
