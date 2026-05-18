"""
config.py — loads settings from .env
Copy env-template.env.txt to .env and fill in your testnet API keys.
"""

import os
from dotenv import load_dotenv

load_dotenv()

API_KEY    = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
USE_TESTNET = os.getenv("USE_TESTNET", "true").lower() == "true"

# How often to fetch prices per pair (seconds)
FETCH_INTERVAL = 10

# ── Multi-pair trading config ──────────────────────────────────────
# Each pair runs independently in its own thread.
# quantity = how much to buy/sell per trade in base asset units.
# Keep small on testnet. On live: size to your risk tolerance.
#
# NOTE: KITEUSDT may not be listed on testnet — if it errors,
#       remove it or replace with another pair like DOGEUSDT.

TRADE_PAIRS = [
    {
        "symbol":   "BTCUSDT",
        "quantity": 0.001,    # ~$100 worth at $100k BTC
        "interval": "5m",
    },
    {
        "symbol":   "ETHUSDT",
        "quantity": 0.01,     # ~$25 worth at $2500 ETH
        "interval": "5m",
    },
    {
        "symbol":   "SOLUSDT",
        "quantity": 0.1,      # ~$15 worth at $150 SOL
        "interval": "5m",
    },
    {
        "symbol":   "KITEUSDT",
        "quantity": 10.0,     # adjust based on KITE price
        "interval": "5m",
    },
]

# ── Strategy settings (shared across all pairs) ────────────────────
TRADE_INTERVAL = "5m"    # default fallback
SMA_SHORT      = 9
SMA_LONG       = 21
RSI_PERIOD     = 14

# ── Risk settings (applied per pair) ──────────────────────────────
STOP_LOSS_PCT        = 2.0   # 2% drop from entry → stop-loss sell
MAX_SESSION_LOSS_PCT = 5.0   # 5% total session loss → halt that pair

# ── Telegram notifications ─────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
