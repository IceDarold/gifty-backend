#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Env file not found: $ENV_FILE"
  exit 1
fi

# Switch DATABASE_URL back to SSH tunnel port 5433.
sed -i '' 's/@host\.docker\.internal:5432\//@host.docker.internal:5433\//g' "$ENV_FILE"

echo "Switched DATABASE_URL to remote DB via SSH tunnel (host.docker.internal:5433)"
grep '^DATABASE_URL=' "$ENV_FILE"
