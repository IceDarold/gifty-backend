#!/bin/bash

# 1. Load base configuration from .env (ignoring comments)
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# 2. Override for Local Development (Native Python)
export API_BASE="http://localhost:8000"
export POSTGRES_HOST="localhost"
export REDIS_HOST="localhost"
export RABBITMQ_HOST="localhost"

# RabbitMQ URL often needs explicit localhost if not using default
export RABBITMQ_URL="amqp://guest:guest@localhost:5672/"
export REDIS_URL="redis://localhost:6379/0"

# 3. Mini App URL (Local or Ngrok)
# If you use ngrok, replace this with your https url
export TELEGRAM_WEBAPP_URL="http://localhost:3000"

# 4. Check for Test Token
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
  echo "⚠️  TELEGRAM_BOT_TOKEN is missing!"
  echo "Please edit this script or export your test token:"
  echo "export TELEGRAM_BOT_TOKEN='your_test_bot_token'"
  exit 1
fi

echo "🚀 Starting Telegram Bot in Local Dev Mode..."
echo "API: $API_BASE"
echo "WebApp: $TELEGRAM_WEBAPP_URL"
echo "Token: ${TELEGRAM_BOT_TOKEN:0:5}..."

# 5. Run Bot Module
python -m services.telegram_bot.app.main
