#!/bin/sh
# Container entrypoint: apply database migrations, then become uvicorn.
# Demo data (when SEED_DEMO_DATA=true) is created by the application itself
# on startup, only if the database is empty.
set -eu

case "${JWT_SECRET:-}" in
  "" | dev-only-* | change-me*)
    echo "WARNING: JWT_SECRET is empty or a placeholder. Acceptable for a local demo, never for a public server." >&2
    ;;
esac

echo "Applying database migrations..."
alembic upgrade head

echo "Starting API on port 8000..."
# The API sits behind the nginx container (and possibly a TLS proxy in front of
# it). Trust X-Forwarded-Proto from any peer (the caller is the web container,
# not 127.0.0.1) so redirects built by Starlette keep the public https scheme;
# the client address is not used for any decision.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
