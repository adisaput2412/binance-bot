"""
state.py — shared bot state between the trading loop and the web dashboard.

The bot writes to this every tick. Flask reads from it to serve the dashboard.
Uses a threading.Lock so reads and writes don't collide.
"""

import threading
from datetime import datetime


class BotState:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {
            # Bot meta
            "status":       "starting",   # "running", "halted", "stopped"
            "mode":         "TESTNET",
            "symbol":       "BTCUSDT",
            "interval":     "5m",
            "started_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_updated": None,

            # Live market data
            "price":        None,
            "sma_short":    None,
            "sma_long":     None,
            "rsi":          None,
            "last_signal":  "HOLD",

            # Position
            "in_position":  False,
            "entry_price":  None,

            # Session P&L
            "total_pnl":        0.0,
            "wins":             0,
            "losses":           0,
            "starting_balance": None,
            "current_balance":  None,

            # Trade history (list of dicts)
            "trades": [],
        }

    def update(self, **kwargs) -> None:
        with self._lock:
            self._data.update(kwargs)
            self._data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def add_trade(self, trade: dict) -> None:
        with self._lock:
            self._data["trades"].insert(0, trade)   # newest first
            if len(self._data["trades"]) > 100:     # cap at 100
                self._data["trades"] = self._data["trades"][:100]

    def get(self) -> dict:
        with self._lock:
            return dict(self._data)


# Singleton — import this everywhere
bot_state = BotState()
