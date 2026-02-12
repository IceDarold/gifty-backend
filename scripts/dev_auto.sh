#!/bin/bash

# --- 1. Load Environment ---
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Override specific variables for Localhost Development
export API_BASE="http://localhost:8000"
export POSTGRES_HOST="localhost"
export REDIS_HOST="localhost"
export RABBITMQ_HOST="localhost"
export RABBITMQ_URL="amqp://guest:guest@localhost:5672/"
export REDIS_URL="redis://localhost:6379/0"
export TELEGRAM_BOT_TOKEN="8581358531:AAHJifvA3mLFjAVHAZVYjecjyEAsZhimnyw"


# --- 2. Check Dependencies ---
if ! command -v npm &> /dev/null; then
    echo "🚨 npm not found! Please install Node.js."
    exit 1
fi
if ! command -v python3 &> /dev/null; then
    echo "🚨 python3 not found!"
    exit 1
fi

# --- 3. Prompt for Token (if missing) ---
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo ""
    echo "🤖 Enter your TEST TELEGRAM BOT TOKEN (from @BotFather):"
    read -s TELEGRAM_BOT_TOKEN
    export TELEGRAM_BOT_TOKEN
    echo "✅ Token captured."
fi

# --- 4. Start Infrastructure ---
echo "🐳 Starting Docker Services..."
docker compose up -d postgres redis rabbitmq api

# --- 5. Start Ngrok (Background) ---
echo "Tunneling localhost:3000 -> Public URL..."
pkill -f ngrok  # Kill any existing tunnels
nohup npx ngrok http 3000 > /dev/null 2>&1 &
NGROK_PID=$!
sleep 5

# Fetch public URL from ngrok API
PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null)

if [ -z "$PUBLIC_URL" ]; then
    echo "❌ Failed to start ngrok or get public URL. Check 'ngrok' command."
    echo "   Ensure you have run 'ngrok config add-authtoken <TOKEN>' once."
    kill $NGROK_PID
    exit 1
fi

export TELEGRAM_WEBAPP_URL="$PUBLIC_URL"
echo "🌐 Web App Live at: $TELEGRAM_WEBAPP_URL"
echo "   (Make sure to update this URL in @BotFather if needed!)"

# --- 6. Start Frontend (Background) ---
echo "💻 Starting Admin Mini App (Next.js)..."
cd apps/admin-tma
nohup npm run dev > ../../nextjs.log 2>&1 &
NEXT_PID=$!
cd ../..

echo "   (Frontend logs: tail -f nextjs.log)"

# --- 7. Start Python Bot (Foreground) ---
echo "🤖 Starting Telegram Bot..."
echo "   Press Ctrl+C to stop everything."
echo ""

# Trap to kill background processes on exit
cleanup() {
    echo ""
    echo "🛑 Stopping..."
    kill $NGROK_PID
    kill $NEXT_PID
    exit
}
trap cleanup SIGINT

python3 -m services.telegram_bot.app.main
