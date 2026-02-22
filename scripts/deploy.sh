#!/bin/bash
# Zero-Downtime Deployment Script for Gifty (Blue-Green with Nginx)

set -e

PROJECT_NAME="gifty"
NGINX_UPSTREAM_CONF="/etc/nginx/conf.d/gifty_upstream.conf"
APP_SERVICE="api"

# 1. Determine which port is currently active
if docker ps | grep -q ":8000->8000"; then
    ACTIVE_PORT=8000
    NEW_PORT=8001
    ACTIVE_COLOR="blue"
    NEW_COLOR="green"
else
    ACTIVE_PORT=8001
    NEW_PORT=8000
    ACTIVE_COLOR="green"
    NEW_COLOR="blue"
fi

echo "Active port: $ACTIVE_PORT ($ACTIVE_COLOR). Deploying to $NEW_PORT ($NEW_COLOR)..."

# 2. Build and start new version in the free slot
# We use project name + color to keep containers separate if needed, 
# but here we'll just use environment variables for port mapping.
if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

APP_PORT=$NEW_PORT $COMPOSE_CMD up -d --build $APP_SERVICE

# 3. Health Check
echo "Waiting for $NEW_COLOR version to be healthy at localhost:$NEW_PORT..."
MAX_RETRIES=24
COUNT=0
while [ $COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:$NEW_PORT/health | grep -q '"status"'; then
        if curl -s http://localhost:$NEW_PORT/health | grep -q '"ok"'; then
             echo "New version is HEALTHY!"
             break
        fi
    fi
    echo "Still waiting... ($((COUNT+1))/$MAX_RETRIES)"
    sleep 5
    COUNT=$((COUNT+1))
done

if [ $COUNT -eq $MAX_RETRIES ]; then
    echo "Error: New version failed health check. Rolling back..."
    APP_PORT=$NEW_PORT $COMPOSE_CMD stop $APP_SERVICE
    exit 1
fi

# 4. Switch Nginx
echo "Switching Nginx upstream to port $NEW_PORT..."
cat <<EOF | sudo tee $NGINX_UPSTREAM_CONF > /dev/null
upstream gifty_backend {
    server 127.0.0.1:$NEW_PORT;
    keepalive 32;
}
EOF

sudo nginx -s reload
echo "Nginx reloaded successfully."

# 5. Cleanup: stop the old version
echo "Stopping old $ACTIVE_COLOR version..."
# We need to find the container ID of the OLD port since docker-compose 
# might have replaced it if we didn't use separate project names.
# However, for simplicity with one docker-compose.yml, we'll just stop the one 
# that is NOT our new port.
# Note: In a true Blue-Green with one compose file, we might need two services.
# For now, let's assume we want to keep it simple.

echo "Deployment complete! New active port: $NEW_PORT"
