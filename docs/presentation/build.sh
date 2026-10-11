#!/bin/sh
# Renders deck.html to fsp-career.pdf with headless Chrome.
# Usage: ./build.sh [stand-url]   (default: the public demo stand)
set -e
cd "$(dirname "$0")"
STAND="${1:-https://fsp-career.85-208-86-188.sslip.io}"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
sed -e "s|__STAND_URL__|${STAND#https://}|g" -e "s|__DOCS_URL__|${STAND#https://}/api/docs|g" deck.html > .deck.rendered.html
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf=fsp-career.pdf "file://$PWD/.deck.rendered.html" >/dev/null 2>&1
echo "built fsp-career.pdf"
