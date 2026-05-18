"""
main.py — Binance Bot Core — multi-pair trading.

Runs one independent strategy thread per trading pair.
Dashboard at http://localhost:5000 (or http://YOUR_VPS_IP:5000)

Before running:
  1. Fill in .env with your keys (see env-template.env.txt)
  2. pip install -r requirements.txt  (or use venv)
  3. python main.py
"""

import logging
import time
import threading

from src.client import get_client, check_connection
from src.indicators import get_indicators
from src.strategy import get_signal
from src.risk import RiskManager
from src.performance import PerformanceTracker
from src.trader import Trader
from src.data import get_account_balance
from src.state import bot_state
from src.sentiment import get_sentiment
import src.notifier as notifier
from dashboard.app import run_dashboard
from src.config import (
    USE_TESTNET,
    TRADE_PAIRS,
    FETCH_INTERVAL,
    SMA_SHORT,
    SMA_LONG,
    RSI_PERIOD,
    STOP_LOSS_PCT,
    MAX_SESSION_LOSS_PCT,
)

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# Shared sentiment (updated every 15 min, read by all pair threads)
_sentiment_lock = threading.Lock()
_current_sentiment = {"verdict": "NEUTRAL", "fg_value": 50, "fg_label": "Unknown"}


def get_usdt_balance(client) -> float:
    balances = get_account_balance(client)
    for b in balances:
        if b["asset"] == "USDT":
            return float(b["free"])
    return 0.0


def _update_sentiment_state(s: dict) -> None:
    if not s:
        return
    bot_state.update(
        sentiment_verdict=s.get("verdict", "NEUTRAL"),
        sentiment_fg_value=s.get("fg_value"),
        sentiment_fg_label=s.get("fg_label"),
        sentiment_news=s.get("headlines", []),
        sentiment_updated=s.get("updated_at"),
    )


def sentiment_loop():
    """Background thread — refreshes sentiment every 15 minutes."""
    global _current_sentiment
    while True:
        try:
            s = get_sentiment()
            if s:
                with _sentiment_lock:
                    _current_sentiment = s
                _update_sentiment_state(s)
        except Exception as e:
            logger.warning(f"Sentiment refresh error: {e}")
        time.sleep(900)   # 15 minutes


def pair_loop(pair_cfg: dict, client, mode: str):
    """
    Independent trading loop for a single pair.
    Runs forever in its own thread.
    """
    symbol   = pair_cfg["symbol"]
    quantity = pair_cfg["quantity"]
    interval = pair_cfg.get("interval", "5m")

    logger.info(f"[{symbol}] Starting — qty={quantity}  interval={interval}")

    risk        = RiskManager()
    performance = PerformanceTracker()
    trader      = Trader(client, symbol, quantity, risk, performance)

    # Init per-pair state
    bot_state.update_pair(symbol, status="running")

    # Snapshot starting balance (shared USDT pool)
    starting_usdt = get_usdt_balance(client)
    risk.set_session_balance(starting_usdt)
    bot_state.update_pair(symbol, starting_balance=starting_usdt, current_balance=starting_usdt)

    prev_indicators = None

    while True:
        try:
            indicators = get_indicators(
                client,
                symbol=symbol,
                interval=interval,
                sma_short=SMA_SHORT,
                sma_long=SMA_LONG,
                rsi_period=RSI_PERIOD,
            )

            if indicators:
                current_price = indicators["close"]
                usdt_now      = get_usdt_balance(client)
                risk.update_balance(usdt_now)

                bot_state.update_pair(
                    symbol,
                    price=current_price,
                    sma_short=indicators["sma_short"],
                    sma_long=indicators["sma_long"],
                    rsi=indicators["rsi"],
                    current_balance=usdt_now,
                    total_pnl=performance.total_pnl,
                    wins=performance.wins,
                    losses=performance.losses,
                )

                if not risk.is_session_limit_hit():
                    with _sentiment_lock:
                        sentiment = dict(_current_sentiment)
                    signal = get_signal(indicators, prev_indicators, sentiment)
                    bot_state.update_pair(symbol, last_signal=signal)
                    trader.tick(signal, current_price)
                else:
                    bot_state.update_pair(symbol, status="halted")
                    notifier.notify_session_halted(MAX_SESSION_LOSS_PCT)

                prev_indicators = indicators

        except Exception as e:
            logger.error(f"[{symbol}] Loop error: {e}")

        time.sleep(FETCH_INTERVAL)


def main():
    mode = "TESTNET" if USE_TESTNET else "LIVE"
    symbols = [p["symbol"] for p in TRADE_PAIRS]

    logger.info(f"=== Binance Bot Core starting ({mode}) ===")
    logger.info(f"Pairs    : {', '.join(symbols)}")
    logger.info(f"Strategy : SMA({SMA_SHORT}/{SMA_LONG}) + RSI({RSI_PERIOD}) + Sentiment")
    logger.info(f"Risk     : stop-loss={STOP_LOSS_PCT}%  |  max session loss={MAX_SESSION_LOSS_PCT}%")

    # ── Start dashboard ───────────────────────────────────────────
    threading.Thread(
        target=run_dashboard,
        kwargs={"host": "0.0.0.0", "port": 5000},
        daemon=True,
    ).start()
    logger.info("Dashboard running at http://localhost:5000")

    # ── Seed state ────────────────────────────────────────────────
    bot_state.update(status="starting", mode=mode)

    # ── Connect ───────────────────────────────────────────────────
    client = get_client()
    if not check_connection(client):
        logger.error("Could not connect to Binance.")
        bot_state.update(status="stopped")
        return

    bot_state.update(status="running")

    # ── Initial sentiment fetch ───────────────────────────────────
    logger.info("Fetching initial sentiment...")
    s = get_sentiment()
    if s:
        with _sentiment_lock:
            _current_sentiment.update(s)
        _update_sentiment_state(s)

    # ── Sentiment refresh thread ──────────────────────────────────
    threading.Thread(target=sentiment_loop, daemon=True).start()

    # ── One thread per pair ───────────────────────────────────────
    threads = []
    for pair_cfg in TRADE_PAIRS:
        t = threading.Thread(
            target=pair_loop,
            args=(pair_cfg, client, mode),
            daemon=True,
            name=pair_cfg["symbol"],
        )
        t.start()
        threads.append(t)
        time.sleep(2)   # stagger starts to avoid API rate limit burst

    notifier.notify_bot_start(", ".join(symbols), "5m", mode)
    logger.info(f"All {len(threads)} pair threads running — Ctrl+C to stop\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nBot stopped by user.")
        bot_state.update(status="stopped")
        notifier.send(f"Bot stopped — {len(TRADE_PAIRS)} pairs were active.")


if __name__ == "__main__":
    main()
