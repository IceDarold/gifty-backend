#!/usr/bin/env sh
set -e

echo "Running migrations..."
# We intentionally allow multiple Alembic heads in the repo.
# Use "heads" to upgrade all branches; "head" fails when multiple heads exist.
alembic upgrade heads

echo "Starting Gunicorn..."
rm -f /app/gunicorn.ctl 2>/dev/null || true
exec gunicorn app.main:app \
  --workers "${WEB_CONCURRENCY:-2}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --no-control-socket \
  --access-logfile - \
  --error-logfile -
