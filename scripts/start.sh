#!/usr/bin/env sh
set -e

if [ "${SKIP_MIGRATIONS:-0}" = "1" ]; then
  echo "Skipping migrations (SKIP_MIGRATIONS=1)"
else
  TARGET="${ALEMBIC_UPGRADE_TARGET:-head}"
  echo "Running migrations (alembic upgrade ${TARGET})..."
  alembic upgrade "${TARGET}"
fi

echo "Starting Gunicorn..."
exec gunicorn app.main:app \
  --workers "${WEB_CONCURRENCY:-2}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
