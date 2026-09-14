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
TRADE_PAIRS = [
    {
        "symbol":   "BTCUSDT",
        "quantity": 0.001,    # ~$100 worth at $100k BTC
        "interval": "1h",
    },
    {
        "symbol":   "ETHUSDT",
        "quantity": 0.01,     # ~$25 worth at $2500 ETH
        "interval": "1h",
    },
    {
        "symbol":   "SOLUSDT",
        "quantity": 0.1,      # ~$15 worth at $150 SOL
        "interval": "1h",
    },
    {
        "symbol":   "BNBUSDT",
        "quantity": 0.05,     # ~$15 worth at $300 BNB
        "interval": "1h",
    },
    {
        "symbol":   "ADAUSDT",
        "quantity": 10,       # ~$5 worth at $0.50 ADA
        "interval": "1h",
    },
    {
        "symbol":   "DOTUSDT",
        "quantity": 2,        # ~$8 worth at $4 DOT
        "interval": "1h",
    },
    {
        "symbol":   "LINKUSDT",
        "quantity": 0.5,      # ~$7 worth at $14 LINK
        "interval": "1h",
    },
    {
        "symbol":   "AVAXUSDT",
        "quantity": 0.2,      # ~$6 worth at $30 AVAX
        "interval": "1h",
    },
]

# ── Strategy settings (shared across all pairs) ────────────────────
# 2026-09-14: live win rate at 6% TP was ~8% — TP tightened to 2.5%
# (closer to the 2% SL) to raise win rate at the cost of smaller wins.
# Re-verify with backtest.py --interval 1h --days 90 before trusting this.
TRADE_INTERVAL = "1h"    # default fallback
SMA_SHORT      = 20
SMA_LONG       = 50
RSI_PERIOD     = 14

# ADX = trend-strength chop filter. SMA crossovers whipsaw in ranging
# markets; requiring ADX >= threshold means we only trade when a real
# trend is underway. 20 is a common "some trend" cutoff (25+ = strong).
ADX_PERIOD     = 14
ADX_THRESHOLD  = 20

# ── Risk settings (applied per pair) ──────────────────────────────
STOP_LOSS_PCT        = 2.0   # 2% drop from entry → stop-loss sell
TAKE_PROFIT_PCT      = 2.5   # 2.5% rise from entry → take-profit sell (tightened from 6% to raise win rate; was ~8% win rate at 6% TP)
MAX_SESSION_LOSS_PCT = 10.0  # 10% total session loss → halt that pair

# ── Telegram notifications ─────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
