#!/usr/bin/env bash
#
# Rebuild the vendored QR encoder from upstream source.
#
# The result is committed to the repository so that the bytes served to users
# are reviewable in a diff, rather than pulled from a registry at deploy time.
# Re-run this and check `git diff` to verify the committed bundle is genuine.
#
# Usage:  ./tools/build-vendor.sh
# Needs:  node + npm (build time only; the app itself has no Node dependency)

set -euo pipefail

QRCODE_VERSION="1.5.4"
ESBUILD_VERSION="0.28.2"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT}/app/static/js/vendor"
OUT_FILE="${OUT_DIR}/qrcode.min.js"
WORK_DIR="$(mktemp -d)"

cleanup() { rm -rf "${WORK_DIR}"; }
trap cleanup EXIT

echo "==> Building qrcode@${QRCODE_VERSION} with esbuild@${ESBUILD_VERSION}"

cd "${WORK_DIR}"
npm init -y >/dev/null 2>&1
npm install --no-audit --no-fund --silent \
  "qrcode@${QRCODE_VERSION}" "esbuild@${ESBUILD_VERSION}"

mkdir -p "${OUT_DIR}"

./node_modules/.bin/esbuild node_modules/qrcode/lib/browser.js \
  --bundle \
  --format=iife \
  --global-name=QRCode \
  --platform=browser \
  --target=es2018 \
  --minify \
  --legal-comments=inline \
  --outfile="${OUT_FILE}"

cp node_modules/qrcode/license "${OUT_DIR}/qrcode.LICENSE.txt"

echo "==> Wrote ${OUT_FILE#"${ROOT}/"} ($(wc -c < "${OUT_FILE}" | tr -d ' ') bytes)"
echo "==> SHA-384: $(openssl dgst -sha384 -binary "${OUT_FILE}" | openssl base64 -A)"
echo
echo "Review with:  git diff --stat -- app/static/js/vendor/"
