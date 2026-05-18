"""
state.py — shared bot state between the trading loop and the web dashboard.

Holds a global status block + per-pair state for all active trading pairs.
"""

import threading
from datetime import datetime


class BotState:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {
            # Bot meta
            "status":       "starting",
            "mode":         "TESTNET",
            "started_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_updated": None,

            # Sentiment (shared across all pairs)
            "sentiment_verdict":  "NEUTRAL",
            "sentiment_fg_value": None,
            "sentiment_fg_label": None,
            "sentiment_news":     [],
            "sentiment_updated":  None,

            # Per-pair state — keyed by symbol e.g. "BTCUSDT"
            "pairs": {},

            # Combined trade history across all pairs
            "trades": [],
        }

    def update(self, **kwargs) -> None:
        with self._lock:
            self._data.update(kwargs)
            self._data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def update_pair(self, symbol: str, **kwargs) -> None:
        """Update state for a specific trading pair."""
        with self._lock:
            if symbol not in self._data["pairs"]:
                self._data["pairs"][symbol] = {
                    "symbol":          symbol,
                    "price":           None,
                    "sma_short":       None,
                    "sma_long":        None,
                    "rsi":             None,
                    "last_signal":     "HOLD",
                    "in_position":     False,
                    "entry_price":     None,
                    "total_pnl":       0.0,
                    "wins":            0,
                    "losses":          0,
                    "status":          "running",
                    "starting_balance": None,
                    "current_balance":  None,
                }
            self._data["pairs"][symbol].update(kwargs)
            self._data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def add_trade(self, trade: dict) -> None:
        with self._lock:
            self._data["trades"].insert(0, trade)
            if len(self._data["trades"]) > 200:
                self._data["trades"] = self._data["trades"][:200]

    def get(self) -> dict:
        with self._lock:
            return dict(self._data)


# Singleton — import this everywhere
bot_state = BotState()
