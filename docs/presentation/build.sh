#!/bin/sh
# Renders deck.html to fsp-career.pdf with headless Chrome.
# Usage: ./build.sh [stand-url]   (without it the last slide shows the local run command)
set -e
cd "$(dirname "$0")"
if [ -n "$1" ]; then
  STAND_TEXT="${1#https://}"
  DOCS_TEXT="${1#https://}/api/docs"
else
  STAND_TEXT="docker compose up --build → localhost:8088"
  DOCS_TEXT="localhost:8100/api/docs"
fi
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
sed -e "s|__STAND_URL__|${STAND_TEXT}|g" -e "s|__DOCS_URL__|${DOCS_TEXT}|g" deck.html > .deck.rendered.html
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf=fsp-career.pdf "file://$PWD/.deck.rendered.html" >/dev/null 2>&1
echo "built fsp-career.pdf"
