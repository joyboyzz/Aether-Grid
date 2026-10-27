#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${AG_OPERATOR_TOKEN:?Set AG_OPERATOR_TOKEN to a local demo review token before running}"
(cd frontend && npm ci && npm run build)
export AG_ENV=demo
export AG_DB_PATH="${AG_DB_PATH:-$PWD/verification/demo.db}"
# Explicit accelerated demonstration clock; never use this as real device timing.
export AG_SIM_BIO_HOURS_PER_PACKET="${AG_SIM_BIO_HOURS_PER_PACKET:-1}"
cd backend
exec python -m uvicorn app.main:asgi_app --host 0.0.0.0 --port "${PORT:-8000}"
