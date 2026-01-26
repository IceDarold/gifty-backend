#!/bin/bash

# Exit on error
set -e

echo "Running migrations..."
alembic upgrade head

echo "Starting Gunicorn..."
# Use Gunicorn with Uvicorn workers for production
exec gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-log-file - \
    --error-log-file -
