#!/bin/bash
# vps-setup.sh — run this once on a fresh Ubuntu 22.04 VPS
# Usage: bash vps-setup.sh

set -e

echo "=== Binance Bot VPS Setup ==="

# 1. Update system
echo "[1/6] Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq

# 2. Install Python and git
echo "[2/6] Installing Python 3, pip, git..."
apt-get install -y -qq python3 python3-pip python3-venv git

# 3. Clone the repo (edit this URL after pushing to GitHub)
REPO_URL="https://github.com/YOUR_USERNAME/binance-bot.git"
BOT_DIR="/home/$USER/binance-bot"

if [ ! -d "$BOT_DIR" ]; then
  echo "[3/6] Cloning repo to $BOT_DIR..."
  git clone "$REPO_URL" "$BOT_DIR"
else
  echo "[3/6] Repo already exists — pulling latest..."
  git -C "$BOT_DIR" pull
fi

# 4. Install Python dependencies
echo "[4/6] Installing Python dependencies..."
pip3 install -r "$BOT_DIR/requirements.txt" --break-system-packages -q

# 5. Create .env file placeholder
ENV_FILE="$BOT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "[5/6] Creating .env placeholder — fill in your keys!"
  cat > "$ENV_FILE" <<EOF
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
USE_TESTNET=true
TELEGRAM_TOKEN=your_telegram_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
EOF
  echo "      --> Edit $ENV_FILE with your real keys before starting the bot"
else
  echo "[5/6] .env already exists — skipping"
fi

# 6. Install systemd service
echo "[6/6] Installing systemd service..."
SERVICE_SRC="$BOT_DIR/binance-bot.service"
SERVICE_DST="/etc/systemd/system/binance-bot.service"

# Replace username placeholder with actual user
sed "s/holy/$USER/g" "$SERVICE_SRC" > "$SERVICE_DST"

systemctl daemon-reload
systemctl enable binance-bot

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit your API keys:  nano $ENV_FILE"
echo "  2. Start the bot:       systemctl start binance-bot"
echo "  3. Check status:        systemctl status binance-bot"
echo "  4. Watch live logs:     journalctl -u binance-bot -f"
echo "  5. View dashboard:      http://$(curl -s ifconfig.me):5000"
echo ""
