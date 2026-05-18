"""
config.py — loads settings from .env
Copy .env.example to .env and fill in your testnet API keys.
"""

import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
USE_TESTNET = os.getenv("USE_TESTNET", "true").lower() == "true"

# Testnet base URLs
TESTNET_BASE_URL = "https://testnet.binance.vision/api"

# Trading pairs to watch (edit freely)
WATCH_PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

# How often to fetch prices (seconds)
FETCH_INTERVAL = 10

# ── Strategy settings ──────────────────────────────────────────────
# Active trading pair for the strategy loop
TRADE_SYMBOL = "BTCUSDT"

# Candle interval — options: 1m, 5m, 15m, 1h, 4h, 1d
TRADE_INTERVAL = "5m"

# How much to buy/sell per trade (in base asset units, e.g. BTC)
# Keep this small on testnet while you're learning
TRADE_QUANTITY = 0.001   # = ~$68 worth of BTC at $68k

# SMA periods
SMA_SHORT = 9
SMA_LONG  = 21

# RSI period
RSI_PERIOD = 14

# ── Risk settings ──────────────────────────────────────────────────
# Stop-loss: auto-sell if price drops this % below entry
STOP_LOSS_PCT = 2.0        # 2% drop → exit immediately

# Max session loss: halt all trading if total loss hits this %
MAX_SESSION_LOSS_PCT = 5.0  # 5% of starting balance → stop for the session

# ── Telegram notifications ─────────────────────────────────────────
# Leave blank to disable — bot works fine without it
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
