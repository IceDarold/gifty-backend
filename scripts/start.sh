#!/usr/bin/env sh
set -e

echo "Running migrations..."
alembic upgrade head

echo "Starting Gunicorn..."
exec gunicorn app.main:app \
  --workers "${WEB_CONCURRENCY:-2}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
