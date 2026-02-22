#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

SSH_ALIAS="${SSH_ALIAS:-gifty}"
DB_LOCAL_PORT="${DB_LOCAL_PORT:-5433}"
DB_REMOTE_PORT="${DB_REMOTE_PORT:-5432}"
ADMIN_TMA_PORT="${ADMIN_TMA_PORT:-3000}"
LOG_DIR="${LOG_DIR:-/tmp/gifty-dev}"
NEXT_LOG="$LOG_DIR/admin-tma.log"
NGROK_LOG="$LOG_DIR/ngrok.log"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env}"

mkdir -p "$LOG_DIR"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

wait_port() {
  local host="$1"
  local port="$2"
  local retries="${3:-30}"
  local i
  for i in $(seq 1 "$retries"); do
    if nc -z "$host" "$port" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

update_env_webapp_url() {
  local url="$1"
  if [ ! -f "$ENV_FILE" ]; then
    return 0
  fi

  if grep -q '^TELEGRAM_WEBAPP_URL=' "$ENV_FILE"; then
    sed -i '' "s|^TELEGRAM_WEBAPP_URL=.*$|TELEGRAM_WEBAPP_URL=${url}|" "$ENV_FILE"
  else
    printf '\nTELEGRAM_WEBAPP_URL=%s\n' "$url" >> "$ENV_FILE"
  fi
}

require_cmd ssh
require_cmd docker
require_cmd npm
require_cmd curl
require_cmd python3
require_cmd nc

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is required"
  exit 1
fi

echo "[1/5] SSH tunnel: localhost:${DB_LOCAL_PORT} -> ${SSH_ALIAS}:${DB_REMOTE_PORT}"
pkill -f "ssh.*-L ${DB_LOCAL_PORT}:localhost:${DB_REMOTE_PORT}" 2>/dev/null || true
ssh -f -N \
  -o ServerAliveInterval=60 \
  -o ServerAliveCountMax=10 \
  -o ExitOnForwardFailure=yes \
  -L "${DB_LOCAL_PORT}:localhost:${DB_REMOTE_PORT}" \
  "$SSH_ALIAS"

if wait_port "localhost" "$DB_LOCAL_PORT" 10; then
  echo "SSH tunnel is up"
else
  echo "Failed to open SSH tunnel on localhost:${DB_LOCAL_PORT}"
  exit 1
fi

echo "[2/5] Docker services"
docker compose up -d postgres redis rabbitmq api telegram-bot

echo "[3/5] Admin TMA (Next.js) on http://localhost:${ADMIN_TMA_PORT}"
pkill -f "next dev.*--port ${ADMIN_TMA_PORT}" 2>/dev/null || true
(
  cd "$SCRIPT_DIR/apps/admin-tma"
  npm run dev -- --port "$ADMIN_TMA_PORT" --hostname 0.0.0.0 >"$NEXT_LOG" 2>&1
) &

if wait_port "localhost" "$ADMIN_TMA_PORT" 30; then
  echo "Admin TMA is up"
else
  echo "Admin TMA failed to start. Log: $NEXT_LOG"
  exit 1
fi

echo "[4/5] ngrok tunnel"
NGROK_BIN="${NGROK_BIN:-$SCRIPT_DIR/ngrok}"
if [ ! -x "$NGROK_BIN" ]; then
  NGROK_BIN="$(command -v ngrok || true)"
fi
if [ -z "$NGROK_BIN" ]; then
  echo "ngrok binary not found (set NGROK_BIN or install ngrok)"
  exit 1
fi

pkill -f "ngrok http ${ADMIN_TMA_PORT}" 2>/dev/null || true
"$NGROK_BIN" http "$ADMIN_TMA_PORT" --log=stdout >"$NGROK_LOG" 2>&1 &

NGROK_URL=""
for _ in $(seq 1 20); do
  NGROK_URL="$(curl -s http://localhost:4040/api/tunnels | python3 -c 'import json,sys; d=json.load(sys.stdin); print(next((t["public_url"] for t in d.get("tunnels", []) if t.get("public_url","").startswith("https://")), ""))' 2>/dev/null || true)"
  if [ -n "$NGROK_URL" ]; then
    break
  fi
  sleep 1
done

if [ -z "$NGROK_URL" ]; then
  echo "Failed to get ngrok public URL. Log: $NGROK_LOG"
  exit 1
fi

echo "[5/5] Update TELEGRAM_WEBAPP_URL and restart bot"
update_env_webapp_url "$NGROK_URL"
docker compose up -d telegram-bot >/dev/null 2>&1 || true

echo
echo "Dev environment ready"
echo "Dashboard:     $NGROK_URL"
echo "Local admin:   http://localhost:${ADMIN_TMA_PORT}"
echo "Local API:     http://localhost:8000"
echo "DB tunnel:     localhost:${DB_LOCAL_PORT} -> ${SSH_ALIAS}:${DB_REMOTE_PORT}"
echo "Next log:      $NEXT_LOG"
echo "Ngrok log:     $NGROK_LOG"
