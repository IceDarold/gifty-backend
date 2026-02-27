#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

DB_LOCAL_PORT="${DB_LOCAL_PORT:-5433}"
DB_REMOTE_PORT="${DB_REMOTE_PORT:-5432}"
ADMIN_TMA_PORT="${ADMIN_TMA_PORT:-3000}"

echo "[1/4] Stop Admin TMA (Next.js)"
pkill -f "next dev.*--port ${ADMIN_TMA_PORT}" 2>/dev/null || true

echo "[2/4] Stop ngrok"
pkill -f "ngrok http ${ADMIN_TMA_PORT}" 2>/dev/null || true

echo "[3/4] Stop SSH tunnel"
pkill -f "ssh.*-L ${DB_LOCAL_PORT}:localhost:${DB_REMOTE_PORT}" 2>/dev/null || true

echo "[4/4] Stop Docker services"
if docker compose version >/dev/null 2>&1; then
  docker compose stop postgres redis rabbitmq api scraper telegram-bot >/dev/null 2>&1 || true
fi

echo "Dev environment stopped"
