"""
trade_log.py — Persistent trade history stored in trade_history.json.

Trades survive bot restarts. Every BUY/SELL is appended to disk immediately.
"""

import json
import os
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

TRADE_LOG_FILE = "trade_history.json"
_lock = threading.Lock()


def _load_raw() -> list:
    if not os.path.exists(TRADE_LOG_FILE):
        return []
    try:
        with open(TRADE_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load trade history: {e}")
        return []


def _save_raw(trades: list) -> None:
    try:
        with open(TRADE_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(trades, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save trade history: {e}")


def load_all() -> list:
    """Load all trades from disk (called on bot startup)."""
    with _lock:
        trades = _load_raw()
    logger.info(f"Loaded {len(trades)} trades from trade history")
    return trades


def append_trade(trade: dict) -> None:
    """Append a single trade to disk immediately."""
    if "saved_at" not in trade:
        trade["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        trades = _load_raw()
        trades.insert(0, trade)
        _save_raw(trades)


def get_stats() -> dict:
    """Return overall stats from the full persistent history."""
    trades = load_all()
    sell_trades = [t for t in trades if t.get("side") == "SELL" and t.get("pnl") is not None]
    wins   = [t for t in sell_trades if t["pnl"] > 0]
    losses = [t for t in sell_trades if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in sell_trades)
    win_rate  = len(wins) / len(sell_trades) * 100 if sell_trades else 0.0
    return {
        "total_trades": len(sell_trades),
        "wins":         len(wins),
        "losses":       len(losses),
        "win_rate":     round(win_rate, 1),
        "total_pnl":    round(total_pnl, 4),
    }
