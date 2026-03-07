#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

SSH_ALIAS="${SSH_ALIAS:-gifty}"
DB_LOCAL_PORT="${DB_LOCAL_PORT:-5433}"
DB_REMOTE_PORT="${DB_REMOTE_PORT:-5432}"
CLOSE_TUNNEL_AFTER="${CLOSE_TUNNEL_AFTER:-0}"

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

require_cmd ssh
require_cmd docker
require_cmd nc

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is required"
  exit 1
fi

detect_heads() {
  docker compose run --rm --no-deps api alembic heads 2>&1 | awk '{print $1}' | sed '/^$/d' || true
}

tunnel_started=0

if nc -z localhost "$DB_LOCAL_PORT" >/dev/null 2>&1; then
  echo "SSH tunnel already available on localhost:${DB_LOCAL_PORT}"
else
  echo "Opening SSH tunnel: localhost:${DB_LOCAL_PORT} -> ${SSH_ALIAS}:${DB_REMOTE_PORT}"
  if ! ssh -o BatchMode=yes -o ConnectTimeout=8 "$SSH_ALIAS" "exit 0" >/dev/null 2>&1; then
    echo "SSH non-interactive check failed for alias '$SSH_ALIAS'."
    echo "Fix:"
    echo "  1) ensure alias exists in ~/.ssh/config"
    echo "  2) ensure key auth works: ssh-add --apple-use-keychain ~/.ssh/<key>"
    echo "  3) first-time host key: ssh ${SSH_ALIAS}"
    exit 1
  fi
  ssh -f -N \
    -o BatchMode=yes \
    -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=accept-new \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=10 \
    -o ExitOnForwardFailure=yes \
    -L "${DB_LOCAL_PORT}:localhost:${DB_REMOTE_PORT}" \
    "$SSH_ALIAS"

  if wait_port "localhost" "$DB_LOCAL_PORT" 12; then
    tunnel_started=1
    echo "SSH tunnel is up"
  else
    echo "Failed to open SSH tunnel on localhost:${DB_LOCAL_PORT}"
    exit 1
  fi
fi

echo "Running migrations from current local code..."
heads="$(detect_heads)"
head_count="$(echo "$heads" | sed '/^$/d' | wc -l | tr -d ' ')"
if [ "${head_count:-0}" -gt 1 ]; then
  echo "ERROR: multiple Alembic heads detected in current codebase:"
  echo "$heads" | sed 's/^/  - /'
  echo
  if [ "${AUTO_MERGE_HEADS:-0}" = "1" ]; then
    echo "AUTO_MERGE_HEADS=1: creating an automatic merge revision..."
    # Generate merge revision in the mounted worktree (so it persists locally).
    docker compose run --rm --no-deps api alembic merge -m "auto: merge heads" $heads
    echo
    echo "Created merge revision. Commit it, then rerun this script."
    echo "Tip: git status && git add alembic/versions && git commit -m \"fix(migrations): merge alembic heads\""
  else
    echo "Fix: create a merge revision and commit it, then rerun this script:"
    echo "  docker compose run --rm --no-deps api alembic merge -m \"merge heads\" $heads"
  fi
  exit 1
fi

docker compose run --rm --no-deps api alembic upgrade head

echo "Checking migration state..."
docker compose run --rm --no-deps api alembic current

if [ "$tunnel_started" = "1" ] && [ "$CLOSE_TUNNEL_AFTER" = "1" ]; then
  echo "Closing SSH tunnel on localhost:${DB_LOCAL_PORT}"
  pkill -f "ssh.*-L ${DB_LOCAL_PORT}:localhost:${DB_REMOTE_PORT}" 2>/dev/null || true
fi

echo "Done."
